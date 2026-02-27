from api.database import Character as DBCharacter
from api.database import Kiger as DBKiger
from api.database import Maker as DBMaker


VALID_KIGER_PAYLOAD = {
    "name": "Updated Kiger",
    "bio": "Updated bio",
    "profileImage": "https://example.com/updated.png",
    "position": "performer",
    "isActive": True,
    "socialMedia": {"twitter": "https://twitter.com/updated"},
    "Characters": [],
}

VALID_CHARACTER_PAYLOAD = {
    "name": "Updated Character",
    "originalName": "UpdatedCharOriginal",
    "type": "anime",
    "officialImage": "https://example.com/updated.png",
    "source": {"title": "Updated Game", "company": "UpdatedCo", "releaseYear": 2025},
}

VALID_MAKER_PAYLOAD = {
    "name": "Updated Maker",
    "originalName": "UpdatedMakerOriginal",
    "Avatar": "https://example.com/updated.png",
    "socialMedia": {"twitter": "https://twitter.com/updated"},
}


# --- Kiger Update ---


async def test_update_kiger_success(admin_client, db_session):
    kiger = DBKiger(
        id="update-kiger",
        name="Old Name",
        bio="Old Bio",
        is_active=True,
    )
    db_session.add(kiger)
    await db_session.commit()

    response = await admin_client.put(
        "/admin/kiger/update-kiger", json=VALID_KIGER_PAYLOAD
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Kiger"
    assert data["bio"] == "Updated bio"


async def test_update_kiger_with_characters(admin_client, db_session):
    kiger = DBKiger(
        id="kiger-chars-update",
        name="Kiger",
        bio="Bio",
        is_active=True,
    )
    char = DBCharacter(
        original_name="CharForUpdate",
        name="Char",
        type="game",
    )
    db_session.add_all([kiger, char])
    await db_session.flush()

    payload = {
        **VALID_KIGER_PAYLOAD,
        "Characters": [
            {
                "characterId": str(char.id),
                "maker": "MakerName",
                "images": ["https://example.com/img.png"],
            }
        ],
    }
    response = await admin_client.put("/admin/kiger/kiger-chars-update", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["Characters"]) == 1
    assert data["Characters"][0]["characterId"] == char.id


async def test_update_kiger_not_found(admin_client):
    response = await admin_client.put(
        "/admin/kiger/nonexistent", json=VALID_KIGER_PAYLOAD
    )
    assert response.status_code == 404


async def test_update_character_success(admin_client, db_session):
    char = DBCharacter(
        original_name="CharToUpdate",
        name="Old Name",
        type="game",
    )
    db_session.add(char)
    await db_session.commit()

    response = await admin_client.put(
        f"/admin/character/{char.id}", json=VALID_CHARACTER_PAYLOAD
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Character"
    assert data["type"] == "anime"


async def test_update_character_not_found(admin_client):
    response = await admin_client.put(
        "/admin/character/99999", json=VALID_CHARACTER_PAYLOAD
    )
    assert response.status_code == 404


async def test_update_maker_success(admin_client, db_session):
    maker = DBMaker(
        original_name="MakerToUpdate",
        name="Old Maker",
    )
    db_session.add(maker)
    await db_session.commit()

    response = await admin_client.put(
        f"/admin/maker/{maker.id}", json=VALID_MAKER_PAYLOAD
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Maker"


async def test_update_maker_not_found(admin_client):
    response = await admin_client.put("/admin/maker/99999", json=VALID_MAKER_PAYLOAD)
    assert response.status_code == 404
