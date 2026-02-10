import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import authenticate_admin, create_access_token, get_current_admin
from .cache import delete_cache, get_cache, invalidate_cache_by_prefix, set_cache
from .database import Character as DBCharacter
from .database import Kiger as DBKiger
from .database import KigerCharacter
from .database import Maker as DBMaker
from .database import PendingCharacter, PendingKiger, PendingMaker, get_db, init_db
from .models import (
    Character,
    CrawlImageRequest,
    CrawlTwitterTweetRequest,
    CrawlTwitterUserRequest,
    Kiger,
    Maker,
)
from .schemas import (
    CharacterReferenceResponse,
    CharacterResponse,
    ImageCharacterCrawlResponse,
    KigerDetailResponse,
    KigerListItemResponse,
    LoginResponse,
    MakerResponse,
    MessageResponse,
    PendingCharacterResponse,
    PendingKigerResponse,
    PendingMakerResponse,
    ReviewResponse,
    SubmitResponse,
    TwitterTweetCrawlResponse,
    TwitterUserCrawlResponse,
)

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from crawler import (
    fetch_twitter_tweet,
    fetch_twitter_user,
    parse_character_from_tweet,
    parse_character_image,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Kigurumi Data API", version="2.0.0", lifespan=lifespan)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=MessageResponse)
async def root():
    return MessageResponse(message="Kigurumi Static Data API v2.0 - Database Edition")


@app.post("/crawl/twitter/user", response_model=TwitterUserCrawlResponse)
@limiter.limit("1/3seconds")
async def crawl_twitter_user(payload: CrawlTwitterUserRequest, request: Request):
    try:
        twitter_data = await fetch_twitter_user(payload.username)

        user_id = payload.username
        name = twitter_data.get("name", payload.username)
        bio = twitter_data.get("description", "")
        profile_image = twitter_data.get("profile_image_url", "")

        return TwitterUserCrawlResponse(
            id=user_id,
            name=name,
            bio=bio,
            profileImage=profile_image,
            position="",
            isActive=True,
            socialMedia={
                "twitter": f"https://twitter.com/{payload.username}",
            },
            Characters=[],
            createdAt=datetime.utcnow().isoformat() + "Z",
            updatedAt=datetime.utcnow().isoformat() + "Z",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch Twitter user: {str(e)}"
        )


@app.post("/crawl/twitter/tweet", response_model=TwitterTweetCrawlResponse)
@limiter.limit("1/3seconds")
async def crawl_twitter_tweet(payload: CrawlTwitterTweetRequest, request: Request):
    try:
        tweet_data = await fetch_twitter_tweet(payload.username, payload.tweet_id)

        images = []
        if "media_extended" in tweet_data:
            for media in tweet_data["media_extended"]:
                if media.get("type") == "image":
                    images.append(media.get("url", ""))

        character = await parse_character_from_tweet(tweet_data)
        if not character:
            raise HTTPException(
                status_code=404, detail="No character information found in the tweet"
            )

        return TwitterTweetCrawlResponse(
            character=character,
            images=images,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze tweet: {str(e)}"
        )


@app.post("/crawl/image", response_model=ImageCharacterCrawlResponse)
@limiter.limit("1/3seconds")
async def crawl_image(payload: CrawlImageRequest, request: Request):
    try:
        if not payload.image_url:
            return ImageCharacterCrawlResponse(success=False, error="圖片 URL 不能為空")

        if not payload.image_url.startswith(("http://", "https://")):
            return ImageCharacterCrawlResponse(
                success=False,
                error="無效的圖片 URL 格式，必須以 http:// 或 https:// 開頭",
            )

        character = await parse_character_image(payload.image_url)

        if character:
            return ImageCharacterCrawlResponse(success=True, character=character)
        else:
            return ImageCharacterCrawlResponse(
                success=False,
                error="無法從圖片中識別出角色資訊，請確保圖片清晰且包含明確的角色形象",
            )

    except Exception as e:
        return ImageCharacterCrawlResponse(
            success=False, error=f"識別過程發生錯誤: {str(e)}"
        )


@app.post("/kiger", response_model=SubmitResponse)
async def submit_kiger(kiger_data: Kiger, db: AsyncSession = Depends(get_db)):
    try:
        kiger_dict = kiger_data.model_dump()

        kiger_id = str(uuid4())
        reference_id = kiger_dict.get("referenceId")

        changed_fields = None
        if reference_id:
            existing_result = await db.execute(
                select(DBKiger).where(DBKiger.id == reference_id)
            )
            existing_official = existing_result.scalar_one_or_none()
            if existing_official:
                changed_fields = []
                field_map = {
                    "name": ("name", existing_official.name),
                    "bio": ("bio", existing_official.bio),
                    "profile_image": ("profileImage", existing_official.profile_image),
                    "position": ("position", existing_official.position),
                    "is_active": ("isActive", existing_official.is_active),
                    "social_media": ("socialMedia", existing_official.social_media),
                    "characters": ("Characters", None),
                }
                for db_field, (dict_key, official_val) in field_map.items():
                    submitted_val = kiger_dict.get(dict_key)
                    if db_field == "social_media":
                        submitted_val = kiger_dict.get("socialMedia", {})
                    if submitted_val != official_val:
                        changed_fields.append(db_field)

        # 檢查 Characters 引用的 character 是否存在，不存在則自動建立 PendingCharacter
        auto_created_character_ids = []
        for char_ref in kiger_dict.get("Characters", []):
            char_id = char_ref.get("characterId")
            if not char_id:
                continue

            existing_char = await db.execute(
                select(DBCharacter).where(DBCharacter.id == int(char_id))
            )
            if existing_char.scalar_one_or_none():
                continue

            existing_pending = await db.execute(
                select(PendingCharacter).where(
                    PendingCharacter.original_name == str(char_id),
                    PendingCharacter.status == "pending",
                )
            )
            if existing_pending.scalar_one_or_none():
                continue

            char_data = char_ref.get("characterData")
            if char_data:
                pending_char = PendingCharacter(
                    original_name=char_data.get("originalName", str(char_id)),
                    name=char_data.get("name", ""),
                    type=char_data.get("type", ""),
                    official_image=char_data.get("officialImage", ""),
                    source=char_data.get("source"),
                    changed_fields=None,
                    status="pending",
                    submitted_at=datetime.utcnow(),
                )
                db.add(pending_char)
                await db.flush()
                auto_created_character_ids.append(pending_char.id)

        pending_kiger = PendingKiger(
            id=kiger_id,
            reference_id=reference_id,
            name=kiger_dict["name"],
            bio=kiger_dict["bio"],
            profile_image=kiger_dict.get("profileImage", ""),
            position=kiger_dict.get("position", ""),
            is_active=kiger_dict.get("isActive", True),
            social_media=kiger_dict.get("socialMedia", {}),
            characters=kiger_dict.get("Characters", []),
            auto_created_characters=auto_created_character_ids or None,
            changed_fields=changed_fields,
            status="pending",
            submitted_at=datetime.utcnow(),
        )

        db.add(pending_kiger)
        await db.commit()

        return SubmitResponse(
            message=f"Kiger {kiger_id} submitted for review",
            status="pending",
            id=kiger_id,
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to submit kiger: {str(e)}")


@app.post("/character", response_model=SubmitResponse)
async def submit_character(
    character_data: Character, db: AsyncSession = Depends(get_db)
):
    try:
        character_dict = character_data.model_dump()

        changed_fields = None
        existing_result = await db.execute(
            select(DBCharacter).where(
                DBCharacter.original_name == character_dict["originalName"]
            )
        )
        existing_official = existing_result.scalar_one_or_none()
        if existing_official:
            changed_fields = []
            if character_dict["name"] != existing_official.name:
                changed_fields.append("name")
            if character_dict["type"] != existing_official.type:
                changed_fields.append("type")
            if (
                character_dict.get("officialImage", "")
                != existing_official.official_image
            ):
                changed_fields.append("official_image")
            submitted_source = (
                character_dict.get("source", {})
                if character_dict.get("source")
                else None
            )
            if submitted_source != existing_official.source:
                changed_fields.append("source")

        pending_character = PendingCharacter(
            original_name=character_dict["originalName"],
            name=character_dict["name"],
            type=character_dict["type"],
            official_image=character_dict.get("officialImage", ""),
            source=character_dict.get("source", {})
            if character_dict.get("source")
            else None,
            changed_fields=changed_fields,
            status="pending",
            submitted_at=datetime.utcnow(),
        )

        db.add(pending_character)
        await db.commit()
        await db.refresh(pending_character)

        return SubmitResponse(
            message=f"Character {character_data.name} submitted for review",
            status="pending",
            id=str(pending_character.id),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to submit character: {str(e)}"
        )


@app.post("/maker", response_model=SubmitResponse)
async def submit_maker(maker_data: Maker, db: AsyncSession = Depends(get_db)):
    """提交 Maker 資料，進入待審核狀態"""
    try:
        maker_dict = maker_data.model_dump()

        changed_fields = None
        existing_result = await db.execute(
            select(DBMaker).where(DBMaker.original_name == maker_dict["originalName"])
        )
        existing_official = existing_result.scalar_one_or_none()
        if existing_official:
            changed_fields = []
            if maker_dict["name"] != existing_official.name:
                changed_fields.append("name")
            if maker_dict.get("Avatar", "") != existing_official.avatar:
                changed_fields.append("avatar")
            submitted_sm = (
                maker_dict.get("socialMedia", {})
                if maker_dict.get("socialMedia")
                else None
            )
            if submitted_sm != existing_official.social_media:
                changed_fields.append("social_media")

        pending_maker = PendingMaker(
            original_name=maker_dict["originalName"],
            name=maker_dict["name"],
            avatar=maker_dict.get("Avatar", ""),
            social_media=maker_dict.get("socialMedia", {})
            if maker_dict.get("socialMedia")
            else None,
            changed_fields=changed_fields,
            status="pending",
            submitted_at=datetime.utcnow(),
        )

        db.add(pending_maker)
        await db.commit()
        await db.refresh(pending_maker)

        return SubmitResponse(
            message=f"Maker {maker_data.name} submitted for review",
            status="pending",
            id=str(pending_maker.id),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to submit maker: {str(e)}")


@app.get("/kigers", response_model=list[KigerListItemResponse])
async def get_all_kigers(db: AsyncSession = Depends(get_db)):
    """取得所有 Kiger 資料"""
    cache_key = "all_kigers"

    cached = get_cache(cache_key)
    if cached:
        return cached

    result = await db.execute(select(DBKiger))
    kigers = result.scalars().all()

    kigers_list = [
        KigerListItemResponse(
            id=kiger.id,
            name=kiger.name,
            bio=kiger.bio,
            profileImage=kiger.profile_image,
            position=kiger.position,
            isActive=kiger.is_active,
            socialMedia=kiger.social_media,
            createdAt=kiger.created_at.isoformat() + "Z" if kiger.created_at else None,
            updatedAt=kiger.updated_at.isoformat() + "Z" if kiger.updated_at else None,
        )
        for kiger in kigers
    ]

    set_cache(cache_key, [k.model_dump() for k in kigers_list])

    return kigers_list


@app.get("/kiger/{kiger_id}", response_model=KigerDetailResponse)
async def get_kiger(kiger_id: str, db: AsyncSession = Depends(get_db)):
    """取得單一 Kiger 資料"""
    cache_key = f"kiger:{kiger_id}"

    cached = get_cache(cache_key)
    if cached:
        return cached

    result = await db.execute(select(DBKiger).where(DBKiger.id == kiger_id))
    kiger = result.scalar_one_or_none()

    if not kiger:
        raise HTTPException(status_code=404, detail="Kiger not found")

    characters_result = await db.execute(
        select(KigerCharacter).where(KigerCharacter.kiger_id == kiger_id)
    )
    kiger_characters = characters_result.scalars().all()

    characters_list = [
        CharacterReferenceResponse(
            characterId=kc.character_id,
            maker=kc.maker,
            images=kc.images or [],
        )
        for kc in kiger_characters
    ]

    kiger_response = KigerDetailResponse(
        id=kiger.id,
        name=kiger.name,
        bio=kiger.bio,
        profileImage=kiger.profile_image,
        position=kiger.position,
        isActive=kiger.is_active,
        socialMedia=kiger.social_media,
        Characters=characters_list,
        createdAt=kiger.created_at.isoformat() + "Z" if kiger.created_at else None,
        updatedAt=kiger.updated_at.isoformat() + "Z" if kiger.updated_at else None,
    )

    set_cache(cache_key, kiger_response.model_dump())

    return kiger_response


@app.get("/characters", response_model=list[CharacterResponse])
async def get_all_characters(db: AsyncSession = Depends(get_db)):
    """取得所有 Character 資料"""
    cache_key = "all_characters"

    cached = get_cache(cache_key)
    if cached:
        return cached

    result = await db.execute(select(DBCharacter))
    characters = result.scalars().all()

    characters_list = [
        CharacterResponse(
            id=character.id,
            name=character.name,
            originalName=character.original_name,
            type=character.type,
            officialImage=character.official_image,
            source=character.source,
        )
        for character in characters
    ]

    set_cache(cache_key, [c.model_dump() for c in characters_list])

    return characters_list


@app.get("/character/{character_id}", response_model=CharacterResponse)
async def get_character(character_id: int, db: AsyncSession = Depends(get_db)):
    """取得單一 Character 資料"""
    cache_key = f"character:{character_id}"

    cached = get_cache(cache_key)
    if cached:
        return cached

    result = await db.execute(select(DBCharacter).where(DBCharacter.id == character_id))
    character = result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    character_response = CharacterResponse(
        id=character.id,
        name=character.name,
        originalName=character.original_name,
        type=character.type,
        officialImage=character.official_image,
        source=character.source,
    )

    set_cache(cache_key, character_response.model_dump())

    return character_response


@app.get("/makers", response_model=list[MakerResponse])
async def get_all_makers(db: AsyncSession = Depends(get_db)):
    """取得所有 Maker 資料"""
    cache_key = "all_makers"

    cached = get_cache(cache_key)
    if cached:
        return cached

    result = await db.execute(select(DBMaker))
    makers = result.scalars().all()

    makers_list = [
        MakerResponse(
            id=maker.id,
            name=maker.name,
            originalName=maker.original_name,
            Avatar=maker.avatar,
            socialMedia=maker.social_media,
        )
        for maker in makers
    ]

    set_cache(cache_key, [m.model_dump() for m in makers_list])

    return makers_list


@app.get("/maker/{maker_id}", response_model=MakerResponse)
async def get_maker(maker_id: int, db: AsyncSession = Depends(get_db)):
    cache_key = f"maker:{maker_id}"

    # 檢查快取
    cached = get_cache(cache_key)
    if cached:
        return cached

    result = await db.execute(select(DBMaker).where(DBMaker.id == maker_id))
    maker = result.scalar_one_or_none()

    if not maker:
        raise HTTPException(status_code=404, detail="Maker not found")

    maker_response = MakerResponse(
        id=maker.id,
        name=maker.name,
        originalName=maker.original_name,
        Avatar=maker.avatar,
        socialMedia=maker.social_media,
    )

    set_cache(cache_key, maker_response.model_dump())

    return maker_response


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/admin/login", response_model=LoginResponse)
async def admin_login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    admin = await authenticate_admin(db, request.username, request.password)

    if not admin:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    access_token = create_access_token(data={"sub": admin.username})

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        username=admin.username,
    )


@app.get(
    "/admin/pending/kigers",
    response_model=list[PendingKigerResponse],
    dependencies=[Depends(get_current_admin)],
)
async def get_pending_kigers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PendingKiger)
        .where(PendingKiger.status == "pending")
        .order_by(PendingKiger.submitted_at.asc())
    )
    pending_kigers = result.scalars().all()

    return [
        PendingKigerResponse(
            id=pk.id,
            referenceId=pk.reference_id,
            name=pk.name,
            bio=pk.bio,
            profileImage=pk.profile_image,
            position=pk.position,
            isActive=pk.is_active,
            socialMedia=pk.social_media,
            Characters=pk.characters or [],
            changedFields=pk.changed_fields,
            status=pk.status,
            submitted_at=pk.submitted_at.isoformat() if pk.submitted_at else None,
        )
        for pk in pending_kigers
    ]


@app.get(
    "/admin/pending/characters",
    response_model=list[PendingCharacterResponse],
    dependencies=[Depends(get_current_admin)],
)
async def get_pending_characters(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PendingCharacter)
        .where(PendingCharacter.status == "pending")
        .order_by(PendingCharacter.submitted_at.asc())
    )
    pending_characters = result.scalars().all()

    return [
        PendingCharacterResponse(
            id=pc.id,
            originalName=pc.original_name,
            name=pc.name,
            type=pc.type,
            officialImage=pc.official_image,
            source=pc.source,
            changedFields=pc.changed_fields,
            status=pc.status,
            submitted_at=pc.submitted_at.isoformat() if pc.submitted_at else None,
        )
        for pc in pending_characters
    ]


@app.get(
    "/admin/pending/makers",
    response_model=list[PendingMakerResponse],
    dependencies=[Depends(get_current_admin)],
)
async def get_pending_makers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PendingMaker)
        .where(PendingMaker.status == "pending")
        .order_by(PendingMaker.submitted_at.asc())
    )
    pending_makers = result.scalars().all()

    return [
        PendingMakerResponse(
            id=pm.id,
            originalName=pm.original_name,
            name=pm.name,
            Avatar=pm.avatar,
            socialMedia=pm.social_media,
            changedFields=pm.changed_fields,
            status=pm.status,
            submitted_at=pm.submitted_at.isoformat() if pm.submitted_at else None,
        )
        for pm in pending_makers
    ]


class ReviewRequest(BaseModel):
    action: str  # "approve" or "reject"


@app.post(
    "/admin/review/kiger/{kiger_id}",
    response_model=ReviewResponse,
    dependencies=[Depends(get_current_admin)],
)
async def review_kiger(
    kiger_id: str, request: ReviewRequest, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(PendingKiger).where(PendingKiger.id == kiger_id))
    pending = result.scalar_one_or_none()

    if not pending:
        raise HTTPException(status_code=404, detail="Pending kiger not found")

    if request.action == "approve":
        target_id = pending.reference_id or pending.id
        existing_result = await db.execute(
            select(DBKiger).where(DBKiger.id == target_id)
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            fields_to_update = pending.changed_fields
            if fields_to_update is None:
                existing.name = pending.name
                existing.bio = pending.bio
                existing.profile_image = pending.profile_image
                existing.position = pending.position
                existing.is_active = pending.is_active
                existing.social_media = pending.social_media
            else:
                for field in fields_to_update:
                    if field == "characters":
                        continue
                    setattr(existing, field, getattr(pending, field))
            existing.updated_at = datetime.utcnow()
        else:
            new_kiger = DBKiger(
                id=pending.id,
                name=pending.name,
                bio=pending.bio,
                profile_image=pending.profile_image,
                position=pending.position,
                is_active=pending.is_active,
                social_media=pending.social_media,
            )
            db.add(new_kiger)
            target_id = pending.id

        # 連帶審核通過自動建立的 PendingCharacter
        if pending.auto_created_characters:
            for pc_id in pending.auto_created_characters:
                pc_result = await db.execute(
                    select(PendingCharacter).where(
                        PendingCharacter.id == pc_id,
                        PendingCharacter.status == "pending",
                    )
                )
                pc = pc_result.scalar_one_or_none()
                if not pc:
                    continue

                existing_char = await db.execute(
                    select(DBCharacter).where(
                        DBCharacter.original_name == pc.original_name
                    )
                )
                if not existing_char.scalar_one_or_none():
                    new_char = DBCharacter(
                        original_name=pc.original_name,
                        name=pc.name,
                        type=pc.type,
                        official_image=pc.official_image,
                        source=pc.source,
                    )
                    db.add(new_char)
                pc.status = "approved"
                pc.reviewed_at = datetime.utcnow()
            invalidate_cache_by_prefix("character:")
            delete_cache("all_characters")
            await db.flush()

        should_update_characters = pending.changed_fields is None or "characters" in (
            pending.changed_fields or []
        )
        if pending.characters and should_update_characters:
            await db.execute(
                delete(KigerCharacter).where(KigerCharacter.kiger_id == target_id)
            )
            for char_ref in pending.characters:
                char_id = char_ref.get("characterId")
                char_result = await db.execute(
                    select(DBCharacter).where(DBCharacter.id == int(char_id))
                )
                db_char = char_result.scalar_one_or_none()
                if not db_char:
                    char_data = char_ref.get("characterData", {})
                    if char_data:
                        char_result2 = await db.execute(
                            select(DBCharacter).where(
                                DBCharacter.original_name
                                == char_data.get("originalName", str(char_id))
                            )
                        )
                        db_char = char_result2.scalar_one_or_none()
                if not db_char:
                    continue
                kiger_char = KigerCharacter(
                    kiger_id=target_id,
                    character_id=db_char.id,
                    maker=char_ref.get("maker"),
                    images=char_ref.get("images", []),
                )
                db.add(kiger_char)

        pending.status = "approved"
        pending.reviewed_at = datetime.utcnow()
        invalidate_cache_by_prefix("kiger:")
        delete_cache("all_kigers")

        await db.commit()

        return ReviewResponse(
            message=f"Kiger {kiger_id} approved and published", status="approved"
        )

    elif request.action == "reject":
        pending.status = "rejected"
        pending.reviewed_at = datetime.utcnow()
        await db.commit()

        return ReviewResponse(message=f"Kiger {kiger_id} rejected", status="rejected")

    else:
        raise HTTPException(status_code=400, detail="Invalid action")


@app.post(
    "/admin/review/character/{character_id}",
    response_model=ReviewResponse,
    dependencies=[Depends(get_current_admin)],
)
async def review_character(
    character_id: int, request: ReviewRequest, db: AsyncSession = Depends(get_db)
):
    """審核 Character 資料"""
    result = await db.execute(
        select(PendingCharacter).where(PendingCharacter.id == character_id)
    )
    pending = result.scalar_one_or_none()

    if not pending:
        raise HTTPException(status_code=404, detail="Pending character not found")

    if request.action == "approve":
        existing_result = await db.execute(
            select(DBCharacter).where(
                DBCharacter.original_name == pending.original_name
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            if pending.changed_fields is None:
                existing.name = pending.name
                existing.type = pending.type
                existing.official_image = pending.official_image
                existing.source = pending.source
            else:
                for field in pending.changed_fields:
                    setattr(existing, field, getattr(pending, field))
            existing.updated_at = datetime.utcnow()
        else:
            new_character = DBCharacter(
                original_name=pending.original_name,
                name=pending.name,
                type=pending.type,
                official_image=pending.official_image,
                source=pending.source,
            )
            db.add(new_character)
        pending.status = "approved"
        pending.reviewed_at = datetime.utcnow()
        invalidate_cache_by_prefix("character:")
        delete_cache("all_characters")

        await db.commit()

        return ReviewResponse(
            message=f"Character {character_id} approved and published",
            status="approved",
        )

    elif request.action == "reject":
        pending.status = "rejected"
        pending.reviewed_at = datetime.utcnow()
        await db.commit()

        return ReviewResponse(
            message=f"Character {character_id} rejected", status="rejected"
        )

    else:
        raise HTTPException(status_code=400, detail="Invalid action")


@app.post(
    "/admin/review/maker/{maker_id}",
    response_model=ReviewResponse,
    dependencies=[Depends(get_current_admin)],
)
async def review_maker(
    maker_id: int, request: ReviewRequest, db: AsyncSession = Depends(get_db)
):
    """審核 Maker 資料"""
    result = await db.execute(select(PendingMaker).where(PendingMaker.id == maker_id))
    pending = result.scalar_one_or_none()

    if not pending:
        raise HTTPException(status_code=404, detail="Pending maker not found")

    if request.action == "approve":
        existing_result = await db.execute(
            select(DBMaker).where(DBMaker.original_name == pending.original_name)
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            if pending.changed_fields is None:
                existing.name = pending.name
                existing.avatar = pending.avatar
                existing.social_media = pending.social_media
            else:
                for field in pending.changed_fields:
                    setattr(existing, field, getattr(pending, field))
            existing.updated_at = datetime.utcnow()
        else:
            new_maker = DBMaker(
                original_name=pending.original_name,
                name=pending.name,
                avatar=pending.avatar,
                social_media=pending.social_media,
            )
            db.add(new_maker)

        # 更新待審核狀態
        pending.status = "approved"
        pending.reviewed_at = datetime.utcnow()

        # 清除相關快取
        invalidate_cache_by_prefix("maker:")
        delete_cache("all_makers")

        await db.commit()

        return ReviewResponse(
            message=f"Maker {maker_id} approved and published", status="approved"
        )

    elif request.action == "reject":
        pending.status = "rejected"
        pending.reviewed_at = datetime.utcnow()
        await db.commit()

        return ReviewResponse(message=f"Maker {maker_id} rejected", status="rejected")

    else:
        raise HTTPException(status_code=400, detail="Invalid action")


@app.put(
    "/admin/kiger/{kiger_id}",
    response_model=KigerDetailResponse,
    dependencies=[Depends(get_current_admin)],
)
async def update_kiger(
    kiger_id: str, kiger_data: Kiger, db: AsyncSession = Depends(get_db)
):
    """管理員直接修改 Kiger 資料"""
    try:
        result = await db.execute(select(DBKiger).where(DBKiger.id == kiger_id))
        existing_kiger = result.scalar_one_or_none()

        if not existing_kiger:
            raise HTTPException(status_code=404, detail="Kiger not found")

        kiger_dict = kiger_data.model_dump()

        existing_kiger.name = kiger_dict["name"]
        existing_kiger.bio = kiger_dict["bio"]
        existing_kiger.profile_image = kiger_dict.get("profileImage", "")
        existing_kiger.position = kiger_dict.get("position", "")
        existing_kiger.is_active = kiger_dict.get("isActive", True)
        existing_kiger.social_media = kiger_dict.get("socialMedia", {})
        existing_kiger.updated_at = datetime.utcnow()

        if "Characters" in kiger_dict and kiger_dict["Characters"]:
            await db.execute(
                delete(KigerCharacter).where(KigerCharacter.kiger_id == kiger_id)
            )
            for char_ref in kiger_dict["Characters"]:
                kiger_char = KigerCharacter(
                    kiger_id=kiger_id,
                    character_id=char_ref.get("characterId"),
                    maker=char_ref.get("maker"),
                    images=char_ref.get("images", []),
                )
                db.add(kiger_char)

        invalidate_cache_by_prefix("kiger:")
        delete_cache("all_kigers")

        await db.commit()

        characters_result = await db.execute(
            select(KigerCharacter).where(KigerCharacter.kiger_id == kiger_id)
        )
        kiger_characters = characters_result.scalars().all()

        characters_list = [
            CharacterReferenceResponse(
                characterId=kc.character_id,
                maker=kc.maker,
                images=kc.images or [],
            )
            for kc in kiger_characters
        ]

        return KigerDetailResponse(
            id=existing_kiger.id,
            name=existing_kiger.name,
            bio=existing_kiger.bio,
            profileImage=existing_kiger.profile_image,
            position=existing_kiger.position,
            isActive=existing_kiger.is_active,
            socialMedia=existing_kiger.social_media,
            Characters=characters_list,
            createdAt=existing_kiger.created_at.isoformat() + "Z"
            if existing_kiger.created_at
            else None,
            updatedAt=existing_kiger.updated_at.isoformat() + "Z"
            if existing_kiger.updated_at
            else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update kiger: {str(e)}")


@app.put(
    "/admin/character/{character_id}",
    response_model=CharacterResponse,
    dependencies=[Depends(get_current_admin)],
)
async def update_character(
    character_id: int, character_data: Character, db: AsyncSession = Depends(get_db)
):
    """管理員直接修改 Character 資料"""
    try:
        result = await db.execute(
            select(DBCharacter).where(DBCharacter.id == character_id)
        )
        existing_character = result.scalar_one_or_none()

        if not existing_character:
            raise HTTPException(status_code=404, detail="Character not found")

        character_dict = character_data.model_dump()

        existing_character.name = character_dict["name"]
        existing_character.original_name = character_dict["originalName"]
        existing_character.type = character_dict["type"]
        existing_character.official_image = character_dict.get("officialImage", "")
        existing_character.source = character_dict.get("source")
        existing_character.updated_at = datetime.utcnow()

        invalidate_cache_by_prefix("character:")
        delete_cache("all_characters")

        await db.commit()

        return CharacterResponse(
            id=existing_character.id,
            name=existing_character.name,
            originalName=existing_character.original_name,
            type=existing_character.type,
            officialImage=existing_character.official_image,
            source=existing_character.source,
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update character: {str(e)}"
        )


@app.put(
    "/admin/maker/{maker_id}",
    response_model=MakerResponse,
    dependencies=[Depends(get_current_admin)],
)
async def update_maker(
    maker_id: int, maker_data: Maker, db: AsyncSession = Depends(get_db)
):
    """管理員直接修改 Maker 資料"""
    try:
        result = await db.execute(select(DBMaker).where(DBMaker.id == maker_id))
        existing_maker = result.scalar_one_or_none()

        if not existing_maker:
            raise HTTPException(status_code=404, detail="Maker not found")

        maker_dict = maker_data.model_dump()

        existing_maker.name = maker_dict["name"]
        existing_maker.original_name = maker_dict["originalName"]
        existing_maker.avatar = maker_dict.get("Avatar", "")
        existing_maker.social_media = maker_dict.get("socialMedia")
        existing_maker.updated_at = datetime.utcnow()

        invalidate_cache_by_prefix("maker:")
        delete_cache("all_makers")

        await db.commit()

        return MakerResponse(
            id=existing_maker.id,
            name=existing_maker.name,
            originalName=existing_maker.original_name,
            Avatar=existing_maker.avatar,
            socialMedia=existing_maker.social_media,
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update maker: {str(e)}")


@app.post("/debug/clear_cache", dependencies=[Depends(get_current_admin)])
async def clear_cache():
    try:
        delete_cache("all_characters")
        delete_cache("all_kigers")
        delete_cache("all_makers")
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")
