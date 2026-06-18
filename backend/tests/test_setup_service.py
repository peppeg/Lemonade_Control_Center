from app.models.setup import LccConfig, RuntimeConfig
from app.services.setup import SetupService


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
