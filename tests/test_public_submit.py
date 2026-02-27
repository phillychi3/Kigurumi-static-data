from api.database import Character as DBCharacter
from api.database import Maker as DBMaker


VALID_KIGER_PAYLOAD = {
    "name": "TestKiger",
    "bio": "A test kiger",
    "profileImage": "https://example.com/profile.png",
    "position": "cosplayer",
    "isActive": True,
    "socialMedia": {"twitter": "https://twitter.com/test"},
    "Characters": [],
}

VALID_CHARACTER_PAYLOAD = {
    "name": "Test Character",
    "originalName": "TestCharOriginal",
    "type": "game",
    "officialImage": "https://example.com/char.png",
    "source": {"title": "Test Game", "company": "TestCo", "releaseYear": 2024},
}

VALID_MAKER_PAYLOAD = {
    "name": "Test Maker",
    "originalName": "TestMakerOriginal",
    "Avatar": "https://example.com/avatar.png",
    "socialMedia": {"twitter": "https://twitter.com/maker"},
}


async def test_submit_kiger_new(client):
    response = await client.post("/kiger", json=VALID_KIGER_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["id"]


async def test_submit_kiger_with_reference_id(client, db_session):
    from api.database import Kiger as DBKiger

    existing = DBKiger(
        id="existing-kiger",
        name="Original Name",
        bio="Original Bio",
        profile_image="https://example.com/old.png",
        is_active=True,
    )
    db_session.add(existing)
    await db_session.commit()

    payload = {
        **VALID_KIGER_PAYLOAD,
        "referenceId": "existing-kiger",
        "name": "Updated Name",
    }
    response = await client.post("/kiger", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"


async def test_submit_kiger_auto_creates_pending_character(client):
    payload = {
        **VALID_KIGER_PAYLOAD,
        "Characters": [
            {
                "characterId": "99999",
                "images": ["https://example.com/img.png"],
                "characterData": {
                    "name": "New Char",
                    "originalName": "NewCharOriginal",
                    "type": "anime",
                    "officialImage": "https://example.com/new.png",
                    "source": {
                        "title": "Anime",
                        "company": "Studio",
                        "releaseYear": 2024,
                    },
                },
            }
        ],
    }
    response = await client.post("/kiger", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


async def test_submit_character_new(client):
    response = await client.post("/character", json=VALID_CHARACTER_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["id"]


async def test_submit_character_existing_tracks_changes(client, db_session):
    existing = DBCharacter(
        original_name="TestCharOriginal",
        name="Old Name",
        type="game",
        official_image="https://example.com/old.png",
        source={"title": "Test Game", "company": "TestCo", "releaseYear": 2024},
    )
    db_session.add(existing)
    await db_session.commit()

    payload = {**VALID_CHARACTER_PAYLOAD, "name": "New Name"}
    response = await client.post("/character", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


async def test_submit_maker_new(client):
    response = await client.post("/maker", json=VALID_MAKER_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["id"]


async def test_submit_maker_existing_tracks_changes(client, db_session):
    existing = DBMaker(
        original_name="TestMakerOriginal",
        name="Old Maker",
        avatar="https://example.com/old.png",
        social_media={"twitter": "https://twitter.com/old"},
    )
    db_session.add(existing)
    await db_session.commit()

    payload = {**VALID_MAKER_PAYLOAD, "name": "New Maker Name"}
    response = await client.post("/maker", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


async def test_submit_character_invalid_data(client):
    response = await client.post("/character", json={"name": "Missing fields"})
    assert response.status_code == 422
