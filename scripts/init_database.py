import asyncio
import json
import os
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).parent.parent))

from api.database import init_db, async_session_maker, Admin, Maker as DBMaker, engine
from api.auth import get_password_hash


async def migrate_makers_from_json():
    json_path = Path(__file__).parent.parent / "data" / "maker.json"

    if not json_path.exists():
        print(f"警告：找不到 {json_path}，跳過 Maker 資料遷移")
        return

    print(f"開始從 {json_path} 匯入 Maker 資料...")

    with open(json_path, "r", encoding="utf-8") as f:
        makers_data = json.load(f)

    if not isinstance(makers_data, dict):
        print("錯誤：maker.json 格式不正確")
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
            print(f"✓ 成功匯入 {count} 筆 Maker 資料")

        if skipped > 0:
            print(f"⊘ 跳過 {skipped} 筆已存在的 Maker 資料")


async def create_admin_user(username: str, password: str):
    from sqlalchemy import select

    async with async_session_maker() as session:
        result = await session.execute(select(Admin).where(Admin.username == username))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"⊘ 管理員 {username} 已存在，跳過建立")
            return

        admin = Admin(
            username=username,
            hashed_password=get_password_hash(password),
        )
        session.add(admin)
        await session.commit()
        print(f"✓ 成功建立管理員帳號：{username}")


async def main():
    print("=" * 60)
    print("Kigurumi 資料庫初始化與遷移")
    print("=" * 60)

    print("\n[1/3] 建立資料表...")
    await init_db()
    print("✓ 資料表建立完成")

    print("\n[2/3] 匯入現有資料...")
    await migrate_makers_from_json()

    print("\n[3/3] 建立管理員帳號...")

    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

    print(f"使用者名稱：{admin_username}")
    print(f"密碼：{'*' * len(admin_password)}")

    await create_admin_user(admin_username, admin_password)

    print("\n" + "=" * 60)
    print("✓ 資料庫初始化完成！")
    print("=" * 60)
    print("\n重要提醒：")
    print("1. 請在 .env 檔案中設定 DATABASE_URL")
    print(
        "   範例：DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/kigurumi_db"
    )
    print("2. 請修改預設管理員密碼（使用環境變數 ADMIN_PASSWORD）")
    print("3. 請設定 JWT_SECRET_KEY 為隨機字串")
    print("   範例：JWT_SECRET_KEY=your-secret-key-change-this")
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
