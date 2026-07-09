from app.models.setup import ConnectionDoctorResponse, LccConfig, RuntimeConfig
from app.services.setup import (
    SetupService,
    _connection_doctor_next_action,
    _is_local_url,
    _loaded_model_name,
    _normalize_lemonade_url,
)


def test_public_config_redacts_runtime_admin_key(tmp_path):
    service = SetupService(config_file=tmp_path / "config.json")
    service.save_config(
        LccConfig(
            setup_complete=True,
            runtimes=[
                RuntimeConfig(
                    id="lemonade-local",
                    type="lemonade",
                    name="Local Lemonade",
                    url="http://127.0.0.1:13305",
                    admin_key="super-secret",
                    is_active=True,
                )
            ],
            active_runtime_id="lemonade-local",
        )
    )

    public = service.get_public_config()
    serialized = public.model_dump()

    assert public.runtimes[0].admin_key_configured is True
    assert "super-secret" not in str(serialized)


def test_runtime_update_preserves_existing_key_when_omitted(tmp_path):
    service = SetupService(config_file=tmp_path / "config.json")
    original = RuntimeConfig(
        id="lemonade-local",
        type="lemonade",
        name="Local Lemonade",
        url="http://127.0.0.1:13305",
        admin_key="super-secret",
        is_active=True,
    )
    service.save_config(
        LccConfig(
            runtimes=[original],
            active_runtime_id=original.id,
        )
    )

    updated = original.model_copy(
        update={
            "name": "Corsaro Lemonade",
            "admin_key": None,
        }
    )
    result = service.update_runtime(original.id, updated)

    assert result is not None
    assert result.admin_key_configured is True
    assert service.get_config().runtimes[0].admin_key == "super-secret"


def test_normalize_lemonade_url_removes_api_suffix():
    assert _normalize_lemonade_url("192.168.1.5:13305/api/v1/") == "http://192.168.1.5:13305"
    assert _normalize_lemonade_url("http://localhost:13305/v1") == "http://localhost:13305"


def test_is_local_url_identifies_loopback_and_remote_hosts():
    assert _is_local_url("http://localhost:13305") is True
    assert _is_local_url("http://127.0.0.1:13305/api/v1") is True
    assert _is_local_url("http://[::1]:13305") is True
    assert _is_local_url("http://192.168.31.41:13305") is False


def test_loaded_model_name_handles_health_shapes():
    assert _loaded_model_name({"model_loaded": "qwen"}) == "qwen"
    assert _loaded_model_name({"all_models_loaded": [{"name": "coder"}]}) == "coder"
    assert _loaded_model_name({"loaded_models": ["tiny"]}) == "tiny"
    assert _loaded_model_name({"loaded_models": []}) is None


def test_connection_doctor_next_action_prioritizes_reachability_and_locality():
    unreachable = ConnectionDoctorResponse(
        runtime_id="lemonade-local",
        target_url="http://localhost:13305",
        normalized_url="http://localhost:13305",
    )
    assert "Fix the Lemonade URL" in _connection_doctor_next_action(unreachable)

    remote = unreachable.model_copy(update={"reachable": True, "local_target": False})
    assert "remote target" in _connection_doctor_next_action(remote)

    loaded = unreachable.model_copy(update={"reachable": True, "local_target": True, "loaded_model": "qwen"})
    assert "smoke test" in _connection_doctor_next_action(loaded)
