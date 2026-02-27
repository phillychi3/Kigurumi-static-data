from datetime import datetime

from api.database import PendingCharacter, PendingKiger, PendingMaker


async def test_get_pending_kigers_empty(admin_client):
    response = await admin_client.get("/admin/pending/kigers")
    assert response.status_code == 200
    assert response.json() == []


async def test_get_pending_kigers_with_data(admin_client, db_session):
    pk = PendingKiger(
        id="pending-kiger-1",
        name="Pending Kiger",
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

    response = await admin_client.get("/admin/pending/kigers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "pending-kiger-1"
    assert data[0]["status"] == "pending"


async def test_get_pending_kigers_excludes_non_pending(admin_client, db_session):
    pk_pending = PendingKiger(
        id="pk-pending",
        name="Pending",
        bio="",
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    pk_approved = PendingKiger(
        id="pk-approved",
        name="Approved",
        bio="",
        status="approved",
        submitted_at=datetime.utcnow(),
    )
    db_session.add_all([pk_pending, pk_approved])
    await db_session.commit()

    response = await admin_client.get("/admin/pending/kigers")
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "pk-pending"


async def test_get_pending_characters_empty(admin_client):
    response = await admin_client.get("/admin/pending/characters")
    assert response.status_code == 200
    assert response.json() == []


async def test_get_pending_characters_with_data(admin_client, db_session):
    pc = PendingCharacter(
        original_name="PendingChar",
        name="Pending Character",
        type="game",
        official_image="https://example.com/char.png",
        source={"title": "Game", "company": "Co", "releaseYear": 2024},
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    db_session.add(pc)
    await db_session.commit()

    response = await admin_client.get("/admin/pending/characters")
    data = response.json()
    assert len(data) == 1
    assert data[0]["originalName"] == "PendingChar"
    assert data[0]["status"] == "pending"


async def test_get_pending_makers_empty(admin_client):
    response = await admin_client.get("/admin/pending/makers")
    assert response.status_code == 200
    assert response.json() == []


async def test_get_pending_makers_with_data(admin_client, db_session):
    pm = PendingMaker(
        original_name="PendingMaker",
        name="Pending Maker",
        avatar="https://example.com/avatar.png",
        social_media={"twitter": "test"},
        status="pending",
        submitted_at=datetime.utcnow(),
    )
    db_session.add(pm)
    await db_session.commit()

    response = await admin_client.get("/admin/pending/makers")
    data = response.json()
    assert len(data) == 1
    assert data[0]["originalName"] == "PendingMaker"
    assert data[0]["status"] == "pending"
