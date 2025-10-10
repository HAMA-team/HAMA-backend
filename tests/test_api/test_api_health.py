import pytest
from httpx import AsyncClient, ASGITransport

from src.main import app


@pytest.mark.asyncio
async def test_health_endpoint_returns_database_status():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert "database" in data
    assert data["database"] in ("connected", "degraded") or data["database"].startswith("error:")
    assert data["status"] in ("healthy", "degraded")
