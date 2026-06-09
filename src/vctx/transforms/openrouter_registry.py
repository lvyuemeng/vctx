from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from urllib.request import Request, urlopen

from vctx.transforms.model_resolution import OpenRouterModel

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_CACHE_KEY = "openrouter/models.json"


def load_openrouter_models(cache_root: Path, *, offline: bool) -> list[OpenRouterModel]:
    cache_path = cache_root / OPENROUTER_CACHE_KEY
    cached = _read_cached_models(cache_path)
    if cached is not None:
        return cached
    if offline:
        return []
    payload = _fetch_openrouter_models()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return _parse_openrouter_models(payload)


def _read_cached_models(cache_path: Path) -> list[OpenRouterModel] | None:
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return _parse_openrouter_models(payload)


def _fetch_openrouter_models() -> dict[str, Any]:
    request = Request(
        OPENROUTER_MODELS_URL,
        headers={"Accept": "application/json", "User-Agent": "vctx"},
        method="GET",
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return cast(dict[str, Any], payload if isinstance(payload, dict) else {"data": []})


def _parse_openrouter_models(payload: dict[str, Any]) -> list[OpenRouterModel]:
    raw_models = payload.get("data", [])
    if not isinstance(raw_models, list):
        return []
    models: list[OpenRouterModel] = []
    for raw_model in raw_models:
        if not isinstance(raw_model, dict):
            continue
        try:
            models.append(OpenRouterModel.model_validate(raw_model))
        except ValueError:
            continue
    return models
