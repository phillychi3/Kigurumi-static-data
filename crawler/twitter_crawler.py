import httpx
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
import json
import os


async def fetch_twitter_user(username: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.vxtwitter.com/{username}")
        response.raise_for_status()
        return response.json()


async def fetch_twitter_tweet(username: str, tweet_id: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.vxtwitter.com/{username}/status/{tweet_id}"
        )
        response.raise_for_status()
        return response.json()


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
來自作品「{character_data.get('source', {}).get('title', '')}」
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


async def parse_character_from_tweet(
    tweet_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
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
  "type": "角色類型（game/anime/vtuber/oc/other）",
  "officialImage": "高品質官方角色圖片 URL（必須是直接圖片連結，如 .png、.jpg 結尾）",
  "source": {
    "title": "來源作品名稱",
    "company": "公司/製作方",
    "releaseYear": 發布年份（數字）
  }
}

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

                character_data["officialImage"] = official_image

                return character_data

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
