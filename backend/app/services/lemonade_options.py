"""Read Lemonade's official saved per-model load options."""
from __future__ import annotations

import json
from pathlib import Path

from app.config import settings
from app.models.schemas import LemonadeSavedOptionsResponse


def read_saved_options(model_name: str | None = None) -> LemonadeSavedOptionsResponse:
    """Read recipe_options.json and optionally select the entry for one model."""
    path = Path(settings.lemonade_recipe_options_file)
    if not path.exists():
        return LemonadeSavedOptionsResponse(
            available=False,
            path=str(path),
            model_name=model_name,
            error="recipe_options.json not found",
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return LemonadeSavedOptionsResponse(
            available=False,
            path=str(path),
            model_name=model_name,
            error=str(exc),
        )

    options = {str(key): value for key, value in raw.items() if isinstance(value, dict)}
    selected_key = _find_model_key(options, model_name) if model_name else None

    return LemonadeSavedOptionsResponse(
        available=True,
        path=str(path),
        options=options,
        model_name=model_name,
        selected_key=selected_key,
        selected_options=options.get(selected_key) if selected_key else None,
    )


def _find_model_key(options: dict[str, dict], model_name: str | None) -> str | None:
    if not model_name:
        return None

    candidates = [
        model_name,
        f"builtin.{model_name}",
    ]

    if model_name.startswith("builtin."):
        candidates.append(model_name.removeprefix("builtin."))

    if ":" in model_name:
        without_tag = model_name.split(":", 1)[0]
        candidates.extend([without_tag, f"builtin.{without_tag}"])

    for candidate in candidates:
        if candidate in options:
            return candidate

    normalized = _normalize_model_name(model_name)
    for key in options:
        if _normalize_model_name(key).endswith(normalized) or normalized.endswith(_normalize_model_name(key)):
            return key

    return None


def _normalize_model_name(value: str) -> str:
    return value.removeprefix("builtin.").replace(":", "-").lower()
