from typing import List, Optional

from pydantic import BaseModel, Field


class SocialMedia(BaseModel):
    instagram: Optional[str] = None
    twitter: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None
    pixiv: Optional[str] = None
    website: Optional[str] = None


class Source(BaseModel):
    title: str
    company: str
    releaseYear: int


class Character(BaseModel):
    id: Optional[int] = None
    name: str
    originalName: str
    type: str
    officialImage: str
    source: Source
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class CharacterReference(BaseModel):
    characterId: str
    maker: Optional[str] = None
    images: List[str]
    characterData: Optional["Character"] = None


class Kiger(BaseModel):
    id: Optional[str] = None
    referenceId: Optional[str] = None
    name: str
    bio: str
    profileImage: str
    position: str = ""
    isActive: bool
    socialMedia: SocialMedia
    Characters: List[CharacterReference]
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class MakerSocialMedia(BaseModel):
    twitter: Optional[str] = None
    facebook: Optional[str] = None
    taobao: Optional[str] = None
    amazon: Optional[str] = None
    website: Optional[str] = None


class Maker(BaseModel):
    id: Optional[int] = None
    name: str
    originalName: str
    Avatar: str
    socialMedia: MakerSocialMedia
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class CrawlTwitterUserRequest(BaseModel):
    username: str


class CrawlTwitterTweetRequest(BaseModel):
    username: str
    tweet_id: str


class CrawlImageRequest(BaseModel):
    """從圖片 URL 識別角色的請求"""
    image_url: str = Field(..., description="要識別的圖片 URL")


class UpdateDataRequest(BaseModel):
    data_type: str = Field(..., description="kiger, character, or maker")
    data: dict
