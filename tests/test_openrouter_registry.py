from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from vctx.transforms.openrouter_registry import load_openrouter_models


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_load_openrouter_models_fetches_and_writes_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    requests: list[str] = []

    def fake_urlopen(request: object, timeout: float) -> _FakeResponse:
        del timeout
        requests.append(cast(Any, request).full_url)
        return _FakeResponse(
            {
                "data": [
                    {
                        "id": "nex-agi/nex-n2-pro:free",
                        "architecture": {
                            "input_modalities": ["text", "image"],
                            "output_modalities": ["text"],
                        },
                        "pricing": {"prompt": "0", "completion": "0"},
                    }
                ]
            }
        )

    monkeypatch.setattr("vctx.transforms.openrouter_registry.urlopen", fake_urlopen)

    models = load_openrouter_models(tmp_path, offline=False)

    assert [model.id for model in models] == ["nex-agi/nex-n2-pro:free"]
    assert requests == ["https://openrouter.ai/api/v1/models"]
    cached = json.loads((tmp_path / "openrouter" / "models.json").read_text())
    assert cached["data"][0]["id"] == "nex-agi/nex-n2-pro:free"


def test_load_openrouter_models_uses_cached_registry_without_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache_file = tmp_path / "openrouter" / "models.json"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text(
        json.dumps(
            {
                "data": [
                    {
                        "id": "cached/vision:free",
                        "architecture": {
                            "input_modalities": ["text", "image"],
                            "output_modalities": ["text"],
                        },
                        "pricing": {"prompt": "0", "completion": "0"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def fail_urlopen(*args: object, **kwargs: object) -> Iterator[bytes]:
        del args, kwargs
        raise AssertionError("network should not be used when cache exists")

    monkeypatch.setattr("vctx.transforms.openrouter_registry.urlopen", fail_urlopen)

    models = load_openrouter_models(tmp_path, offline=True)

    assert [model.id for model in models] == ["cached/vision:free"]


def test_load_openrouter_models_returns_empty_on_offline_cache_miss(tmp_path: Path) -> None:
    assert load_openrouter_models(tmp_path, offline=True) == []
