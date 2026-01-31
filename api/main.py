from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from contextlib import asynccontextmanager
import sys
import os

from .models import (
    Kiger,
    Character,
    Maker,
    CrawlTwitterUserRequest,
    CrawlTwitterTweetRequest,
)
from .database import (
    get_db,
    init_db,
    PendingKiger,
    PendingCharacter,
    PendingMaker,
    Kiger as DBKiger,
    Character as DBCharacter,
    Maker as DBMaker,
    KigerCharacter,
)
from .auth import (
    get_current_admin,
    authenticate_admin,
    create_access_token,
)
from .cache import (
    get_cache,
    set_cache,
    delete_cache,
    invalidate_cache_by_prefix,
)
from .schemas import (
    MessageResponse,
    SubmitResponse,
    KigerListItemResponse,
    KigerDetailResponse,
    CharacterReferenceResponse,
    CharacterResponse,
    MakerResponse,
    TwitterUserCrawlResponse,
    TwitterTweetCrawlResponse,
    LoginResponse,
    PendingKigerResponse,
    PendingCharacterResponse,
    PendingMakerResponse,
    ReviewResponse,
)

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from crawler import (
    fetch_twitter_user,
    fetch_twitter_tweet,
    parse_character_from_tweet,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Kigurumi Data API", version="2.0.0", lifespan=lifespan)


@app.get("/", response_model=MessageResponse)
async def root():
    return MessageResponse(message="Kigurumi Static Data API v2.0 - Database Edition")


@app.post("/crawl/twitter/user", response_model=TwitterUserCrawlResponse)
async def crawl_twitter_user(request: CrawlTwitterUserRequest):
    try:
        twitter_data = await fetch_twitter_user(request.username)

        user_id = request.username
        name = twitter_data.get("name", request.username)
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
                "twitter": f"https://twitter.com/{request.username}",
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
async def crawl_twitter_tweet(request: CrawlTwitterTweetRequest):
    try:
        tweet_data = await fetch_twitter_tweet(request.username, request.tweet_id)

        images = []
        if "media_extended" in tweet_data:
            for media in tweet_data["media_extended"]:
                if media.get("type") == "image":
                    images.append(media.get("url", ""))

        character = await parse_character_from_tweet(tweet_data)

        return TwitterTweetCrawlResponse(
            character=character,
            images=images,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze tweet: {str(e)}"
        )


@app.post("/kiger", response_model=SubmitResponse)
async def submit_kiger(kiger_data: Kiger, db: AsyncSession = Depends(get_db)):
    try:
        kiger_dict = kiger_data.model_dump()

        pending_kiger = PendingKiger(
            id=kiger_dict["id"],
            name=kiger_dict["name"],
            bio=kiger_dict["bio"],
            profile_image=kiger_dict.get("profileImage", ""),
            position=kiger_dict.get("position", ""),
            is_active=kiger_dict.get("isActive", True),
            social_media=kiger_dict.get("socialMedia", {}),
            characters=kiger_dict.get("Characters", []),
            status="pending",
            submitted_at=datetime.utcnow(),
        )

        result = await db.execute(
            select(PendingKiger).where(PendingKiger.id == kiger_dict["id"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = pending_kiger.name
            existing.bio = pending_kiger.bio
            existing.profile_image = pending_kiger.profile_image
            existing.position = pending_kiger.position
            existing.is_active = pending_kiger.is_active
            existing.social_media = pending_kiger.social_media
            existing.characters = pending_kiger.characters
            existing.status = "pending"
            existing.submitted_at = datetime.utcnow()
        else:
            db.add(pending_kiger)

        await db.commit()

        return SubmitResponse(
            message=f"Kiger {kiger_data.id} submitted for review",
            status="pending",
            id=kiger_data.id,
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

        pending_character = PendingCharacter(
            original_name=character_dict["originalName"],
            name=character_dict["name"],
            type=character_dict["type"],
            official_image=character_dict.get("officialImage", ""),
            source=character_dict.get("source", {})
            if character_dict.get("source")
            else None,
            status="pending",
            submitted_at=datetime.utcnow(),
        )

        result = await db.execute(
            select(PendingCharacter).where(
                PendingCharacter.original_name == character_dict["originalName"]
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = pending_character.name
            existing.type = pending_character.type
            existing.official_image = pending_character.official_image
            existing.source = pending_character.source
            existing.status = "pending"
            existing.submitted_at = datetime.utcnow()
        else:
            db.add(pending_character)

        await db.commit()

        return SubmitResponse(
            message=f"Character {character_data.name} submitted for review",
            status="pending",
            id=character_data.originalName,
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

        pending_maker = PendingMaker(
            original_name=maker_dict["originalName"],
            name=maker_dict["name"],
            avatar=maker_dict.get("Avatar", ""),
            social_media=maker_dict.get("socialMedia", {})
            if maker_dict.get("socialMedia")
            else None,
            status="pending",
            submitted_at=datetime.utcnow(),
        )

        result = await db.execute(
            select(PendingMaker).where(
                PendingMaker.original_name == maker_dict["originalName"]
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = pending_maker.name
            existing.avatar = pending_maker.avatar
            existing.social_media = pending_maker.social_media
            existing.status = "pending"
            existing.submitted_at = datetime.utcnow()
        else:
            db.add(pending_maker)

        await db.commit()

        return SubmitResponse(
            message=f"Maker {maker_data.name} submitted for review",
            status="pending",
            id=maker_data.originalName,
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
async def get_character(character_id: str, db: AsyncSession = Depends(get_db)):
    """取得單一 Character 資料"""
    cache_key = f"character:{character_id}"

    cached = get_cache(cache_key)
    if cached:
        return cached

    result = await db.execute(
        select(DBCharacter).where(DBCharacter.original_name == character_id)
    )
    character = result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    character_response = CharacterResponse(
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
async def get_maker(maker_id: str, db: AsyncSession = Depends(get_db)):
    cache_key = f"maker:{maker_id}"

    # 檢查快取
    cached = get_cache(cache_key)
    if cached:
        return cached

    result = await db.execute(select(DBMaker).where(DBMaker.original_name == maker_id))
    maker = result.scalar_one_or_none()

    if not maker:
        raise HTTPException(status_code=404, detail="Maker not found")

    maker_response = MakerResponse(
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
        select(PendingKiger).where(PendingKiger.status == "pending")
    )
    pending_kigers = result.scalars().all()

    return [
        PendingKigerResponse(
            id=pk.id,
            name=pk.name,
            bio=pk.bio,
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
        select(PendingCharacter).where(PendingCharacter.status == "pending")
    )
    pending_characters = result.scalars().all()

    return [
        PendingCharacterResponse(
            originalName=pc.original_name,
            name=pc.name,
            type=pc.type,
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
        select(PendingMaker).where(PendingMaker.status == "pending")
    )
    pending_makers = result.scalars().all()

    return [
        PendingMakerResponse(
            originalName=pm.original_name,
            name=pm.name,
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
        existing_result = await db.execute(
            select(DBKiger).where(DBKiger.id == kiger_id)
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.name = pending.name
            existing.bio = pending.bio
            existing.profile_image = pending.profile_image
            existing.position = pending.position
            existing.is_active = pending.is_active
            existing.social_media = pending.social_media
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

        if pending.characters:
            await db.execute(
                delete(KigerCharacter).where(KigerCharacter.kiger_id == kiger_id)
            )
            for char_ref in pending.characters:
                kiger_char = KigerCharacter(
                    kiger_id=kiger_id,
                    character_id=char_ref.get("characterId"),
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
    character_id: str, request: ReviewRequest, db: AsyncSession = Depends(get_db)
):
    """審核 Character 資料"""
    result = await db.execute(
        select(PendingCharacter).where(PendingCharacter.original_name == character_id)
    )
    pending = result.scalar_one_or_none()

    if not pending:
        raise HTTPException(status_code=404, detail="Pending character not found")

    if request.action == "approve":
        existing_result = await db.execute(
            select(DBCharacter).where(DBCharacter.original_name == character_id)
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.name = pending.name
            existing.type = pending.type
            existing.official_image = pending.official_image
            existing.source = pending.source
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
    maker_id: str, request: ReviewRequest, db: AsyncSession = Depends(get_db)
):
    """審核 Maker 資料"""
    # 查詢待審核資料
    result = await db.execute(
        select(PendingMaker).where(PendingMaker.original_name == maker_id)
    )
    pending = result.scalar_one_or_none()

    if not pending:
        raise HTTPException(status_code=404, detail="Pending maker not found")

    if request.action == "approve":
        existing_result = await db.execute(
            select(DBMaker).where(DBMaker.original_name == maker_id)
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.name = pending.name
            existing.avatar = pending.avatar
            existing.social_media = pending.social_media
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
