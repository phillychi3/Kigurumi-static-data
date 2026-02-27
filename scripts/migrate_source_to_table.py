"""
遷移腳本：將 characters.source JSON 欄位獨立為 sources 資料表

適用於已有資料的現有資料庫。全新環境請直接執行 init_database.py。

執行步驟：
1. 建立 sources 資料表（含 UNIQUE KEY on (title, company)）
2. 在 characters 資料表新增 source_id 欄位
3. 讀取每筆 character 的舊 JSON source，查找或建立 sources 紀錄，回填 source_id
4. 移除 characters 的舊 source JSON 欄位
"""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text

from api.database import async_session_maker, engine, init_db


async def migrate():
    # 建立 sources 資料表（init_db 會處理，確保存在）
    await init_db()
    print("✓ sources 資料表已建立（或已存在）")

    async with engine.begin() as conn:
        # 檢查 characters 資料表是否已有 source_id 欄位
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() "
                "AND table_name = 'characters' "
                "AND column_name = 'source_id'"
            )
        )
        has_source_id = (result.scalar() or 0) > 0

        if not has_source_id:
            await conn.execute(
                text(
                    "ALTER TABLE characters "
                    "ADD COLUMN source_id INT NULL, "
                    "ADD CONSTRAINT fk_characters_source_id "
                    "FOREIGN KEY (source_id) REFERENCES sources(id)"
                )
            )
            print("✓ characters.source_id 欄位已新增")
        else:
            print("✓ characters.source_id 欄位已存在，跳過")

        # 檢查 characters 資料表是否還有舊的 source JSON 欄位
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() "
                "AND table_name = 'characters' "
                "AND column_name = 'source'"
            )
        )
        has_old_source = (result.scalar() or 0) > 0

        if not has_old_source:
            print("✓ 舊的 characters.source JSON 欄位不存在，無需遷移資料")
            return

    # 遷移資料：讀取舊 source JSON，建立 sources 紀錄，回填 source_id
    async with async_session_maker() as session:
        from sqlalchemy import select

        from api.database import Source as DBSource

        result = await session.execute(
            text("SELECT id, source FROM characters WHERE source IS NOT NULL")
        )
        rows = result.fetchall()

        updated = 0
        skipped = 0

        for row in rows:
            char_id = row[0]
            source_data = row[1]

            if not source_data:
                skipped += 1
                continue

            # source_data 從 MySQL JSON 欄位讀出為 dict
            if isinstance(source_data, str):
                import json

                source_data = json.loads(source_data)

            title = source_data.get("title", "")
            company = source_data.get("company", "")
            release_year = source_data.get("releaseYear", 0)

            if not title and not company:
                skipped += 1
                continue

            # 查找或建立 source
            src_result = await session.execute(
                select(DBSource).where(
                    DBSource.title == title, DBSource.company == company
                )
            )
            source_obj = src_result.scalar_one_or_none()
            if not source_obj:
                source_obj = DBSource(
                    title=title, company=company, release_year=release_year
                )
                session.add(source_obj)
                await session.flush()

            # 更新 character.source_id
            await session.execute(
                text("UPDATE characters SET source_id = :sid WHERE id = :cid"),
                {"sid": source_obj.id, "cid": char_id},
            )
            updated += 1

        await session.commit()
        print(f"✓ 已回填 {updated} 筆 character.source_id（跳過 {skipped} 筆）")

    # 移除舊的 source JSON 欄位
    async with engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE characters DROP FOREIGN KEY fk_characters_source_id")
        )
        await conn.execute(text("ALTER TABLE characters DROP COLUMN source"))
        # 重新加回 FK（DROP COLUMN 不影響 source_id，但先移除再加回確保乾淨）
        await conn.execute(
            text(
                "ALTER TABLE characters "
                "ADD CONSTRAINT fk_characters_source_id "
                "FOREIGN KEY (source_id) REFERENCES sources(id)"
            )
        )
        print("✓ 舊的 characters.source JSON 欄位已移除")

    print("\n遷移完成！")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
