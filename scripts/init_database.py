import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from api.auth import get_password_hash
from api.database import Admin
from api.database import Character as DBCharacter
from api.database import Kiger as DBKiger
from api.database import KigerCharacter
from api.database import Maker as DBMaker
from api.database import Source as DBSource
from api.database import async_session_maker, engine, init_db


async def migrate_makers_from_json():
    json_path = Path(__file__).parent.parent / "data" / "maker.json"

    if not json_path.exists():
        print(f"找不到 {json_path}，跳過 Maker 資料遷移")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        makers_data = json.load(f)

    if not isinstance(makers_data, dict):
        print("maker.json 格式不正確")
        return

    async with async_session_maker() as session:
        from sqlalchemy import select

        count = 0
        skipped = 0

        for original_name, maker_dict in makers_data.items():
            result = await session.execute(
                select(DBMaker).where(DBMaker.original_name == original_name)
            )
            existing = result.scalar_one_or_none()

            if existing:
                skipped += 1
                continue
            maker = DBMaker(
                original_name=original_name,
                name=maker_dict.get("name", original_name),
                avatar=maker_dict.get("Avatar", ""),
                social_media=maker_dict.get("socialMedia", {}),
            )
            session.add(maker)
            count += 1

        if count > 0:
            await session.commit()
            print(f"成功匯入 {count} 筆 Maker 資料")

        if skipped > 0:
            print(f"跳過 {skipped} 筆已存在的 Maker 資料")


async def migrate_characters_from_json():
    json_path = Path(__file__).parent.parent / "data" / "character.json"

    if not json_path.exists():
        print(f"找不到 {json_path}，跳過 Character 資料遷移")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        characters_data = json.load(f)

    if not isinstance(characters_data, dict):
        print("character.json 格式不正確")
        return

    async with async_session_maker() as session:
        from sqlalchemy import select

        count = 0
        skipped = 0

        for original_name, character_dict in characters_data.items():
            result = await session.execute(
                select(DBCharacter).where(DBCharacter.original_name == original_name)
            )
            existing = result.scalar_one_or_none()

            if existing:
                skipped += 1
                continue

            source_dict = character_dict.get("source")
            source_id = None
            if source_dict:
                title = source_dict.get("title", "")
                company = source_dict.get("company", "")
                release_year = source_dict.get("releaseYear", 0)
                source_result = await session.execute(
                    select(DBSource).where(
                        DBSource.title == title, DBSource.company == company
                    )
                )
                source_obj = source_result.scalar_one_or_none()
                if not source_obj:
                    source_obj = DBSource(
                        title=title, company=company, release_year=release_year
                    )
                    session.add(source_obj)
                    await session.flush()
                source_id = source_obj.id

            character = DBCharacter(
                original_name=original_name,
                name=character_dict.get("name", original_name),
                type=character_dict.get("type", ""),
                official_image=character_dict.get("officialImage", ""),
                source_id=source_id,
            )
            session.add(character)
            count += 1

        if count > 0:
            await session.commit()
            print(f"成功匯入 {count} 筆 Character 資料")

        if skipped > 0:
            print(f"跳過 {skipped} 筆已存在的 Character 資料")


async def migrate_kigers_from_json():
    json_path = Path(__file__).parent.parent / "data" / "kiger.json"

    if not json_path.exists():
        print(f"找不到 {json_path}，跳過 Kiger 資料遷移")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        kigers_data = json.load(f)

    if not isinstance(kigers_data, dict):
        print("kiger.json 格式不正確")
        return

    async with async_session_maker() as session:
        from sqlalchemy import select

        count = 0
        skipped = 0

        for kiger_id, kiger_dict in kigers_data.items():
            result = await session.execute(
                select(DBKiger).where(DBKiger.id == kiger_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                skipped += 1
                continue

            kiger = DBKiger(
                id=kiger_id,
                name=kiger_dict.get("name", kiger_id),
                bio=kiger_dict.get("bio", ""),
                profile_image=kiger_dict.get("profileImage", ""),
                position=kiger_dict.get("position", ""),
                is_active=kiger_dict.get("isActive", True),
                social_media=kiger_dict.get("socialMedia", {}),
            )
            session.add(kiger)

            # 處理 Kiger 的 Character 關聯
            characters = kiger_dict.get("Characters", [])
            for char_ref in characters:
                kiger_char = KigerCharacter(
                    kiger_id=kiger_id,
                    character_id=char_ref.get("characterId"),
                    maker=char_ref.get("maker"),
                    images=char_ref.get("images", []),
                )
                session.add(kiger_char)

            count += 1

        if count > 0:
            await session.commit()
            print(f"成功匯入 {count} 筆 Kiger 資料")

        if skipped > 0:
            print(f"跳過 {skipped} 筆已存在的 Kiger 資料")


async def create_admin_user(username: str, password: str):
    from sqlalchemy import select

    async with async_session_maker() as session:
        result = await session.execute(select(Admin).where(Admin.username == username))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"管理員 {username} 已存在，跳過建立")
            return

        admin = Admin(
            username=username,
            hashed_password=get_password_hash(password),
        )
        session.add(admin)
        await session.commit()
        print(f"成功建立管理員帳號：{username}")


async def main():
    await init_db()
    await migrate_characters_from_json()
    await migrate_makers_from_json()
    await migrate_kigers_from_json()
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    await create_admin_user(admin_username, admin_password)
    print("初始化完成")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
