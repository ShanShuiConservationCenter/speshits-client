#type:ignore
from unittest.mock import AsyncMock

import httpx
import pytest
from tenacity import RetryError

from speshits_client.client import SpeshitsClient


@pytest.fixture
def mock_client(monkeypatch):
    """Fixture providing a SpeshitsClient with mocked credentials"""
    return SpeshitsClient(username="test", password="test")


@pytest.fixture(autouse=True)
def mock_httpx(monkeypatch):
    """Mock httpx requests for all tests"""
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "access_token": "fake_token",
        "expires_in": 3600,
        "success": True,
    }
    mock_response.raise_for_status = AsyncMock()

    mock_get = AsyncMock()
    mock_get.json.return_value = {
        "success": True,
        "total": 3,
        "data": [{"id": 1}, {"id": 2}, {"id": 3}],
    }

    monkeypatch.setattr(
        httpx.AsyncClient, "post", AsyncMock(return_value=mock_response)
    )
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=mock_get))


@pytest.mark.asyncio
async def test_get_token_success(mock_client):
    token = await mock_client.get_token()
    assert token == "fake_token"
    assert isinstance(mock_client.expire, int)
    assert mock_client.expire > 0


@pytest.mark.asyncio
async def test_get_token_failure(mock_client, monkeypatch):
    mock_error = AsyncMock()
    mock_error.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401 Unauthorized",
        request=httpx.Request("POST", ""),
        response=httpx.Response(401),
    )
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=mock_error))

    with pytest.raises(httpx.HTTPStatusError):
        await mock_client.get_token()


@pytest.mark.asyncio
async def test_refresh_token_logic(mock_client, monkeypatch):
    # Initial token fetch
    await mock_client.refresh_token()
    original_expire = mock_client.expire

    # Simulate expiration
    mock_client.expire = 0
    await mock_client.refresh_token()
    assert mock_client.expire != original_expire


@pytest.mark.asyncio
async def test_get_taxons_page_validation(mock_client):
    with pytest.raises(ValueError):
        await mock_client.get_taxons_page()


@pytest.mark.asyncio
async def test_retry_mechanism(mock_client, monkeypatch):
    mock_error = AsyncMock()
    mock_error.raise_for_status.side_effect = httpx.ReadTimeout("Timeout")
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=mock_error))

    with pytest.raises(RetryError):
        await mock_client.get_taxons_page(canonicalName="test")


@pytest.mark.asyncio
async def test_pagination_logic(mock_client, monkeypatch):
    # Setup paginated responses
    mock_responses = [{"total": 5, "data": [1, 2, 3]}, {"total": 5, "data": [4, 5]}]

    mock_get = AsyncMock()
    mock_get.json.side_effect = mock_responses
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=mock_get))

    results = await mock_client.get_all_taxons(canonicalName="test")
    assert len(results) == 5
    assert httpx.AsyncClient.get.await_count == 2


@pytest.mark.asyncio
async def test_error_handling(mock_client, monkeypatch):
    mock_error = AsyncMock()
    mock_error.json.return_value = {"success": False, "message": "Invalid parameter"}
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=mock_error))

    with pytest.raises(Exception) as exc:
        await mock_client.get_taxons_page(canonicalName="test")
    assert "Invalid parameter" in str(exc.value)
