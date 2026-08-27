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

    async def get(self, url, *args, **kwargs):
        request = httpx.Request("GET", url)
        raise httpx.ConnectError("connection refused", request=request)


@pytest.mark.asyncio
async def test_health_is_degraded_when_lemonade_is_unreachable(monkeypatch):
    monkeypatch.setattr(health.httpx, "AsyncClient", UnreachableClient)

    result = await health.health_check()

    assert result.status == "degraded"
    assert result.lemonade_reachable is False
    assert result.app_name == "Lemonade Control Center"


@pytest.mark.asyncio
async def test_health_is_ok_when_lemonade_is_reachable(monkeypatch):
    recorded_headers: list[dict] = []

    class ReachableClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, *, headers=None, **kwargs):
            recorded_headers.append(headers)
            request = httpx.Request("GET", url)
            return httpx.Response(200, request=request, json={"version": "10.9.0", "status": "ok"})

    monkeypatch.setattr(health.httpx, "AsyncClient", ReachableClient)

    result = await health.health_check()

    assert result.status == "ok"
    assert result.lemonade_reachable is True
    assert result.lemonade_version == "10.9.0"
