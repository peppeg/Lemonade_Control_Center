import pytest

from app.services.diagnostics.engine import SystemState
from app.services.diagnostics.models import Severity
from app.services.diagnostics.rules import capability_gap, lemonade_exposed


@pytest.mark.asyncio
async def test_capability_gap_asks_for_key_only_when_missing():
    state = SystemState()

    result = await capability_gap(state)

    assert result is not None
    assert result.alert is not None
    assert "Add the Lemonade admin API key" in result.alert.suggestion
    assert result.alert.evidence["has_admin_key"] is False


@pytest.mark.asyncio
async def test_capability_gap_does_not_claim_configured_key_is_missing():
    state = SystemState()
    state.has_admin_key = True

    result = await capability_gap(state)

    assert result is not None
    assert result.alert is not None
    assert "admin key is configured" in result.alert.description
    assert "Add the Lemonade admin API key" not in result.alert.suggestion
    assert "Connection Doctor" in result.alert.suggestion


@pytest.mark.asyncio
async def test_capability_gap_passes_when_admin_endpoints_are_available():
    state = SystemState()
    state.has_admin_key = True
    state.has_internal_config = True
    state.has_internal_set = True

    assert await capability_gap(state) is None


def _exposure_state(host, url="http://127.0.0.1:13305", internal=None, api=None) -> SystemState:
    state = SystemState()
    state.lemonade_host = host
    state.lemonade_url = url
    state.anonymous_internal_access = internal
    state.anonymous_api_access = api
    return state


@pytest.mark.asyncio
async def test_lemonade_exposed_flags_open_internal_endpoints_on_all_interfaces():
    result = await lemonade_exposed(_exposure_state("0.0.0.0", internal=True, api=True))

    assert result is not None
    assert result.alert is not None
    assert result.alert.severity == Severity.high
    assert "LEMONADE_API_KEY" in result.alert.suggestion


@pytest.mark.asyncio
async def test_lemonade_exposed_flags_open_inference_when_only_admin_key_is_set():
    result = await lemonade_exposed(_exposure_state("0.0.0.0", internal=False, api=True))

    assert result is not None
    assert result.alert is not None
    assert result.alert.severity == Severity.medium


@pytest.mark.asyncio
async def test_lemonade_exposed_uses_remote_url_when_host_is_unknown():
    result = await lemonade_exposed(_exposure_state(None, url="http://192.168.31.41:13305", internal=False, api=True))

    assert result is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("host", "internal", "api"),
    [
        ("127.0.0.1", True, True),
        ("localhost", True, True),
        ("0.0.0.0", False, False),
        ("0.0.0.0", None, None),
    ],
)
async def test_lemonade_exposed_passes_when_loopback_or_authenticated(host, internal, api):
    assert await lemonade_exposed(_exposure_state(host, internal=internal, api=api)) is None
