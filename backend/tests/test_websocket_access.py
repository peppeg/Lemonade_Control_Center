import re
from types import SimpleNamespace

import pytest
from fastapi.routing import APIWebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.services.security import origin_allowed

KEY = "test-secret"
LOOPBACK = "127.0.0.1"
REMOTE = "192.168.1.20"
FOREIGN = "https://evil.example"
HOST = "127.0.0.1:17600"
SAME_ORIGIN = f"http://{HOST}"


def _websocket_paths() -> list[str]:
    paths = [route.path for route in app.routes if isinstance(route, APIWebSocketRoute)]
    return [re.sub(r"\{[^}]+\}", "x", path) for path in paths]


WEBSOCKET_PATHS = _websocket_paths()


@pytest.fixture(autouse=True)
def _no_journal(monkeypatch):
    # Accepted log handshakes must not start a real `journalctl -f`.
    monkeypatch.setattr("app.routers.logs.capabilities", SimpleNamespace(cmd_journalctl=False))


@pytest.fixture
def configure(monkeypatch):
    def apply(*, require_auth: bool = False, key: str | None = None, origins: str = "") -> None:
        monkeypatch.setattr("app.config.settings.require_auth", require_auth)
        monkeypatch.setattr("app.config.settings.lcc_api_key", key)
        monkeypatch.setattr("app.config.settings.allowed_origins", origins)

    return apply


def _accepted(path: str, client: str, *, origin: str | None = None, key: str | None = None) -> bool:
    headers = {"host": HOST}
    if origin is not None:
        headers["origin"] = origin
    if key is not None:
        headers["x-lcc-api-key"] = key
    try:
        # No lifespan: the background collector must not run in these tests.
        with TestClient(app, client=(client, 50000)).websocket_connect(path, headers=headers):
            return True
    except WebSocketDisconnect as refused:
        assert refused.code == 1008
        return False


def test_known_websocket_routes_are_discovered():
    # Guards the parametrized tests below against silently covering nothing.
    assert {"/ws/metrics", "/api/logs/ws/logs"} <= set(WEBSOCKET_PATHS)


@pytest.mark.parametrize("path", WEBSOCKET_PATHS)
@pytest.mark.parametrize(
    ("client", "require_auth", "configured_key", "supplied_key", "expected"),
    [
        pytest.param(LOOPBACK, False, None, None, True, id="loopback-trusted"),
        pytest.param(LOOPBACK, True, KEY, None, False, id="loopback-auth-no-key"),
        pytest.param(LOOPBACK, True, KEY, "wrong", False, id="loopback-auth-wrong-key"),
        pytest.param(LOOPBACK, True, KEY, KEY, True, id="loopback-auth-valid-key"),
        pytest.param(LOOPBACK, True, None, None, False, id="loopback-auth-unconfigured"),
        pytest.param(REMOTE, False, KEY, None, False, id="remote-no-key"),
        pytest.param(REMOTE, False, KEY, "wrong", False, id="remote-wrong-key"),
        pytest.param(REMOTE, False, KEY, KEY, True, id="remote-valid-key"),
        pytest.param(REMOTE, False, None, "anything", False, id="remote-unconfigured"),
    ],
)
def test_key_rules(configure, path, client, require_auth, configured_key, supplied_key, expected):
    configure(require_auth=require_auth, key=configured_key)

    assert _accepted(path, client, key=supplied_key) is expected


@pytest.mark.parametrize("path", WEBSOCKET_PATHS)
def test_key_is_accepted_in_the_query_string(configure, path):
    configure(key=KEY)

    assert _accepted(f"{path}?lcc_key={KEY}", REMOTE, origin=SAME_ORIGIN) is True


@pytest.mark.parametrize("path", WEBSOCKET_PATHS)
@pytest.mark.parametrize(
    ("origin", "expected"),
    [
        pytest.param(None, True, id="missing"),
        pytest.param(SAME_ORIGIN, True, id="same-origin"),
        pytest.param("http://localhost:5173", True, id="dev-server"),
        pytest.param(FOREIGN, False, id="foreign"),
        pytest.param("http://127.0.0.1:9999", False, id="same-host-other-port"),
        pytest.param("null", False, id="opaque"),
        pytest.param("", False, id="empty"),
    ],
)
def test_origin_rules(configure, path, origin, expected):
    configure()

    assert _accepted(path, LOOPBACK, origin=origin) is expected


@pytest.mark.parametrize("path", WEBSOCKET_PATHS)
def test_foreign_origin_is_refused_even_with_a_valid_key(configure, path):
    configure(key=KEY)

    assert _accepted(path, REMOTE, origin=FOREIGN, key=KEY) is False


@pytest.mark.parametrize("path", WEBSOCKET_PATHS)
def test_configured_origin_is_accepted_when_the_proxy_rewrites_host(configure, path):
    configure(origins="https://lcc.example.com, https://other.example.com/")

    assert _accepted(path, LOOPBACK, origin="https://lcc.example.com") is True
    assert _accepted(path, LOOPBACK, origin="https://other.example.com") is True
    assert _accepted(path, LOOPBACK, origin=FOREIGN) is False


@pytest.mark.parametrize(
    ("origin", "host", "expected"),
    [
        # TLS proxy that forwards Host: LCC sees http while the browser uses https.
        ("https://lcc.example.com", "lcc.example.com", True),
        ("https://lcc.example.com", "lcc.example.com:443", True),
        ("https://lcc.example.com:443", "lcc.example.com", True),
        ("http://LCC.example.com", "lcc.example.com:80", True),
        ("http://[::1]:17600", "[::1]:17600", True),
        ("http://lcc.example.com.evil.example", "lcc.example.com", False),
        ("http://lcc.example.com@evil.example", "lcc.example.com", False),
        ("http://127.0.0.1:17600/path", "127.0.0.1:17600", False),
        ("chrome-extension://abcdef", "abcdef", False),
        ("http://127.0.0.1:notaport", "127.0.0.1:17600", False),
        ("http://[broken", "127.0.0.1:17600", False),
        ("http://127.0.0.1:17600", None, False),
        ("http://127.0.0.1:17600", "[broken", False),
    ],
)
def test_origin_matching(configure, origin, host, expected):
    configure()

    assert origin_allowed(origin, host) is expected
