from unittest.mock import AsyncMock, patch


@patch("api.main.fetch_twitter_user", new_callable=AsyncMock)
async def test_crawl_twitter_user(mock_fetch, client):
    mock_fetch.return_value = {
        "name": "Test User",
        "description": "A test bio",
        "profile_image_url": "https://example.com/avatar.jpg",
    }
    response = await client.post(
        "/crawl/twitter/user", json={"username": "testuser"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test User"
    assert data["bio"] == "A test bio"
    mock_fetch.assert_called_once_with("testuser")


@patch("api.main.parse_character_from_tweet", new_callable=AsyncMock)
@patch("api.main.fetch_twitter_tweet", new_callable=AsyncMock)
async def test_crawl_twitter_tweet(mock_fetch, mock_parse, client):
    mock_fetch.return_value = {
        "text": "Cosplaying as Character!",
        "media_extended": [
            {"type": "image", "url": "https://example.com/img.png"}
        ],
    }
    mock_parse.return_value = {
        "name": "Test Character",
        "originalName": "TestChar",
    }
    response = await client.post(
        "/crawl/twitter/tweet", json={"username": "testuser", "tweet_id": "123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["character"]["name"] == "Test Character"
    assert len(data["images"]) == 1


@patch("api.main.parse_character_image", new_callable=AsyncMock)
async def test_crawl_image_success(mock_parse, client):
    mock_parse.return_value = {
        "name": "Detected Character",
        "originalName": "DetectedChar",
    }
    response = await client.post(
        "/crawl/image", json={"image_url": "https://example.com/photo.jpg"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["character"]["name"] == "Detected Character"


async def test_crawl_image_invalid_url(client):
    response = await client.post(
        "/crawl/image", json={"image_url": "not-a-url"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error"] is not None
