from typing import List, Optional

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """通用訊息回應"""

    message: str


class SubmitResponse(BaseModel):
    """提交資料的回應"""

    message: str
    status: str
    id: str


class KigerListItemResponse(BaseModel):
    """Kiger 列表項目回應"""

    id: str
    name: str
    bio: Optional[str] = ""
    profileImage: Optional[str] = ""
    position: Optional[str] = ""
    isActive: bool = True
    socialMedia: Optional[dict] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class CharacterReferenceResponse(BaseModel):
    """角色引用回應（在 Kiger 詳情中使用）"""

    characterId: int
    maker: Optional[str] = None
    images: List[str] = []


class KigerDetailResponse(BaseModel):
    """Kiger 詳細資料回應"""

    id: str
    name: str
    bio: Optional[str] = ""
    profileImage: Optional[str] = ""
    position: Optional[str] = ""
    isActive: bool = True
    socialMedia: Optional[dict] = None
    Characters: List[CharacterReferenceResponse] = []
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class SourceResponse(BaseModel):
    """來源資訊回應"""

    title: str
    company: str
    releaseYear: int


class CharacterResponse(BaseModel):
    """角色資料回應"""

    id: int
    name: str
    originalName: str
    type: str
    officialImage: Optional[str] = ""
    source: Optional[dict] = None


class MakerResponse(BaseModel):
    """Maker 資料回應"""

    id: int
    name: str
    originalName: str
    Avatar: Optional[str] = ""
    socialMedia: Optional[dict] = None


class TwitterUserCrawlResponse(BaseModel):
    """Twitter 用戶爬蟲回應"""

    id: str
    name: str
    bio: str
    profileImage: str
    position: str
    isActive: bool
    socialMedia: dict
    Characters: List[CharacterReferenceResponse]
    createdAt: str
    updatedAt: str


class TwitterTweetCrawlResponse(BaseModel):
    """Twitter 推文爬蟲回應"""

    character: Optional[dict] = None
    images: List[str] = []


class ImageCharacterCrawlResponse(BaseModel):
    """圖片角色識別回應"""

    success: bool
    character: Optional[dict] = None
    error: Optional[str] = None


class LoginResponse(BaseModel):
    """登入回應"""

    access_token: str
    token_type: str = "bearer"
    username: str


class PendingKigerResponse(BaseModel):
    """待審核 Kiger 回應"""

    id: str
    referenceId: Optional[str] = None
    name: str
    bio: Optional[str] = ""
    profileImage: Optional[str] = ""
    position: Optional[str] = ""
    isActive: bool = True
    socialMedia: Optional[dict] = None
    Characters: List[str] = []
    changedFields: Optional[List[str]] = None
    status: str
    submitted_at: Optional[str] = None


class PendingCharacterResponse(BaseModel):
    """待審核 Character 回應"""

    id: int
    originalName: str
    name: str
    type: str
    officialImage: Optional[str] = ""
    source: Optional[dict] = None
    changedFields: Optional[List[str]] = None
    status: str
    submitted_at: Optional[str] = None


class PendingMakerResponse(BaseModel):
    """待審核 Maker 回應"""

    id: int
    originalName: str
    name: str
    Avatar: Optional[str] = ""
    socialMedia: Optional[dict] = None
    changedFields: Optional[List[str]] = None
    status: str
    submitted_at: Optional[str] = None


class ReviewResponse(BaseModel):
    """審核回應"""

    message: str
    status: str


class KigerListResponse(BaseModel):
    """Kiger 列表回應"""

    data: List[KigerListItemResponse] = Field(default_factory=list)
    total: int = 0


class CharacterListResponse(BaseModel):
    """Character 列表回應"""

    data: List[CharacterResponse] = Field(default_factory=list)
    total: int = 0


class MakerListResponse(BaseModel):
    """Maker 列表回應"""

    data: List[MakerResponse] = Field(default_factory=list)
    total: int = 0


class PendingKigerListResponse(BaseModel):
    """待審核 Kiger 列表回應"""

    data: List[PendingKigerResponse] = Field(default_factory=list)
    total: int = 0


class PendingCharacterListResponse(BaseModel):
    """待審核 Character 列表回應"""

    data: List[PendingCharacterResponse] = Field(default_factory=list)
    total: int = 0


class PendingMakerListResponse(BaseModel):
    """待審核 Maker 列表回應"""

    data: List[PendingMakerResponse] = Field(default_factory=list)
    total: int = 0
