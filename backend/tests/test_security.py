import json

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.middleware.access_control import LccAccessControlMiddleware
from app.services.security import is_loopback_host, security_status


def make_request(host: str, headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/private",
            "raw_path": b"/api/private",
            "query_string": b"",
            "headers": headers or [],
            "client": (host, 50000),
            "server": ("testserver", 80),
        }
    )


async def success_response(request: Request):
    return JSONResponse({"ok": True})


def response_json(response: JSONResponse) -> dict:
    return json.loads(response.body)


def test_loopback_detection():
    assert is_loopback_host("localhost")
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("::1")
    assert not is_loopback_host("192.168.1.20")
    assert not is_loopback_host(None)


def test_localhost_is_trusted_by_default(monkeypatch):
    monkeypatch.setattr("app.config.settings.require_auth", False)
    monkeypatch.setattr("app.config.settings.lcc_api_key", None)

    assert security_status("127.0.0.1")["authenticated"] is True


@pytest.mark.asyncio
async def test_remote_access_is_blocked_without_configured_key(monkeypatch):
    monkeypatch.setattr("app.config.settings.require_auth", False)
    monkeypatch.setattr("app.config.settings.lcc_api_key", None)
    middleware = LccAccessControlMiddleware(success_response)

    response = await middleware.dispatch(
        make_request("192.168.1.20"),
        success_response,
    )

    assert response.status_code == 503
    assert "LCC_API_KEY is not configured" in response_json(response)["detail"]


@pytest.mark.asyncio
async def test_remote_access_accepts_header_and_bearer_keys(monkeypatch):
    monkeypatch.setattr("app.config.settings.require_auth", False)
    monkeypatch.setattr("app.config.settings.lcc_api_key", "test-secret")
    middleware = LccAccessControlMiddleware(success_response)

    missing = await middleware.dispatch(
        make_request("192.168.1.20"),
        success_response,
    )
    header = await middleware.dispatch(
        make_request(
            "192.168.1.20",
            [(b"x-lcc-api-key", b"test-secret")],
        ),
        success_response,
    )
    bearer = await middleware.dispatch(
        make_request(
            "192.168.1.20",
            [(b"authorization", b"Bearer test-secret")],
        ),
        success_response,
    )

    assert missing.status_code == 401
    assert header.status_code == 200
    assert bearer.status_code == 200
