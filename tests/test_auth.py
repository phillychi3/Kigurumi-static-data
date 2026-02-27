from api.auth import get_password_hash
from api.database import Admin

TEST_ADMIN_USERNAME = "testadmin"
TEST_ADMIN_PASSWORD = "testpassword123"


async def test_login_success(client, db_session):
    admin = Admin(
        username=TEST_ADMIN_USERNAME,
        hashed_password=get_password_hash(TEST_ADMIN_PASSWORD),
    )
    db_session.add(admin)
    await db_session.commit()

    response = await client.post(
        "/admin/login",
        json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["username"] == TEST_ADMIN_USERNAME


async def test_login_wrong_password(client, db_session):
    admin = Admin(
        username=TEST_ADMIN_USERNAME,
        hashed_password=get_password_hash(TEST_ADMIN_PASSWORD),
    )
    db_session.add(admin)
    await db_session.commit()

    response = await client.post(
        "/admin/login",
        json={"username": TEST_ADMIN_USERNAME, "password": "wrongpassword"},
    )
    assert response.status_code == 401


async def test_login_nonexistent_user(client):
    response = await client.post(
        "/admin/login",
        json={"username": "nonexistent", "password": "whatever"},
    )
    assert response.status_code == 401


async def test_admin_endpoint_without_token(client):
    response = await client.get("/admin/pending/kigers")
    assert response.status_code == 403


async def test_admin_endpoint_with_invalid_token(client):
    response = await client.get(
        "/admin/pending/kigers",
        headers={"Authorization": "Bearer invalid-token-here"},
    )
    assert response.status_code == 401


async def test_admin_endpoint_with_valid_token(client, db_session):
    admin = Admin(
        username=TEST_ADMIN_USERNAME,
        hashed_password=get_password_hash(TEST_ADMIN_PASSWORD),
    )
    db_session.add(admin)
    await db_session.commit()

    login_response = await client.post(
        "/admin/login",
        json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
    )
    token = login_response.json()["access_token"]

    response = await client.get(
        "/admin/pending/kigers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
