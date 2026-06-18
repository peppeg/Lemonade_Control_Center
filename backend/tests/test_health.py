import httpx
import pytest

from app.routers import health


class UnreachableClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, url):
        request = httpx.Request("GET", url)
        raise httpx.ConnectError("connection refused", request=request)


@pytest.mark.asyncio
async def test_health_is_degraded_when_lemonade_is_unreachable(monkeypatch):
    monkeypatch.setattr(health.httpx, "AsyncClient", UnreachableClient)

    result = await health.health_check()

    assert result.status == "degraded"
    assert result.lemonade_reachable is False
    assert result.app_name == "Lemonade Control Center"
