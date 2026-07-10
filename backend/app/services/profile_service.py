"""Profile persistence and smart recommendation engine."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.models.profiles import (
    ModelProfiles,
    Profile,
    ProfileConfig,
    ProfileCreateRequest,
    ProfileUpdateRequest,
    SmartRecommendation,
)

PROFILES_DIR = Path(__file__).parent.parent / "data" / "profiles"

BUILTIN_PROFILES = [
    Profile(
        id="safe",
        name="Safe",
        icon="safe",
        description="Conservative settings for reliable loading and moderate output.",
        is_builtin=True,
        is_default=True,
        config=ProfileConfig(ctx_size=8192, global_timeout=300, max_tokens=2000, temperature=0.7),
    ),
    Profile(
        id="coding",
        name="Coding",
        icon="code",
        description="Balanced profile for code generation and terminal-style workflows.",
        is_builtin=True,
        config=ProfileConfig(
            ctx_size=16384,
            global_timeout=600,
            llamacpp_backend="vulkan",
            max_tokens=4000,
            temperature=0.3,
        ),
    ),
    Profile(
        id="long",
        name="Long Context",
        icon="context",
        description="Larger context window for analysis, logs, and long documents.",
        is_builtin=True,
        config=ProfileConfig(ctx_size=32768, global_timeout=900, max_tokens=8000, temperature=0.6),
    ),
    Profile(
        id="stress",
        name="Stress",
        icon="stress",
        description="Aggressive profile for controlled experiments on capable hardware.",
        is_builtin=True,
        config=ProfileConfig(ctx_size=65536, global_timeout=1800, max_tokens=16000, temperature=0.7),
    ),
    Profile(
        id="executor",
        name="Executor Strict",
        icon="executor",
        description="Deterministic profile for automation and local executors.",
        is_builtin=True,
        config=ProfileConfig(ctx_size=16384, global_timeout=600, max_tokens=4000, temperature=0.0),
    ),
]


class ProfileService:
    """Manages per-model profiles stored as JSON files."""

    def __init__(self) -> None:
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    def _file_path(self, model_name: str) -> Path:
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "__", model_name).strip("._-")
        return PROFILES_DIR / f"{safe_name or 'model'}.json"

    def _load(self, model_name: str) -> ModelProfiles:
        path = self._file_path(model_name)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return ModelProfiles(**data)

        model_profiles = ModelProfiles(
            model_name=model_name,
            default_profile_id="safe",
            profiles=[profile.model_copy(deep=True) for profile in BUILTIN_PROFILES],
        )
        self._save(model_profiles)
        return model_profiles

    def _save(self, model_profiles: ModelProfiles) -> None:
        path = self._file_path(model_profiles.model_name)
        path.write_text(model_profiles.model_dump_json(indent=2), encoding="utf-8")

    def list_profiles(self, model_name: str) -> ModelProfiles:
        return self._load(model_name)

    def get_profile(self, model_name: str, profile_id: str) -> Profile | None:
        model_profiles = self._load(model_name)
        return next((profile for profile in model_profiles.profiles if profile.id == profile_id), None)

    def create_profile(self, model_name: str, request: ProfileCreateRequest) -> Profile:
        model_profiles = self._load(model_name)
        slug = self._slugify(request.name)
        base_slug = slug
        counter = 1
        existing_ids = {profile.id for profile in model_profiles.profiles}
        while slug in existing_ids:
            slug = f"{base_slug}-{counter}"
            counter += 1

        profile = Profile(
            id=slug,
            name=request.name,
            description=request.description,
            icon=request.icon,
            config=request.config,
        )
        model_profiles.profiles.append(profile)
        self._save(model_profiles)
        return profile

    def update_profile(
        self,
        model_name: str,
        profile_id: str,
        request: ProfileUpdateRequest,
    ) -> Profile | None:
        model_profiles = self._load(model_name)
        profile = next((item for item in model_profiles.profiles if item.id == profile_id), None)
        if profile is None:
            return None

        if request.name is not None:
            profile.name = request.name
        if request.description is not None:
            profile.description = request.description
        if request.icon is not None:
            profile.icon = request.icon
        if request.config is not None:
            profile.config = request.config
        if request.is_default is True:
            for item in model_profiles.profiles:
                item.is_default = False
            profile.is_default = True
            model_profiles.default_profile_id = profile.id

        profile.updated_at = datetime.now(timezone.utc)
        self._save(model_profiles)
        return profile

    def delete_profile(self, model_name: str, profile_id: str) -> bool:
        model_profiles = self._load(model_name)
        profile = next((item for item in model_profiles.profiles if item.id == profile_id), None)
        if profile is None or profile.is_builtin:
            return False

        model_profiles.profiles = [item for item in model_profiles.profiles if item.id != profile_id]
        if model_profiles.default_profile_id == profile_id:
            model_profiles.default_profile_id = "safe"
            for item in model_profiles.profiles:
                item.is_default = item.id == "safe"
        self._save(model_profiles)
        return True

    def clone_profile(self, model_name: str, profile_id: str, new_name: str) -> Profile | None:
        source = self.get_profile(model_name, profile_id)
        if source is None:
            return None
        return self.create_profile(
            model_name,
            ProfileCreateRequest(
                name=new_name,
                description=f"Cloned from {source.name}",
                icon=source.icon,
                config=source.config.model_copy(deep=True),
            ),
        )

    def set_default(self, model_name: str, profile_id: str) -> bool:
        request = ProfileUpdateRequest(is_default=True)
        return self.update_profile(model_name, profile_id, request) is not None

    def export_profile(self, model_name: str, profile_id: str) -> dict | None:
        profile = self.get_profile(model_name, profile_id)
        if profile is None:
            return None
        return {
            "lcc_profile_version": 1,
            "model_name": model_name,
            "profile": profile.model_dump(mode="json"),
        }

    def import_profile(self, model_name: str, data: dict) -> Profile | None:
        try:
            profile_data = data.get("profile", data)
            return self.create_profile(
                model_name,
                ProfileCreateRequest(
                    name=str(profile_data.get("name", "Imported Profile")),
                    description=str(profile_data.get("description", "Imported profile")),
                    icon=str(profile_data.get("icon", "profile")),
                    config=ProfileConfig(**profile_data.get("config", {})),
                ),
            )
        except (TypeError, ValueError):
            return None

    def compute_recommendation(
        self,
        model_name: str,
        model_size_gb: float | None,
        ram_total_gb: float,
        ram_available_gb: float,
        model_loaded: bool = False,
        loaded_model_rss_gb: float | None = None,
    ) -> SmartRecommendation:
        warnings: list[str] = []
        notes: list[str] = []
        model_gb = model_size_gb or 0

        reserved_system_gb = max(8.0, ram_total_gb * 0.12)
        recoverable_active_model_gb = loaded_model_rss_gb if model_loaded and loaded_model_rss_gb else 0
        planning_headroom_gb = max(0, ram_available_gb + recoverable_active_model_gb - reserved_system_gb)
        ram_after_model = planning_headroom_gb - model_gb

        if model_gb <= 0:
            notes.append("Model size is unknown. Recommendations use RAM-only estimates.")
        if ram_after_model < 0:
            if model_loaded:
                warnings.append(
                    f"Model plus reserved system overhead exceeds the current planning headroom "
                    f"({model_gb:.1f} GB model, {planning_headroom_gb:.1f} GB headroom)."
                )
            else:
                warnings.append(
                    f"Cold-load estimate exceeds current headroom "
                    f"({model_gb:.1f} GB model, {planning_headroom_gb:.1f} GB headroom). "
                    "Unload the active model or close other workloads before loading."
                )
            ram_after_model = 0
        if model_gb > ram_total_gb * 0.6:
            notes.append("This model occupies more than 60% of total RAM. Keep other workloads low.")
        if model_loaded:
            notes.append(
                "This model is already loaded. Recommendations account for the active llama-server process as recoverable memory."
            )

        gb_per_8k = 1.0
        if model_gb > 60:
            gb_per_8k = 1.5
        elif 0 < model_gb < 10:
            gb_per_8k = 0.3

        usable_for_kv = max(0, ram_after_model - 4.0)
        recommended_ctx = self._ctx_from_kv_budget(usable_for_kv, gb_per_8k, 131072)
        safe_max_ctx = self._ctx_from_kv_budget(ram_after_model * 0.9, gb_per_8k, 131072)
        risk_threshold_ctx = self._ctx_from_kv_budget(ram_after_model, gb_per_8k, 262144)

        if recommended_ctx < 8192:
            warnings.append("Limited RAM headroom for additional KV cache. Use a small context window.")
        if risk_threshold_ctx <= safe_max_ctx:
            warnings.append("Safe and risk thresholds are close. Avoid stress profiles for this model.")

        return SmartRecommendation(
            model_name=model_name,
            model_size_gb=model_size_gb,
            model_loaded=model_loaded,
            ram_total_gb=round(ram_total_gb, 1),
            ram_available_gb=round(ram_available_gb, 1),
            planning_headroom_gb=round(planning_headroom_gb, 1),
            reserved_system_gb=round(reserved_system_gb, 1),
            recommended_ctx=recommended_ctx,
            safe_max_ctx=safe_max_ctx,
            risk_threshold_ctx=risk_threshold_ctx,
            warnings=warnings,
            notes=notes,
        )

    def _ctx_from_kv_budget(self, budget_gb: float, gb_per_8k: float, cap: int) -> int:
        ctx_k = int(max(0, budget_gb) / gb_per_8k * 8)
        rounded = max(2048, min(ctx_k * 1024, cap))
        return int(rounded)

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "profile"
