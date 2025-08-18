from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
from google import genai
from google.genai import types
import json
import os
from dotenv import load_dotenv
import subprocess
import uuid
import time


load_dotenv()

app = FastAPI(title="Kigurumi Twitter Crawler", version="1.0.0")


class SocialMedia(BaseModel):
    instagram: Optional[str] = None
    twitter: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None
    pixiv: Optional[str] = None
    website: Optional[str] = None


class Source(BaseModel):
    name: str
    type: str


class Character(BaseModel):
    name: str
    originalName: str
    type: str
    officialImage: str
    source: Source


class KigCharacter(BaseModel):
    characterId: str
    maker: str
    images: List[str]


class Kiger(BaseModel):
    id: str
    name: str
    bio: str
    profileImage: str
    isActive: bool
    socialMedia: SocialMedia
    Characters: List[KigCharacter]
    createdAt: str
    updatedAt: str


class TwitterUserResponse(BaseModel):
    id: str
    name: str
    bio: str
    profileImage: str
    socialMedia: SocialMedia


class TwitterTweetResponse(BaseModel):
    character: Optional[Character]
    images: List[str]


class CharacterImageSearchRequest(BaseModel):
    name: str
    originalName: Optional[str] = None
    source: Optional[str] = None
    type: Optional[str] = None


class CharacterImageSearchResponse(BaseModel):
    name: str
    officialImage: str
    isValid: bool
    sources: List[str]


class ImageValidationRequest(BaseModel):
    url: str


class ImageValidationResponse(BaseModel):
    url: str
    isValid: bool
    message: str
    contentType: Optional[str] = None


async def fetch_twitter_user(username: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"https://api.vxtwitter.com/{username}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to fetch Twitter user: {str(e)}"
            )


async def fetch_twitter_tweet(username: str, tweet_id: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.vxtwitter.com/{username}/status/{tweet_id}"
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to fetch tweet: {str(e)}"
            )


async def validate_image_url(url: str) -> bool:
    if not url:
        return False

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    try:
        async with httpx.AsyncClient(
            timeout=15.0, headers=headers, follow_redirects=True
        ) as client:
            try:
                response = await client.head(url)
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    if content_type.startswith("image/"):
                        return True
            except httpx.HTTPStatusError:
                pass

            try:
                response = await client.get(url, headers={"Range": "bytes=0-1023"})
                if response.status_code in [200, 206]:
                    content_type = response.headers.get("content-type", "")
                    if content_type.startswith("image/"):
                        return True

                    content = response.content[:10]

                    if (
                        content.startswith(b"\x89PNG")
                        or content.startswith(b"\xff\xd8\xff")
                        or content.startswith(b"GIF8")
                        or content.startswith(b"RIFF")
                    ):
                        return True
            except httpx.HTTPStatusError:
                pass

        return False

    except Exception as e:
        print(f"圖片 URL 驗證失敗: {url}, 錯誤: {e}")
        return False


async def get_fallback_character_image(character_data: Dict[str, Any]) -> Optional[str]:
    api_key = os.getenv("GOOGLE_GENAI_API_KEY")
    if not api_key:
        return None

    client = genai.Client(api_key=api_key)

    fallback_instruction = f"""
請為角色「{character_data.get('name', '')}」（{character_data.get('originalName', '')}）
來自作品「{character_data.get('source', {}).get('name', '')}」
提供一個有效的官方圖片 URL。

請嘗試以下圖片來源：
1. 官方遊戲/動漫網站
2. Fandom Wiki 圖片
3. 萌娘百科圖片
4. GamePress 或其他遊戲資料庫
5. 官方 Twitter 或社群媒體

要求：
- 必須是直接的圖片連結（以 .png、.jpg、.jpeg、.webp 結尾）
- 高解析度官方美術圖或角色立繪
- 避免 cosplay 或同人作品
- 確保 URL 可直接訪問

只回傳一個 URL，不要包含其他文字。如果找不到合適的圖片，請回傳 "null"。
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            config=types.GenerateContentConfig(
                system_instruction=fallback_instruction,
                temperature=0.1,
                max_output_tokens=200,
            ),
            contents=[fallback_instruction],
        )

        if response and response.text:
            url = response.text.strip().strip('"')
            if url.lower() == "null":
                return None

            if await validate_image_url(url):
                return url

        return None

    except Exception as e:
        print(f"獲取備選圖片時發生錯誤：{e}")
        return None


async def create_github_pr(
    file_path: str, new_data: Any, commit_message: str, pr_title: str, pr_body: str
) -> Dict[str, Any]:
    """創建 GitHub Pull Request"""

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")

    repo_owner = "phillychi3"
    repo_name = "Kigurumi-static-data"

    branch_name = f"update-data-{uuid.uuid4().hex[:8]}"

    try:
        base_dir = "./"

        # 1. 切換到 main 分支並拉取最新代碼
        subprocess.run(["git", "checkout", "main"], cwd=base_dir, check=True)
        subprocess.run(["git", "pull", "origin", "main"], cwd=base_dir, check=True)

        # 2. 創建新分支
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=base_dir, check=True)

        # 3. 更新文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)

        # 4. 提交變更
        subprocess.run(["git", "add", file_path], cwd=base_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", commit_message], cwd=base_dir, check=True
        )

        # 5. 推送分支
        subprocess.run(["git", "push", "origin", branch_name], cwd=base_dir, check=True)

        # 等待讓 GitHub 同步分支
        time.sleep(3)

        # 6. 驗證分支是否存在於遠程
        try:
            result = subprocess.run(
                ["git", "ls-remote", "--heads", "origin", branch_name],
                cwd=base_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            if not result.stdout.strip():
                raise Exception(f"Branch {branch_name} not found on remote")
        except subprocess.CalledProcessError:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to verify branch {branch_name} on remote",
            )

        # 7. 使用 GitHub API 創建 Pull Request
        async with httpx.AsyncClient() as client:
            # 根據官方文檔使用正確的 headers
            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {github_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }

            # 根據文檔，對於同一個倉庫，head 應該只是分支名
            pr_data = {
                "title": pr_title,
                "head": branch_name,
                "base": "main",
                "body": pr_body,
            }

            print(f"創建 PR - 倉庫: {repo_owner}/{repo_name}")
            print(f"分支: {branch_name} -> main")
            print(f"標題: {pr_title}")

            response = await client.post(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls",
                headers=headers,
                json=pr_data,
            )

            if response.status_code == 201:
                pr_info = response.json()
                return {
                    "success": True,
                    "pr_url": pr_info["html_url"],
                    "pr_number": pr_info["number"],
                    "branch_name": branch_name,
                }
            else:
                error_detail = f"GitHub API Error - Status: {response.status_code}"
                try:
                    error_response = response.json()
                    error_detail += (
                        f", Response: {json.dumps(error_response, indent=2)}"
                    )
                except Exception:
                    error_detail += f", Text: {response.text}"

                print(f"PR 創建失敗: {error_detail}")
                print(f"請求資料: {json.dumps(pr_data, indent=2)}")

                try:
                    subprocess.run(
                        ["git", "checkout", "main"], cwd=base_dir, check=False
                    )
                    subprocess.run(
                        ["git", "branch", "-D", branch_name], cwd=base_dir, check=False
                    )
                    subprocess.run(
                        ["git", "push", "origin", "--delete", branch_name],
                        cwd=base_dir,
                        check=False,
                    )
                except Exception:
                    pass

                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create PR: {error_detail}",
                )

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Git operation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create PR: {str(e)}")


async def parse_character_from_tweet(tweet_data: Dict[str, Any]) -> Optional[Character]:
    api_key = os.getenv("GOOGLE_GENAI_API_KEY")
    if not api_key:
        print("警告：未設置 GOOGLE_GENAI_API_KEY 環境變數")
        return None

    client = genai.Client(api_key=api_key)

    system_instruction = """
你是一個專門識別日本動漫、遊戲角色的專家。請從提供的推文內容和圖片中識別角色資訊，並以 JSON 格式回傳結果。

對於官方圖片搜尋，請優先使用以下來源：
1. 遊戲角色：遊戲官方網站、遊戲 Wiki (如 GamePress、Gameinfo)
2. 動漫角色：動漫官方網站、萌娘百科 (moegirl.org.cn)、Fandom Wiki
3. 虛擬主播：官方 Twitter、官方網站
4. 其他角色：角色設定集、官方美術資料

圖片 URL 格式要求：
- 必須是高解析度的官方美術圖或設定圖
- 避免使用 cosplay 照片或二次創作
- 優先選擇去背的角色立繪
- 如果是遊戲角色，優先使用遊戲內的角色卡面或立繪

回傳格式：
{
  "name": "角色中文名稱",
  "originalName": "角色原文名稱（日文/英文）",
  "type": "角色類型（如：動漫角色、遊戲角色、虛擬主播等）",
  "officialImage": "高品質官方角色圖片 URL（必須是直接圖片連結，如 .png、.jpg 結尾）",
  "source": {
    "name": "來源作品名稱",
    "type": "來源類型（如：動畫、遊戲、輕小說等）"
  }
}

圖片搜尋指引：
- 對於明日方舟角色：優先使用 GitHub Aceship/Arknight-Images 倉庫的直連圖片
- 對於原神角色：使用 Honey Impact 或官方媒體資源
- 對於 FGO 角色：使用 Atlas Academy 或官方資源
- 對於 Vtuber：使用官方網站媒體工具包
- 優先選擇 GitHub raw.githubusercontent.com 連結，因為穩定性最高
- 確保圖片 URL 是可直接訪問的完整連結，避免帶有複雜查詢參數

如果無法識別出明確的角色資訊，請回傳 null。
請只回傳 JSON 格式的資料，不要包含其他說明文字。
"""

    images = []
    if "media_extended" in tweet_data:
        for media in tweet_data["media_extended"]:
            if media.get("type") == "image":
                images.append(media.get("url", ""))

    tweet_text = tweet_data.get("text", "")

    prompt = f"""
推文內容：{tweet_text}

推文完整資料：
{json.dumps(tweet_data, ensure_ascii=False, indent=2)}
"""

    try:
        content_parts = [prompt]

        for image_url in images:
            content_parts.append(image_url)

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
                max_output_tokens=1024,
            ),
            contents=content_parts,
        )

        if response and response.text:
            try:
                response_text = response.text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]

                response_text = response_text.strip()

                if response_text.lower() == "null":
                    return None

                character_data = json.loads(response_text)

                if not all(
                    key in character_data
                    for key in ["name", "originalName", "type", "source"]
                ):
                    print(f"警告：回應缺少必要欄位：{character_data}")
                    return None

                official_image = character_data.get("officialImage", "")

                if official_image:
                    is_valid = await validate_image_url(official_image)
                    if not is_valid:
                        print(f"警告：官方圖片 URL 無效或無法訪問：{official_image}")
                        fallback_image = await get_fallback_character_image(
                            character_data
                        )
                        official_image = fallback_image if fallback_image else ""

                character = Character(
                    name=character_data["name"],
                    originalName=character_data["originalName"],
                    type=character_data["type"],
                    officialImage=official_image,
                    source=Source(
                        name=character_data["source"]["name"],
                        type=character_data["source"]["type"],
                    ),
                )

                return character

            except json.JSONDecodeError as e:
                print(f"JSON 解析錯誤：{e}")
                print(f"原始回應：{response.text}")
                return None
            except KeyError as e:
                print(f"回應格式錯誤，缺少欄位：{e}")
                print(f"原始回應：{response.text}")
                return None

        return None

    except Exception as e:
        print(f"角色識別過程中發生錯誤：{e}")
        return None


@app.get("/")
async def root():
    return {"message": "Kigurumi Twitter Crawler API"}


@app.get("/twitter/{username}", response_model=Kiger)
async def get_twitter_user(username: str):
    """獲取 Twitter 用戶資訊"""

    twitter_data = await fetch_twitter_user(username)

    user_id = username
    name = twitter_data.get("name", username)
    bio = twitter_data.get("description", "")
    profile_image = twitter_data.get("profile_image_url", "")

    social_media = SocialMedia()
    social_media.twitter = f"https://twitter.com/{username}"

    return Kiger(
        id=user_id,
        name=name,
        bio=bio,
        profileImage=profile_image,
        socialMedia=social_media,
        isActive=True,
        Characters=[],
        createdAt=time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        updatedAt=time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    )


@app.get("/twitter/{username}/status/{tweet_id}", response_model=TwitterTweetResponse)
async def analyze_tweet_for_character(username: str, tweet_id: str):
    """分析推文以提取角色資訊"""

    tweet_data = await fetch_twitter_tweet(username, tweet_id)

    images = []
    if "media_extended" in tweet_data:
        for media in tweet_data["media_extended"]:
            if media.get("type") == "image":
                images.append(media.get("url", ""))

    character = await parse_character_from_tweet(tweet_data)

    return TwitterTweetResponse(character=character, images=images)


@app.post("/kiger", response_model=Dict[str, str])
async def save_kiger(kiger: Kiger):
    """保存 Kiger 資料並創建 GitHub Pull Request"""

    try:
        file_path = "kiger.json"

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        data[kiger.id] = kiger.model_dump()

        commit_message = f"Add/Update Kiger: {kiger.name} ({kiger.id})"
        pr_title = f"🎭 新增/更新 Kiger 資料: {kiger.name}"
        pr_body = f"""## 新增/更新 Kiger 資料

**Kiger 資訊:**
- ID: `{kiger.id}`
- 名稱: {kiger.name}
- 簡介: {kiger.bio}
- 狀態: {'活躍' if kiger.isActive else '非活躍'}
- 角色數量: {len(kiger.Characters)}

**社交媒體:**
{f'- Twitter: {kiger.socialMedia.twitter}' if kiger.socialMedia.twitter else ''}
{f'- Instagram: {kiger.socialMedia.instagram}' if kiger.socialMedia.instagram else ''}
{f'- Facebook: {kiger.socialMedia.facebook}' if kiger.socialMedia.facebook else ''}
{f'- Website: {kiger.socialMedia.website}' if kiger.socialMedia.website else ''}

此 PR 由 Kigurumi Crawler API 自動生成。
"""

        result = await create_github_pr(
            file_path=file_path,
            new_data=data,
            commit_message=commit_message,
            pr_title=pr_title,
            pr_body=pr_body,
        )

        return {
            "message": f"Kiger {kiger.id} PR created successfully",
            "pr_url": result["pr_url"],
            "pr_number": str(result["pr_number"]),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create Kiger PR: {str(e)}"
        )


@app.post("/character", response_model=Dict[str, str])
async def save_character(character: Character):
    """保存角色資料並創建 GitHub Pull Request"""

    try:
        file_path = "character.json"

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    data = []
        except (FileNotFoundError, json.JSONDecodeError):
            data = []

        existing_character = None
        for i, existing in enumerate(data):
            if (
                existing.get("name") == character.name
                and existing.get("originalName") == character.originalName
                and existing.get("source", {}).get("name") == character.source.name
            ):
                existing_character = i
                break

        if existing_character is not None:
            data[existing_character] = character.model_dump()
            action = "更新"
        else:
            data.append(character.model_dump())
            action = "新增"

        commit_message = f"{action} Character: {character.name} ({character.originalName}) from {character.source.name}"
        pr_title = f"🎨 {action}角色資料: {character.name}"
        pr_body = f"""## {action}角色資料

**角色資訊:**
- 名稱: {character.name}
- 原文名稱: {character.originalName}
- 類型: {character.type}
- 來源作品: {character.source.name} ({character.source.type})

**官方圖片:**
![{character.name}]({character.officialImage})

**操作:** {action}現有角色資料

此 PR 由 Kigurumi Crawler API 自動生成。
"""

        result = await create_github_pr(
            file_path=file_path,
            new_data=data,
            commit_message=commit_message,
            pr_title=pr_title,
            pr_body=pr_body,
        )

        return {
            "message": f"Character {character.name} PR created successfully",
            "pr_url": result["pr_url"],
            "pr_number": str(result["pr_number"]),
            "action": action,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create Character PR: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
