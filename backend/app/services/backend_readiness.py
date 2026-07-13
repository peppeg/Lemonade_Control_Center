"""Normalize Lemonade system-info backend state into a stable LCC contract."""
from __future__ import annotations

from typing import Any
from fastapi import HTTPException

from app.models.backend_readiness import (
    BackendInstallResponse,
    BackendReadinessCounts,
    BackendReadinessItem,
    BackendReadinessResponse,
)


STATE_RANK = {
    "update_required": 0,
    "installed": 1,
    "installable": 2,
    "unsupported": 4,
}


def normalize_backend_readiness(system_info: Any) -> BackendReadinessResponse:
    """Return a defensive, typed projection of ``recipes[*].backends``."""
    if not isinstance(system_info, dict):
        return unavailable_backend_readiness("Lemonade system-info was not an object.", status="degraded")

    recipes = system_info.get("recipes")
    if not isinstance(recipes, dict):
        return unavailable_backend_readiness(
            "Lemonade system-info did not include a recipes object.",
            status="degraded",
        )

    items: list[BackendReadinessItem] = []
    for recipe_key, recipe_value in recipes.items():
        if not isinstance(recipe_key, str) or not isinstance(recipe_value, dict):
            continue
        backends = recipe_value.get("backends")
        if not isinstance(backends, dict):
            continue

        recipe_name = _text(recipe_value.get("web_display_name")) or _text(
            recipe_value.get("display_name")
        ) or recipe_key
        experimental = recipe_value.get("experimental") is True

        for backend_key, backend_value in backends.items():
            if not isinstance(backend_key, str):
                continue
            backend = backend_value if isinstance(backend_value, dict) else {}
            items.append(
                BackendReadinessItem(
                    recipe_key=recipe_key,
                    recipe_name=recipe_name,
                    backend_key=backend_key,
                    state=_state(backend.get("state")),
                    version=_optional_text(backend.get("version")),
                    message=_text(backend.get("message")),
                    action=_text(backend.get("action")),
                    devices=_string_list(backend.get("devices")),
                    release_url=_optional_text(backend.get("release_url")),
                    download_filename=_optional_text(backend.get("download_filename")),
                    experimental=experimental,
                )
            )

    items.sort(
        key=lambda item: (
            STATE_RANK.get(item.state, 3),
            item.recipe_name.casefold(),
            item.backend_key.casefold(),
        )
    )
    counts = _counts(items)
    if not items:
        return BackendReadinessResponse(
            status="empty",
            available=True,
            message="Lemonade reported no backend readiness entries.",
            counts=counts,
            items=[],
        )
    return BackendReadinessResponse(
        status="ready",
        available=True,
        counts=counts,
        items=items,
    )


async def collect_backend_readiness(provider: Any) -> BackendReadinessResponse:
    """Fetch authoritative system info through the active Lemonade provider."""
    return normalize_backend_readiness(await provider.get_system_info())


async def install_ready_backend(provider: Any, recipe_key: str, backend_key: str) -> BackendInstallResponse:
    """Install/update only a backend currently advertised as actionable by Lemonade."""
    readiness = await collect_backend_readiness(provider)
    item = next(
        (
            candidate
            for candidate in readiness.items
            if candidate.recipe_key == recipe_key and candidate.backend_key == backend_key
        ),
        None,
    )
    if item is None:
        raise HTTPException(404, "Lemonade did not advertise this recipe/backend pair.")
    if item.state not in {"installable", "update_required"}:
        raise HTTPException(409, f"Backend state '{item.state}' is not installable or updateable.")

    raw = await provider.install_backend(recipe_key, backend_key)
    return BackendInstallResponse(
        success=True,
        recipe_key=recipe_key,
        backend_key=backend_key,
        previous_state=item.state,
        message=(
            f"Updated {recipe_key}:{backend_key}."
            if item.state == "update_required"
            else f"Installed {recipe_key}:{backend_key}."
        ),
        raw=raw,
    )


def unavailable_backend_readiness(
    message: str,
    *,
    status: str = "unavailable",
) -> BackendReadinessResponse:
    normalized_status = status if status in {"degraded", "unavailable"} else "unavailable"
    return BackendReadinessResponse(
        status=normalized_status,
        available=False,
        message=message,
    )


def _counts(items: list[BackendReadinessItem]) -> BackendReadinessCounts:
    counts = BackendReadinessCounts()
    for item in items:
        if item.state == "installed":
            counts.installed += 1
        elif item.state == "update_required":
            counts.update_required += 1
        elif item.state == "installable":
            counts.installable += 1
        elif item.state == "unsupported":
            counts.unsupported += 1
        else:
            counts.other += 1
    return counts


def _state(value: Any) -> str:
    state = _text(value).strip().lower().replace("-", "_").replace(" ", "_")
    return state or "unknown"


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
