from fastapi import FastAPI, HTTPException
from typing import Dict, Any
import json
import os
import time

from .models import (
    Kiger,
    Character,
    Maker,
    CrawlTwitterUserRequest,
    CrawlTwitterTweetRequest,
)
from .github_service import create_github_pr
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from crawler import (
    fetch_twitter_user,
    fetch_twitter_tweet,
    parse_character_from_tweet,
)


app = FastAPI(title="Kigurumi Data API", version="1.0.0")


@app.get("/")
async def root():
    return {"message": "Kigurumi Static Data API"}


@app.post("/crawl/twitter/user")
async def crawl_twitter_user(request: CrawlTwitterUserRequest):
    try:
        twitter_data = await fetch_twitter_user(request.username)

        user_id = request.username
        name = twitter_data.get("name", request.username)
        bio = twitter_data.get("description", "")
        profile_image = twitter_data.get("profile_image_url", "")

        kiger_data = {
            "id": user_id,
            "name": name,
            "bio": bio,
            "profileImage": profile_image,
            "position": "",
            "isActive": True,
            "socialMedia": {
                "twitter": f"https://twitter.com/{request.username}",
            },
            "Characters": [],
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }

        return kiger_data

    except Exception as e:
        raise Exception(f"Failed to fetch Twitter user: {str(e)}")


async def save_kiger_with_pr(kiger_data: Dict[str, Any]) -> Dict[str, Any]:
    file_path = "kiger.json"

    try:
        full_path = os.path.join(os.path.dirname(__file__), "..", file_path)
        with open(full_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                data = {}
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    data[kiger_data["id"]] = kiger_data

    commit_message = f"Add/Update Kiger: {kiger_data['name']} ({kiger_data['id']})"
    pr_title = f"新增/更新 Kiger 資料: {kiger_data['name']}"
    pr_body = f"""## 新增/更新 Kiger 資料

**Kiger 資訊:**
- ID: `{kiger_data['id']}`
- 名稱: {kiger_data['name']}
- 簡介: {kiger_data['bio']}
- 狀態: {'活躍' if kiger_data['isActive'] else '非活躍'}
- 角色數量: {len(kiger_data.get('Characters', []))}

**社交媒體:**
{f"- Twitter: {kiger_data['socialMedia'].get('twitter')}" if kiger_data.get('socialMedia', {}).get('twitter') else ''}
{f"- Instagram: {kiger_data['socialMedia'].get('instagram')}" if kiger_data.get('socialMedia', {}).get('instagram') else ''}

此 PR 由 Kigurumi Crawler API 自動生成。
"""

    result = await create_github_pr(
        file_path=file_path,
        new_data=data,
        commit_message=commit_message,
        pr_title=pr_title,
        pr_body=pr_body,
    )

    return result


@app.post("/crawl/twitter/tweet")
async def crawl_twitter_tweet(request: CrawlTwitterTweetRequest):
    try:
        tweet_data = await fetch_twitter_tweet(request.username, request.tweet_id)

        images = []
        if "media_extended" in tweet_data:
            for media in tweet_data["media_extended"]:
                if media.get("type") == "image":
                    images.append(media.get("url", ""))

        character = await parse_character_from_tweet(tweet_data)

        return {
            "character": character,
            "images": images,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze tweet: {str(e)}"
        )


@app.post("/kiger")
async def save_kiger(kiger_data: Kiger):
    try:
        result = await save_kiger_with_pr(kiger_data.model_dump())
        return {
            "message": f"Kiger {kiger_data.id} PR created successfully",
            "pr_url": result["pr_url"],
            "pr_number": result["pr_number"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save kiger: {str(e)}")


@app.post("/character")
async def save_character(character_data: Character):
    try:
        character_dict = character_data.model_dump()
        file_path = "character.json"

        full_path = os.path.join(os.path.dirname(__file__), "..", file_path)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        character_id = character_data.originalName
        data[character_id] = character_dict

        commit_message = f"Add/Update Character: {character_data.name} ({character_data.originalName})"
        pr_title = f"新增/更新角色資料: {character_data.name}"
        pr_body = f"""## 新增/更新角色資料

**角色資訊:**
- 名稱: {character_data.name}
- 原文名稱: {character_data.originalName}
- 類型: {character_data.type}
- 來源作品: {character_data.source.title} ({character_data.source.company})

**官方圖片:**
![{character_data.name}]({character_data.officialImage})

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
            "message": f"Character {character_data.name} PR created successfully",
            "pr_url": result["pr_url"],
            "pr_number": result["pr_number"],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to save character: {str(e)}"
        )


@app.post("/maker")
async def save_maker(maker_data: Maker):
    try:
        maker_dict = maker_data.model_dump()
        file_path = "maker.json"

        full_path = os.path.join(os.path.dirname(__file__), "..", file_path)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        maker_id = maker_data.originalName
        data[maker_id] = maker_dict

        commit_message = (
            f"Add/Update Maker: {maker_data.name} ({maker_data.originalName})"
        )
        pr_title = f"新增/更新製作商資料: {maker_data.name}"

        twitter_line = (
            f"- Twitter: {maker_data.socialMedia.twitter}"
            if maker_data.socialMedia.twitter
            else ""
        )
        website_line = (
            f"- Website: {maker_data.socialMedia.website}"
            if maker_data.socialMedia.website
            else ""
        )

        pr_body = f"""## 新增/更新製作商資料

**製作商資訊:**
- 名稱: {maker_data.name}
- 原文名稱: {maker_data.originalName}

**社交媒體:**
{twitter_line}
{website_line}

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
            "message": f"Maker {maker_data.name} PR created successfully",
            "pr_url": result["pr_url"],
            "pr_number": result["pr_number"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save maker: {str(e)}")
