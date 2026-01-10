from pydantic import BaseModel, Field
from typing import List, Optional


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
    name: str
    originalName: str
    type: str
    officialImage: str
    source: Source


class CharacterReference(BaseModel):
    characterId: str
    maker: Optional[str] = None
    images: List[str]


class Kiger(BaseModel):
    id: str
    name: str
    bio: str
    profileImage: str
    position: str = ""
    isActive: bool
    socialMedia: SocialMedia
    Characters: List[CharacterReference]
    createdAt: str
    updatedAt: str


class MakerSocialMedia(BaseModel):
    twitter: Optional[str] = None
    facebook: Optional[str] = None
    taobao: Optional[str] = None
    amazon: Optional[str] = None
    website: Optional[str] = None


class Maker(BaseModel):
    name: str
    originalName: str
    Avatar: str
    socialMedia: MakerSocialMedia


class CrawlTwitterUserRequest(BaseModel):
    username: str


class CrawlTwitterTweetRequest(BaseModel):
    username: str
    tweet_id: str


class UpdateDataRequest(BaseModel):
    data_type: str = Field(..., description="kiger, character, or maker")
    data: dict
