from __future__ import annotations

from pathlib import Path

from vctx.app.config import CapabilityEnabled, PrepareRequest, resolve_config
from vctx.transforms.planning import (
    SourceState,
    TransformEnvironment,
    plan_asr,
    plan_visual_context,
)


def test_resolve_config_missing_fields_become_default_auto(tmp_path: Path) -> None:
    request = PrepareRequest(input="lecture.srt", out_dir=tmp_path / "out")

    resolved = resolve_config(request)

    assert resolved.runtime.auto is True
    assert resolved.runtime.offline is False
    assert resolved.source.preferred_language is None
    assert resolved.transforms.asr.enabled == CapabilityEnabled.AUTO
    assert resolved.transforms.asr.route == "auto"
    assert resolved.transforms.asr.allow_network is True
    assert resolved.transforms.asr.allow_upload is True
    assert resolved.transforms.asr.allow_paid is False
    assert resolved.transforms.visual_context.enabled == CapabilityEnabled.AUTO
    assert resolved.output.chunk_max_chars == 6000


def test_offline_request_disables_network_routes(tmp_path: Path) -> None:
    request = PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out", offline=True)

    resolved = resolve_config(request)

    assert resolved.runtime.offline is True
    assert resolved.transforms.asr.allow_network is False
    assert resolved.transforms.asr.allow_upload is False
    assert resolved.transforms.visual_context.allow_network is False


def test_plan_asr_missing_everything_returns_actionable_unavailable(tmp_path: Path) -> None:
    request = PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out")
    resolved = resolve_config(request)
    environment = TransformEnvironment()
    source = SourceState(has_transcript=False, has_media=True)

    plan = plan_asr(resolved.transforms.asr, environment, source)

    assert plan.selected == "unavailable"
    assert "ASR extra not installed" in plan.reason
    assert "no configured ASR provider" in plan.reason
    assert plan.evidence_seed.requires_user_config is False


def test_plan_asr_skips_when_transcript_exists(tmp_path: Path) -> None:
    request = PrepareRequest(input="lecture.srt", out_dir=tmp_path / "out")
    resolved = resolve_config(request)
    environment = TransformEnvironment(installed_asr=True)
    source = SourceState(has_transcript=True, has_media=False)

    plan = plan_asr(resolved.transforms.asr, environment, source)

    assert plan.selected == "skipped"
    assert plan.reason == "transcript already available"


def test_visual_context_prefers_free_online_for_vlm_when_local_ocr_is_not_suitable(
    tmp_path: Path,
) -> None:
    request = PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out")
    resolved = resolve_config(request)
    environment = TransformEnvironment(
        installed_ocr=True,
        network_available=True,
        free_online_vision=True,
    )
    source = SourceState(has_transcript=True, has_media=True, visual_need="description")

    plan = plan_visual_context(resolved.transforms.visual_context, environment, source)

    assert plan.selected == "free-online"
    assert plan.provider_id == "free-online-vision"
    assert "visual description" in plan.reason
