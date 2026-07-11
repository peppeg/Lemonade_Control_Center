import json

from app.models.profiles import ProfileConfig, ProfileCreateRequest, ProfileUpdateRequest
from app.models.schemas import RunEvidenceSeed
from app.services.profile_service import ProfileService
from app.services.run_evidence import RunEvidenceStorage


def test_profile_service_migrates_metadata_and_attaches_latest_useful_evidence(tmp_path):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "model-a.json").write_text(
        json.dumps(
            {
                "model_name": "model-a",
                "default_profile_id": "coding",
                "profiles": [
                    {
                        "id": "coding",
                        "name": "Coding",
                        "description": "Legacy profile",
                        "icon": "code",
                        "config": {"ctx_size": 16384},
                        "is_builtin": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    evidence = RunEvidenceStorage(path=tmp_path / "evidence.json")
    evidence.add(
        RunEvidenceSeed(
            id="failed",
            model_name="model-a",
            workflow_profile_id="coding",
            success=False,
        )
    )
    evidence.add(
        RunEvidenceSeed(
            id="useful",
            model_name="model-a",
            workflow_profile_id="coding",
            success=True,
            observed_model_name="model-a-canonical",
            observed_backend="vulkan",
            observed_ctx_size=16384,
        )
    )

    service = ProfileService(profiles_dir=profiles_dir, evidence_storage=evidence)
    result = service.list_profiles("model-a")
    coding = next(profile for profile in result.profiles if profile.id == "coding")

    assert coding.intent == "Coding Fast"
    assert coding.notes == ""
    assert coding.known_caveats == []
    assert coding.latest_evidence is not None
    assert coding.latest_evidence.id == "useful"
    assert coding.latest_evidence.observed_model_name == "model-a-canonical"
    assert any(profile.id == "italian-writing" for profile in result.profiles)

    persisted = json.loads((profiles_dir / "model-a.json").read_text(encoding="utf-8"))
    assert all("latest_evidence" not in profile for profile in persisted["profiles"])


def test_profile_service_persists_workflow_memory_and_preserves_it_on_clone(tmp_path):
    service = ProfileService(
        profiles_dir=tmp_path / "profiles",
        evidence_storage=RunEvidenceStorage(path=tmp_path / "evidence.json"),
    )
    created = service.create_profile(
        "model-a",
        ProfileCreateRequest(
            name="Italian Review",
            description="Review Italian technical prose.",
            intent="Italian Writing",
            notes="Prefer concise terminology.",
            known_caveats=["Verify English API names."],
            runtime_id="lemonade-local",
            config=ProfileConfig(ctx_size=16384, max_tokens=3000, temperature=0.4),
        ),
    )

    updated = service.update_profile(
        "model-a",
        created.id,
        ProfileUpdateRequest(notes="Prefer concise, formal terminology."),
    )
    clone = service.clone_profile("model-a", created.id, "Italian Review Copy")

    assert updated is not None
    assert updated.notes == "Prefer concise, formal terminology."
    assert updated.runtime_id == "lemonade-local"
    assert clone is not None
    assert clone.intent == "Italian Writing"
    assert clone.known_caveats == ["Verify English API names."]
    assert clone.runtime_id == "lemonade-local"

    exported = service.export_profile("model-a", created.id)
    assert exported is not None
    assert exported["profile"]["intent"] == "Italian Writing"
    assert exported["profile"]["latest_evidence"] is None
