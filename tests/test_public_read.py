from api.database import Character as DBCharacter
from api.database import Kiger as DBKiger
from api.database import KigerCharacter
from api.database import Maker as DBMaker


async def test_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "v2.0" in data["message"]


# --- Kigers ---


async def test_get_kigers_empty(client):
    response = await client.get("/kigers")
    assert response.status_code == 200
    assert response.json() == []


async def test_get_kigers_with_data(client, db_session):
    kiger = DBKiger(
        id="test-kiger-1",
        name="Test Kiger",
        bio="A test bio",
        profile_image="https://example.com/img.png",
        position="cosplayer",
        is_active=True,
        social_media={"twitter": "https://twitter.com/test"},
    )
    db_session.add(kiger)
    await db_session.commit()

    response = await client.get("/kigers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "test-kiger-1"
    assert data[0]["name"] == "Test Kiger"
    assert data[0]["isActive"] is True


async def test_get_kiger_by_id(client, db_session):
    kiger = DBKiger(
        id="kiger-detail",
        name="Detail Kiger",
        bio="Detail bio",
        profile_image="https://example.com/detail.png",
        position="performer",
        is_active=True,
        social_media=None,
    )
    db_session.add(kiger)
    await db_session.commit()

    response = await client.get("/kiger/kiger-detail")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "kiger-detail"
    assert data["name"] == "Detail Kiger"
    assert data["Characters"] == []


async def test_get_kiger_with_characters(client, db_session):
    kiger = DBKiger(
        id="kiger-with-chars",
        name="Kiger With Chars",
        bio="",
        is_active=True,
    )
    char = DBCharacter(
        original_name="TestChar",
        name="Test Character",
        type="game",
        official_image="https://example.com/char.png",
        source={"title": "Test Game", "company": "TestCo", "releaseYear": 2024},
    )
    db_session.add(kiger)
    db_session.add(char)
    await db_session.flush()

    kc = KigerCharacter(
        kiger_id=kiger.id,
        character_id=char.id,
        maker="TestMaker",
        images=["https://example.com/img1.png"],
    )
    db_session.add(kc)
    await db_session.commit()

    response = await client.get("/kiger/kiger-with-chars")
    assert response.status_code == 200
    data = response.json()
    assert len(data["Characters"]) == 1
    assert data["Characters"][0]["characterId"] == char.id
    assert data["Characters"][0]["maker"] == "TestMaker"


async def test_get_kiger_not_found(client):
    response = await client.get("/kiger/nonexistent")
    assert response.status_code == 404


# --- Characters ---


async def test_get_characters_empty(client):
    response = await client.get("/characters")
    assert response.status_code == 200
    assert response.json() == []


async def test_get_characters_with_data(client, db_session):
    char = DBCharacter(
        original_name="Char1",
        name="Character One",
        type="anime",
        official_image="https://example.com/char1.png",
        source={"title": "Anime1", "company": "Studio1", "releaseYear": 2023},
    )
    db_session.add(char)
    await db_session.commit()

    response = await client.get("/characters")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Character One"
    assert data[0]["originalName"] == "Char1"


async def test_get_character_by_id(client, db_session):
    char = DBCharacter(
        original_name="CharById",
        name="Char By Id",
        type="vtuber",
        official_image="https://example.com/vtuber.png",
        source={"title": "VTuber Agency", "company": "Agency1", "releaseYear": 2022},
    )
    db_session.add(char)
    await db_session.commit()

    response = await client.get(f"/character/{char.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Char By Id"
    assert data["type"] == "vtuber"


async def test_get_character_not_found(client):
    response = await client.get("/character/99999")
    assert response.status_code == 404


# --- Makers ---


async def test_get_makers_empty(client):
    response = await client.get("/makers")
    assert response.status_code == 200
    assert response.json() == []


async def test_get_makers_with_data(client, db_session):
    maker = DBMaker(
        original_name="Maker1",
        name="Maker One",
        avatar="https://example.com/maker.png",
        social_media={"twitter": "https://twitter.com/maker1"},
    )
    db_session.add(maker)
    await db_session.commit()

    response = await client.get("/makers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Maker One"
    assert data[0]["originalName"] == "Maker1"


async def test_get_maker_by_id(client, db_session):
    maker = DBMaker(
        original_name="MakerById",
        name="Maker By Id",
        avatar="https://example.com/avatar.png",
        social_media=None,
    )
    db_session.add(maker)
    await db_session.commit()

    response = await client.get(f"/maker/{maker.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Maker By Id"


async def test_get_maker_not_found(client):
    response = await client.get("/maker/99999")
    assert response.status_code == 404
