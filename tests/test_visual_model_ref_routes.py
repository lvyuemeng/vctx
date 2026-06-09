from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from vctx.app.config import CapabilityEnabled, CapabilityPolicy, ProviderConfig
from vctx.models.common import SourceRef
from vctx.models.media import MediaAsset
from vctx.models.visual import FrameAsset
from vctx.transforms.model_resolution import (
    OpenRouterModel,
    OpenRouterModelArchitecture,
    OpenRouterModelPricing,
)
from vctx.transforms.visual_execute import run_visual_context
from vctx.transforms.visual_planning import AcquisitionAction, Evidence, VisualAssessment
from vctx.transforms.visual_routes import discover_visual_operations


def test_openrouter_prefix_model_discovers_describe_operation_without_provider_block() -> None:
    operations = discover_visual_operations(
        CapabilityPolicy(
            enabled=CapabilityEnabled.TRUE,
            model="openrouter:nex-agi/nex-n2-pro:free",
            allow_network=True,
            allow_upload=True,
        ),
        env={"OPENROUTER_API_KEY": "present"},
    )

    describe = next(operation for operation in operations if operation.name == "describe")

    assert describe.route == "free-online"
    assert describe.provider_id == "openrouter:nex-agi/nex-n2-pro:free"
    assert describe.params["model"] == "nex-agi/nex-n2-pro:free"
    assert describe.params["base_url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert describe.params["api_key_env"] == "OPENROUTER_API_KEY"
    assert describe.params["provider_type"] == "openai-compatible-vision"


def test_auto_model_discovers_free_openrouter_vlm_from_registry_metadata() -> None:
    operations = discover_visual_operations(
        CapabilityPolicy(
            enabled=CapabilityEnabled.TRUE,
            model="auto",
            allow_network=True,
            allow_upload=True,
        ),
        env={"OPENROUTER_API_KEY": "present"},
        openrouter_models=[
            OpenRouterModel(
                id="text-only/free:free",
                architecture=OpenRouterModelArchitecture(
                    input_modalities=["text"], output_modalities=["text"]
                ),
                pricing=OpenRouterModelPricing(prompt="0", completion="0"),
            ),
            OpenRouterModel(
                id="nex-agi/nex-n2-pro:free",
                architecture=OpenRouterModelArchitecture(
                    input_modalities=["text", "image"], output_modalities=["text"]
                ),
                pricing=OpenRouterModelPricing(prompt="0", completion="0"),
            ),
        ],
    )

    describe = next(operation for operation in operations if operation.name == "describe")

    assert describe.provider_id == "openrouter:nex-agi/nex-n2-pro:free"
    assert describe.params["cost"] == "free"


def test_provider_alias_still_takes_precedence_over_prefix_auto() -> None:
    operations = discover_visual_operations(
        CapabilityPolicy(
            enabled=CapabilityEnabled.TRUE,
            route="configured-online",
            preferred_provider="test-vlm",
            model="auto",
            allow_network=True,
            allow_upload=True,
        ),
        vision_providers={
            "test-vlm": ProviderConfig(
                type="openai-compatible-vision",
                base_url="https://example.invalid/v1/chat/completions",
                api_key_env="VISION_KEY",
                model="vision-test",
                cost_mode="free",
            )
        },
        env={"OPENROUTER_API_KEY": "present"},
    )

    describe = next(operation for operation in operations if operation.name == "describe")

    assert describe.provider_id == "test-vlm"
    assert "base_url" not in describe.params


def test_visual_execution_materializes_prefix_resolved_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import vctx.transforms.visual_frames as visual_frames_module
    import vctx.transforms.visual_vlm as visual_vlm_module

    media_path = tmp_path / "lecture.mp4"
    media_path.write_bytes(b"fake video")
    frame_path = tmp_path / "visual" / "frames" / "frame-0001.png"

    def fake_extract_frames(
        media_asset: MediaAsset,
        action: AcquisitionAction,
        frames_dir: Path,
    ) -> list[FrameAsset]:
        del media_asset, action
        frames_dir.mkdir(parents=True, exist_ok=True)
        frame_path.write_bytes(b"fake png")
        return [
            FrameAsset(
                id="frame-0001",
                timestamp_seconds=12.0,
                path=frame_path,
                source="transcript_anchor",
                evidence=[Evidence(kind="transcript", name="diagram", weight=0.9)],
            )
        ]

    seen: dict[str, str | None] = {}

    def fake_describe(self: object, frame: FrameAsset) -> str:
        del frame
        provider = cast(Any, self).provider
        seen["base_url"] = provider.base_url
        seen["api_key_env"] = provider.api_key_env
        seen["model"] = provider.model
        return "A remote VLM description."

    monkeypatch.setattr(visual_frames_module, "extract_frames", fake_extract_frames)
    monkeypatch.setattr(
        visual_vlm_module.OpenAiCompatibleVisionAdapter,
        "describe",
        fake_describe,
    )

    records = run_visual_context(
        VisualAssessment(
            visual_yield=0.8,
            audio_sufficiency=0.2,
            rationale="test",
            recipe=[
                AcquisitionAction(name="sample", params={"strategy": "cover", "budget": 1}),
                AcquisitionAction(
                    name="describe",
                    params={
                        "provider_id": "openrouter:nex-agi/nex-n2-pro:free",
                        "provider_type": "openai-compatible-vision",
                        "base_url": "https://openrouter.ai/api/v1/chat/completions",
                        "api_key_env": "OPENROUTER_API_KEY",
                        "model": "nex-agi/nex-n2-pro:free",
                    },
                ),
            ],
        ),
        MediaAsset(
            id="media-1",
            source=SourceRef(kind="file", value=str(media_path)),
            local_path=media_path,
            media_type="video",
        ),
        tmp_path,
        vision_providers={},
        env_files=[],
    )

    assert records.records[0].text == "A remote VLM description."
    assert seen == {
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "api_key_env": "OPENROUTER_API_KEY",
        "model": "nex-agi/nex-n2-pro:free",
    }
