import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_db_connection(async_client):
    response = await async_client.get("/health/db")
    assert response.status_code == 200
    assert response.json()["db"] == "ok"
