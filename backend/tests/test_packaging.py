from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_builds_frontend_and_runs_non_root_with_persistent_data():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM node:22-bookworm-slim AS frontend-build" in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "RUN npm run build" in dockerfile
    assert "FROM python:3.12-slim-bookworm AS runtime" in dockerfile
    assert "TELEMETRY_SCOPE=container" in dockerfile
    assert "CAPABILITIES_MODE=safe_runtime" in dockerfile
    assert 'USER 10001:10001' in dockerfile
    assert 'VOLUME ["/app/backend/app/data"]' in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert 'CMD ["python", "-m", "app.run"]' in dockerfile


def test_default_compose_is_authenticated_loopback_api_only():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert '"127.0.0.1:${LCC_PORT:-17600}:17600"' in compose
    assert "LCC_API_KEY: \"${LCC_API_KEY:?" in compose
    assert 'REQUIRE_AUTH: "true"' in compose
    assert 'LAN_MODE: "true"' in compose
    assert "TELEMETRY_SCOPE: container" in compose
    assert "CAPABILITIES_MODE: safe_runtime" in compose
    assert "lcc-data:/app/backend/app/data" in compose
    assert "pid: host" not in compose
    assert "/sys:/sys" not in compose
    assert "/dev/dri" not in compose
    assert "/dev/accel" not in compose


def test_host_telemetry_override_is_explicit_and_read_only():
    override = (ROOT / "compose.host-telemetry.yaml").read_text(encoding="utf-8")

    assert "pid: host" in override
    assert "TELEMETRY_SCOPE: host" in override
    assert "/sys:/sys:ro" in override
    assert "LEMONADE_CACHE_DIR:?" in override
    assert ":/opt/var/lib/lemonade/.cache/lemonade:ro" in override


def test_deployment_docs_preserve_telemetry_and_ownership_boundaries():
    documentation = (ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")

    for required in ("`/proc`", "`/sys`", "`/dev/dri`", "`/dev/accel`", "`journalctl`", "`systemctl`"):
        assert required in documentation
    assert "ownership stays `unproven`" in documentation
    assert "API reachability is not host telemetry" in documentation
