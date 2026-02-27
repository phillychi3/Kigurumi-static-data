from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.auth import get_password_hash
from api.cache import clear_cache
from api.database import Admin, Base, get_db
from api.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_ADMIN_USERNAME = "testadmin"
TEST_ADMIN_PASSWORD = "testpassword123"


@pytest_asyncio.fixture()
async def db_session():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def client(db_session):
    clear_cache()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Disable rate limiter in tests
    app.state.limiter.enabled = False

    with patch("api.main.init_db", new_callable=AsyncMock):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            yield ac

    app.state.limiter.enabled = True
    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def admin_client(db_session):
    clear_cache()

    admin = Admin(
        username=TEST_ADMIN_USERNAME,
        hashed_password=get_password_hash(TEST_ADMIN_PASSWORD),
    )
    db_session.add(admin)
    await db_session.commit()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Disable rate limiter in tests
    app.state.limiter.enabled = False

    with patch("api.main.init_db", new_callable=AsyncMock):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            login_response = await ac.post(
                "/admin/login",
                json={
                    "username": TEST_ADMIN_USERNAME,
                    "password": TEST_ADMIN_PASSWORD,
                },
            )
            assert login_response.status_code == 200
            token = login_response.json()["access_token"]
            ac.headers["Authorization"] = f"Bearer {token}"
            yield ac

    app.state.limiter.enabled = True
    app.dependency_overrides.clear()
