from datetime import datetime

from sqlalchemy import select

from api.database import Character as DBCharacter
from api.database import Kiger as DBKiger
from api.database import Maker as DBMaker
from api.database import PendingCharacter, PendingKiger, PendingMaker
from api.database import Source as DBSource


async def test_review_kiger_approve_new(admin_client, db_session):
    pk = PendingKiger(
        id="new-kiger-1",
        name="New Kiger",
        bio="Bio",
        profile_image="https://example.com/img.png",
        position="cosplayer",
        is_active=True,
        social_media={"twitter": "test"},
        characters=[],
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    db_session.add(pk)
    await db_session.commit()

    response = await admin_client.post(
        "/admin/review/kiger/new-kiger-1", json={"action": "approve"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    result = await db_session.execute(
        select(DBKiger).where(DBKiger.id == "new-kiger-1")
    )
    kiger = result.scalar_one_or_none()
    assert kiger is not None
    assert kiger.name == "New Kiger"


async def test_review_kiger_approve_update_existing(admin_client, db_session):
    existing = DBKiger(
        id="existing-kiger",
        name="Old Name",
        bio="Old Bio",
        is_active=True,
    )
    db_session.add(existing)
    await db_session.flush()

    pk = PendingKiger(
        id="update-kiger-1",
        reference_id="existing-kiger",
        name="Updated Name",
        bio="Updated Bio",
        profile_image="https://example.com/new.png",
        position="performer",
        is_active=True,
        social_media=None,
        characters=[],
        changed_fields=None,
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    db_session.add(pk)
    await db_session.commit()

    response = await admin_client.post(
        "/admin/review/kiger/update-kiger-1", json={"action": "approve"}
    )
    assert response.status_code == 200

    await db_session.refresh(existing)
    assert existing.name == "Updated Name"
    assert existing.bio == "Updated Bio"


async def test_review_kiger_reject(admin_client, db_session):
    pk = PendingKiger(
        id="reject-kiger",
        name="To Reject",
        bio="",
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    db_session.add(pk)
    await db_session.commit()

    response = await admin_client.post(
        "/admin/review/kiger/reject-kiger", json={"action": "reject"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    result = await db_session.execute(
        select(DBKiger).where(DBKiger.id == "reject-kiger")
    )
    assert result.scalar_one_or_none() is None


async def test_review_kiger_not_found(admin_client):
    response = await admin_client.post(
        "/admin/review/kiger/nonexistent", json={"action": "approve"}
    )
    assert response.status_code == 404


async def test_review_kiger_invalid_action(admin_client, db_session):
    pk = PendingKiger(
        id="invalid-action-kiger",
        name="Test",
        bio="",
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    db_session.add(pk)
    await db_session.commit()

    response = await admin_client.post(
        "/admin/review/kiger/invalid-action-kiger", json={"action": "invalid"}
    )
    assert response.status_code == 400


async def test_review_character_approve_new(admin_client, db_session):
    pc = PendingCharacter(
        original_name="NewChar",
        name="New Character",
        type="anime",
        official_image="https://example.com/char.png",
        source={"title": "Anime", "company": "Studio", "releaseYear": 2024},
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    db_session.add(pc)
    await db_session.commit()

    response = await admin_client.post(
        f"/admin/review/character/{pc.id}", json={"action": "approve"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    result = await db_session.execute(
        select(DBCharacter).where(DBCharacter.original_name == "NewChar")
    )
    char = result.scalar_one_or_none()
    assert char is not None
    assert char.name == "New Character"
    assert char.source_id is not None

    source_result = await db_session.execute(
        select(DBSource).where(DBSource.id == char.source_id)
    )
    source = source_result.scalar_one_or_none()
    assert source is not None
    assert source.title == "Anime"
    assert source.company == "Studio"
    assert source.release_year == 2024


async def test_review_character_approve_no_source_leaves_source_id_null(
    admin_client, db_session
):
    pc = PendingCharacter(
        original_name="NoSourceChar",
        name="No Source",
        type="other",
        source=None,
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    db_session.add(pc)
    await db_session.commit()

    response = await admin_client.post(
        f"/admin/review/character/{pc.id}", json={"action": "approve"}
    )
    assert response.status_code == 200

    char_result = await db_session.execute(
        select(DBCharacter).where(DBCharacter.original_name == "NoSourceChar")
    )
    char = char_result.scalar_one_or_none()
    assert char is not None
    assert char.source_id is None


async def test_review_character_approve_deduplicates_source(admin_client, db_session):
    shared_source = {"title": "SharedGame", "company": "SharedCo", "releaseYear": 2022}
    pc1 = PendingCharacter(
        original_name="CharDedup1",
        name="Char Dedup 1",
        type="game",
        source=shared_source,
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    pc2 = PendingCharacter(
        original_name="CharDedup2",
        name="Char Dedup 2",
        type="game",
        source=shared_source,
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    db_session.add_all([pc1, pc2])
    await db_session.commit()

    await admin_client.post(
        f"/admin/review/character/{pc1.id}", json={"action": "approve"}
    )
    await admin_client.post(
        f"/admin/review/character/{pc2.id}", json={"action": "approve"}
    )

    source_result = await db_session.execute(
        select(DBSource).where(
            DBSource.title == "SharedGame", DBSource.company == "SharedCo"
        )
    )
    sources = source_result.scalars().all()
    assert len(sources) == 1, "same source should be deduplicated to one record"

    char_result = await db_session.execute(
        select(DBCharacter).where(
            DBCharacter.original_name.in_(["CharDedup1", "CharDedup2"])
        )
    )
    chars = char_result.scalars().all()
    assert all(c.source_id == sources[0].id for c in chars)


async def test_review_character_approve_update_existing(admin_client, db_session):
    existing = DBCharacter(
        original_name="ExistingChar",
        name="Old Name",
        type="game",
    )
    db_session.add(existing)
    await db_session.flush()

    pc = PendingCharacter(
        original_name="ExistingChar",
        name="Updated Name",
        type="game",
        changed_fields=None,
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    db_session.add(pc)
    await db_session.commit()

    response = await admin_client.post(
        f"/admin/review/character/{pc.id}", json={"action": "approve"}
    )
    assert response.status_code == 200

    await db_session.refresh(existing)
    assert existing.name == "Updated Name"


async def test_review_character_reject(admin_client, db_session):
    pc = PendingCharacter(
        original_name="RejectChar",
        name="To Reject",
        type="anime",
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    db_session.add(pc)
    await db_session.commit()

    response = await admin_client.post(
        f"/admin/review/character/{pc.id}", json={"action": "reject"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    result = await db_session.execute(
        select(DBCharacter).where(DBCharacter.original_name == "RejectChar")
    )
    assert result.scalar_one_or_none() is None


async def test_review_character_not_found(admin_client):
    response = await admin_client.post(
        "/admin/review/character/99999", json={"action": "approve"}
    )
    assert response.status_code == 404


async def test_review_maker_approve_new(admin_client, db_session):
    pm = PendingMaker(
        original_name="NewMaker",
        name="New Maker",
        avatar="https://example.com/avatar.png",
        social_media={"twitter": "test"},
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    db_session.add(pm)
    await db_session.commit()

    response = await admin_client.post(
        f"/admin/review/maker/{pm.id}", json={"action": "approve"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    result = await db_session.execute(
        select(DBMaker).where(DBMaker.original_name == "NewMaker")
    )
    maker = result.scalar_one_or_none()
    assert maker is not None
    assert maker.name == "New Maker"


async def test_review_maker_approve_update_existing(admin_client, db_session):
    existing = DBMaker(
        original_name="ExistingMaker",
        name="Old Maker",
    )
    db_session.add(existing)
    await db_session.flush()

    pm = PendingMaker(
        original_name="ExistingMaker",
        name="Updated Maker",
        avatar="https://example.com/new.png",
        changed_fields=None,
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    db_session.add(pm)
    await db_session.commit()

    response = await admin_client.post(
        f"/admin/review/maker/{pm.id}", json={"action": "approve"}
    )
    assert response.status_code == 200

    await db_session.refresh(existing)
    assert existing.name == "Updated Maker"


async def test_review_maker_reject(admin_client, db_session):
    pm = PendingMaker(
        original_name="RejectMaker",
        name="To Reject",
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    db_session.add(pm)
    await db_session.commit()

    response = await admin_client.post(
        f"/admin/review/maker/{pm.id}", json={"action": "reject"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


async def test_review_maker_not_found(admin_client):
    response = await admin_client.post(
        "/admin/review/maker/99999", json={"action": "approve"}
    )
    assert response.status_code == 404
