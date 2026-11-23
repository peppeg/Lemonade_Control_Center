import json
import logging

import pytest
from app_routes import websocket_paths
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.middleware.access_control import LccAccessControlMiddleware
from app.services.security import host_allowed

KEY = "test-secret"
LOOPBACK = "127.0.0.1"
REMOTE = "192.168.1.20"
REBOUND = "evil.example:17600"


@pytest.fixture(autouse=True)
def audit_log(monkeypatch, tmp_path):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr("app.services.security.AUDIT_LOG", path)
    monkeypatch.setattr("app.services.security._warned", set())
    monkeypatch.setattr("app.config.settings.require_auth", False)
    monkeypatch.setattr("app.config.settings.lcc_api_key", KEY)
    monkeypatch.setattr("app.config.settings.allowed_origins", "")
    monkeypatch.setattr("app.config.settings.allowed_hosts", "")
    monkeypatch.setattr("app.config.settings.trusted_proxy_ips", "")
    return path


def _status(host: str, *, peer: str = LOOPBACK, method: str = "GET", **headers: str) -> int:
    stand_in = LccAccessControlMiddleware(PlainTextResponse("handler reached"))
    sent = {"host": host} | {name.replace("_", "-"): value for name, value in headers.items()}
    return TestClient(stand_in, client=(peer, 50000)).request(method, "/api/example", headers=sent).status_code


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        (None, True),
        ("localhost", True),
        ("localhost:17600", True),
        ("LOCALHOST:17600", True),
        ("lcc.localhost:17600", True),
        ("127.0.0.1:17600", True),
        ("[::1]:17600", True),
        ("192.168.1.5:17600", True),
        ("evil.example", False),
        (REBOUND, False),
        ("localhost.evil.example", False),
        ("127.0.0.1.evil.example", False),
        ("notlocalhost", False),
        ("localhost@evil.example", False),
        ("", False),
        ("[broken", False),
        ("localhost:notaport", False),
    ],
)
def test_local_names(host, expected):
    assert host_allowed(host) is expected


def test_configured_names_are_accepted(monkeypatch):
    monkeypatch.setattr("app.config.settings.allowed_hosts", "corsaro, LCC.lan")

    assert host_allowed("corsaro:17600")
    assert host_allowed("lcc.lan")
    assert not host_allowed("other.lan")
    assert not host_allowed("sub.lcc.lan")


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_rebound_requests_need_the_key(method):
    # Everything a rebound page sends looks same-origin.
    same_origin = {"origin": f"http://{REBOUND}", "sec_fetch_site": "same-origin"}

    assert _status(REBOUND, method=method, **same_origin) == 401
    assert _status(REBOUND, method=method, x_lcc_api_key=KEY, **same_origin) == 200
    assert _status("localhost:17600", method=method) == 200


def test_rebound_requests_are_blocked_when_no_key_is_configured(monkeypatch):
    monkeypatch.setattr("app.config.settings.lcc_api_key", None)

    assert _status(REBOUND) == 503
    assert _status("localhost:17600") == 200


def test_lan_clients_may_use_any_name_with_the_key():
    assert _status("lcc.lan", peer=REMOTE) == 401
    assert _status("lcc.lan", peer=REMOTE, x_lcc_api_key=KEY) == 200


@pytest.mark.parametrize("path", websocket_paths())
def test_rebound_websockets_need_the_key(monkeypatch, path):
    # Accepted log handshakes must not start a real `journalctl -f`.
    monkeypatch.setattr("app.routers.logs.capabilities.cmd_journalctl", False)
    client = TestClient(app, client=(LOOPBACK, 50000))
    rebound = {"host": REBOUND, "origin": f"http://{REBOUND}"}

    with pytest.raises(WebSocketDisconnect) as refused, client.websocket_connect(path, headers=rebound):
        pass
    assert refused.value.code == 1008

    with client.websocket_connect(path, headers=rebound | {"x-lcc-api-key": KEY}):
        pass


def test_status_and_audit_do_not_call_rebound_requests_local(audit_log):
    status = TestClient(app, client=(LOOPBACK, 50000)).get("/api/security/status", headers={"host": REBOUND}).json()
    _status(REBOUND, method="POST")

    assert (status["auth_required"], status["authenticated"], status["mode"]) == (True, False, "lan")
    assert json.loads(audit_log.read_text(encoding="utf-8"))["local"] is False


def test_unknown_names_are_explained_once_and_only_for_local_clients(caplog):
    with caplog.at_level(logging.WARNING, logger="app.services.security"):
        _status("lcc.lan", peer=REMOTE)
        assert caplog.records == []
        _status(REBOUND)
        _status(REBOUND)

    assert len(caplog.records) == 1
    assert "ALLOWED_HOSTS" in caplog.text
