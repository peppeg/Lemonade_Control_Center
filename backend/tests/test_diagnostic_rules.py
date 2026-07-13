import pytest

from app.services.diagnostics.engine import SystemState
from app.services.diagnostics.rules import capability_gap


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
