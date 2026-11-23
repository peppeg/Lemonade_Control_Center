import json

import pytest
from app_routes import http_routes
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from app.main import app
from app.middleware.access_control import LccAccessControlMiddleware
from app.services.security import MUTATING_METHODS

KEY = "test-secret"
LOOPBACK = "127.0.0.1"
REMOTE = "192.168.1.20"
HOST = "127.0.0.1:17600"
SAME_ORIGIN = f"http://{HOST}"
FOREIGN = "https://evil.example"

MUTATING_ROUTES = [(method, path) for method, path in http_routes() if method in MUTATING_METHODS]


@pytest.fixture(autouse=True)
def audit_log(monkeypatch, tmp_path):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr("app.services.security.AUDIT_LOG", path)
    monkeypatch.setattr("app.config.settings.require_auth", False)
    monkeypatch.setattr("app.config.settings.lcc_api_key", None)
    monkeypatch.setattr("app.config.settings.allowed_origins", "")
    return path


def _send(method: str, path: str, client: str = LOOPBACK, **headers: str) -> int:
    # The middleware wraps a stand-in app on purpose: if the check regressed,
    # running these tests must not restart services or delete local data.
    stand_in = LccAccessControlMiddleware(PlainTextResponse("handler reached"))
    sent = {"host": HOST} | {name.replace("_", "-"): value for name, value in headers.items()}
    return TestClient(stand_in, client=(client, 50000)).request(method, path, headers=sent).status_code


def test_the_app_installs_the_middleware():
    assert LccAccessControlMiddleware in [item.cls for item in app.user_middleware]


def test_known_mutating_routes_are_discovered():
    # Guards the parametrized test below against silently covering nothing.
    assert {
        ("POST", "/api/metrics/clear"),
        ("POST", "/api/lemonade/unload"),
        ("POST", "/api/settings/runtimes/x/activate"),
        ("POST", "/api/system/restart"),
    } <= set(MUTATING_ROUTES)


@pytest.mark.parametrize(("method", "path"), MUTATING_ROUTES)
def test_every_mutating_route_refuses_cross_site_requests(method, path):
    assert _send(method, path, origin=FOREIGN, sec_fetch_site="cross-site") == 403
    assert _send(method, path, origin=FOREIGN) == 403
    assert _send(method, path, origin=SAME_ORIGIN, sec_fetch_site="same-origin") == 200
    assert _send(method, path) == 200


@pytest.mark.parametrize("method", sorted(MUTATING_METHODS))
@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        pytest.param({}, 200, id="cli"),
        pytest.param({"origin": SAME_ORIGIN}, 200, id="same-origin-no-fetch-metadata"),
        pytest.param({"origin": SAME_ORIGIN, "sec_fetch_site": "same-origin"}, 200, id="same-origin"),
        pytest.param({"sec_fetch_site": "none"}, 200, id="user-initiated"),
        pytest.param({"sec_fetch_site": "cross-site"}, 403, id="cross-site-no-origin"),
        pytest.param({"origin": "null", "sec_fetch_site": "cross-site"}, 403, id="sandboxed-frame"),
        pytest.param({"origin": "null"}, 403, id="opaque-origin"),
        pytest.param({"origin": ""}, 403, id="empty-origin"),
        pytest.param(
            {"origin": "http://127.0.0.1:9999", "sec_fetch_site": "same-site"}, 403, id="other-local-port"
        ),
        pytest.param({"origin": "http://127.0.0.1:9999"}, 403, id="other-local-port-no-fetch-metadata"),
        pytest.param({"sec_fetch_site": "unexpected"}, 403, id="unknown-fetch-site"),
        # A proxy that rewrites Host: the browser still reports same-origin.
        pytest.param(
            {"origin": "https://lcc.example.com", "sec_fetch_site": "same-origin"}, 200, id="proxy-rewrites-host"
        ),
        # Vite proxy, and a frontend that calls the API directly.
        pytest.param({"origin": "http://localhost:5173", "sec_fetch_site": "same-origin"}, 200, id="dev-proxy"),
        pytest.param({"origin": "http://localhost:5173", "sec_fetch_site": "cross-site"}, 200, id="dev-direct"),
        pytest.param({"origin": "http://localhost:5173"}, 200, id="dev-no-fetch-metadata"),
    ],
)
def test_cross_site_rules(method, headers, expected):
    assert _send(method, "/api/example", **headers) == expected


def test_paths_outside_the_api_are_covered_too():
    assert _send("POST", "/elsewhere", origin=FOREIGN) == 403


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
def test_safe_methods_are_not_affected(method):
    assert _send(method, "/api/example", origin=FOREIGN, sec_fetch_site="cross-site") == 200


def test_configured_origin_is_accepted(monkeypatch):
    monkeypatch.setattr("app.config.settings.allowed_origins", "http://lcc.lan")

    assert _send("POST", "/api/example", origin="http://lcc.lan") == 200
    assert _send("POST", "/api/example", origin="http://other.lan") == 403


def test_lan_clients_follow_the_same_rule_even_with_a_valid_key(monkeypatch):
    monkeypatch.setattr("app.config.settings.lcc_api_key", KEY)

    assert _send("POST", "/api/example", client=REMOTE, origin=FOREIGN, x_lcc_api_key=KEY) == 403
    assert _send("POST", "/api/example", client=REMOTE, origin=SAME_ORIGIN, x_lcc_api_key=KEY) == 200
    assert _send("POST", "/api/example", client=REMOTE, origin=SAME_ORIGIN) == 401


def test_refused_requests_are_audited(audit_log):
    _send("POST", "/api/metrics/clear", origin=FOREIGN, sec_fetch_site="cross-site")

    record = json.loads(audit_log.read_text(encoding="utf-8"))
    assert record["path"] == "/api/metrics/clear"
    assert record["status_code"] == 403
    assert record["authenticated"] is False
