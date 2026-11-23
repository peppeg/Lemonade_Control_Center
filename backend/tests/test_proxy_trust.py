import json
import logging

import pytest
from app_routes import websocket_paths
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app import run
from app.main import app
from app.middleware.access_control import LccAccessControlMiddleware

KEY = "test-secret"
LOOPBACK = "127.0.0.1"
REMOTE = "192.168.1.20"
PUBLIC = "203.0.113.9"

# Uvicorn's own handling in front of LCC: off (`python -m app.run` default), and
# on with the local proxy trusted (TRUSTED_PROXY_IPS, or a plain `uvicorn` start).
SERVERS = [pytest.param(None, id="headers-ignored"), pytest.param(LOOPBACK, id="local-proxy-trusted")]


@pytest.fixture(autouse=True)
def audit_log(monkeypatch, tmp_path):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr("app.services.security.AUDIT_LOG", path)
    monkeypatch.setattr("app.services.security._warned", set())
    monkeypatch.setattr("app.config.settings.require_auth", False)
    monkeypatch.setattr("app.config.settings.lcc_api_key", KEY)
    monkeypatch.setattr("app.config.settings.allowed_origins", "")
    monkeypatch.setattr("app.config.settings.trusted_proxy_ips", "")
    return path


def _client(target, trusted: str | None, peer: str) -> TestClient:
    if trusted is not None:
        target = ProxyHeadersMiddleware(target, trusted_hosts=trusted)
    return TestClient(target, base_url="http://127.0.0.1:17600", client=(peer, 50000))


def _status(headers, *, trusted: str | None, peer: str = LOOPBACK, method: str = "GET") -> int:
    stand_in = LccAccessControlMiddleware(PlainTextResponse("handler reached"))
    return _client(stand_in, trusted, peer).request(method, "/api/example", headers=headers).status_code


@pytest.mark.parametrize("trusted", SERVERS)
def test_direct_localhost_is_still_trusted(trusted):
    assert _status({}, trusted=trusted) == 200


@pytest.mark.parametrize("trusted", SERVERS)
@pytest.mark.parametrize(
    "headers",
    [
        pytest.param([("x-forwarded-for", PUBLIC)], id="real-client"),
        pytest.param([("x-forwarded-for", LOOPBACK)], id="spoofed-loopback"),
        pytest.param([("x-forwarded-for", f"{LOOPBACK}, {PUBLIC}")], id="spoofed-then-appended"),
        # Some proxies add a second header line instead of extending the first.
        pytest.param([("x-forwarded-for", LOOPBACK), ("x-forwarded-for", PUBLIC)], id="repeated-header"),
        pytest.param([("x-forwarded-for", "")], id="empty"),
        pytest.param([("forwarded", "for=127.0.0.1")], id="forwarded"),
        pytest.param([("x-real-ip", LOOPBACK)], id="x-real-ip"),
    ],
)
def test_forwarded_requests_need_the_key(trusted, headers):
    assert _status(headers, trusted=trusted) == 401
    assert _status([*headers, ("x-lcc-api-key", "wrong")], trusted=trusted) == 401
    assert _status([*headers, ("x-lcc-api-key", KEY)], trusted=trusted) == 200


def test_forwarded_requests_are_blocked_when_no_key_is_configured(monkeypatch):
    monkeypatch.setattr("app.config.settings.lcc_api_key", None)

    assert _status({"x-forwarded-for": LOOPBACK}, trusted=None) == 503
    assert _status({}, trusted=None) == 200


def test_untrusted_peer_cannot_choose_its_address(audit_log):
    spoofed = {"x-forwarded-for": LOOPBACK}

    assert _status(spoofed, trusted=LOOPBACK, peer=REMOTE, method="POST") == 401

    record = json.loads(audit_log.read_text(encoding="utf-8"))
    assert record["client_host"] == REMOTE
    assert record["local"] is False


@pytest.mark.parametrize(("trusted", "recorded"), [(None, LOOPBACK), (LOOPBACK, PUBLIC)])
def test_audit_records_the_forwarded_address_only_from_trusted_proxies(audit_log, trusted, recorded):
    headers = {"x-forwarded-for": PUBLIC, "x-lcc-api-key": KEY}

    assert _status(headers, trusted=trusted, method="POST") == 200

    record = json.loads(audit_log.read_text(encoding="utf-8"))
    assert record["client_host"] == recorded
    assert record["local"] is False


@pytest.mark.parametrize("trusted", SERVERS)
@pytest.mark.parametrize("path", websocket_paths())
def test_forwarded_websockets_need_the_key(monkeypatch, trusted, path):
    # Accepted log handshakes must not start a real `journalctl -f`.
    monkeypatch.setattr("app.routers.logs.capabilities.cmd_journalctl", False)
    client = _client(app, trusted, LOOPBACK)
    spoofed = {"x-forwarded-for": LOOPBACK}

    with pytest.raises(WebSocketDisconnect) as refused, client.websocket_connect(path, headers=spoofed):
        pass
    assert refused.value.code == 1008

    with client.websocket_connect(path, headers=spoofed | {"x-lcc-api-key": KEY}):
        pass
    # websocket_connect() ignores base_url, so the Host has to be explicit.
    with client.websocket_connect(path, headers={"host": "127.0.0.1:17600"}):
        pass


def test_status_asks_forwarded_clients_for_the_key():
    client = _client(app, None, LOOPBACK)

    direct = client.get("/api/security/status").json()
    forwarded = client.get("/api/security/status", headers={"x-forwarded-for": LOOPBACK}).json()

    assert (direct["auth_required"], direct["mode"], direct["lan_client"]) == (False, "localhost", False)
    assert (forwarded["auth_required"], forwarded["mode"], forwarded["lan_client"]) == (True, "lan", True)
    assert forwarded["authenticated"] is False


def test_forwarding_is_explained_once(caplog):
    with caplog.at_level(logging.WARNING, logger="app.services.security"):
        _status({}, trusted=None)
        assert caplog.records == []
        _status({"x-forwarded-for": PUBLIC}, trusted=None)
        _status({"x-forwarded-for": PUBLIC}, trusted=None)

    assert len(caplog.records) == 1
    assert "LCC_API_KEY" in caplog.text


@pytest.mark.parametrize(
    ("configured", "proxy_headers", "allowed"),
    [("", False, ""), ("  ", False, ""), ("127.0.0.1", True, "127.0.0.1"), (" 10.0.0.2,::1 ", True, "10.0.0.2,::1")],
)
def test_run_passes_explicit_proxy_options(monkeypatch, configured, proxy_headers, allowed):
    calls = []
    monkeypatch.setattr("app.run.uvicorn.run", lambda *args, **kwargs: calls.append(kwargs))
    monkeypatch.setattr("app.config.settings.lan_mode", False)
    monkeypatch.setattr("app.config.settings.trusted_proxy_ips", configured)

    run.main()

    assert calls[0]["proxy_headers"] is proxy_headers
    assert calls[0]["forwarded_allow_ips"] == allowed
