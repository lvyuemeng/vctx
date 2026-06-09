from __future__ import annotations

from vctx.transforms.visual_planning import VisualSourceSignals, plan_visual_acquisition


def test_visual_acquisition_skips_podcast_like_video() -> None:
    plan = plan_visual_acquisition(
        VisualSourceSignals(
            has_video=True,
            title="Long-form AI Podcast interview",
            duration_seconds=5400,
            transcript_available=True,
            transcript_timestamps=True,
            motion_hint="low",
            text_density_hint="low",
        )
    )

    assert plan.useful is False
    assert plan.content_class == "podcast"
    assert plan.sampling_strategy == "sparse_cover"
    assert plan.extraction_intents == ["capture"]
    assert plan.target_frame_count == 1


def test_visual_acquisition_uses_hybrid_ocr_for_slide_lecture() -> None:
    plan = plan_visual_acquisition(
        VisualSourceSignals(
            has_video=True,
            title="Distributed systems lecture with slides",
            duration_seconds=3600,
            transcript_available=True,
            transcript_timestamps=True,
            text_density_hint="high",
            motion_hint="low",
        )
    )

    assert plan.useful is True
    assert plan.content_class == "slides"
    assert plan.sampling_strategy == "hybrid"
    assert plan.extraction_intents == ["ocr", "capture"]
    assert plan.align_to_transcript is True
    assert plan.prefer_keyframes is True
    assert plan.deduplicate_near_identical is True
    assert plan.target_frame_count == 40
    assert plan.min_interval_seconds == 8


def test_visual_acquisition_preserves_images_for_diagrams_and_formulas() -> None:
    plan = plan_visual_acquisition(
        VisualSourceSignals(
            has_video=True,
            content_hint="formula",
            duration_seconds=900,
            transcript_timestamps=True,
        )
    )

    assert plan.useful is True
    assert plan.content_class == "formula"
    assert plan.sampling_strategy == "hybrid"
    assert plan.extraction_intents == ["ocr", "describe", "capture"]
    assert plan.target_frame_count == 15
    assert plan.align_to_transcript is True
    assert plan.warnings == [
        "diagram/formula interpretation is model output; keep source frame references"
    ]


def test_visual_acquisition_uses_descriptions_for_scenery() -> None:
    plan = plan_visual_acquisition(
        VisualSourceSignals(
            has_video=True,
            content_hint="scenery",
            duration_seconds=1800,
            motion_hint="high",
            text_density_hint="low",
        )
    )

    assert plan.useful is True
    assert plan.sampling_strategy == "scene_change"
    assert plan.extraction_intents == ["describe", "capture"]
    assert plan.target_frame_count == 10
    assert plan.align_to_transcript is False


def test_visual_acquisition_unknown_mixed_uses_conservative_hybrid() -> None:
    plan = plan_visual_acquisition(
        VisualSourceSignals(
            has_video=True,
            duration_seconds=None,
            transcript_timestamps=True,
            text_density_hint="unknown",
            motion_hint="unknown",
        )
    )

    assert plan.useful is True
    assert plan.content_class == "mixed"
    assert plan.sampling_strategy == "hybrid"
    assert plan.extraction_intents == ["ocr", "describe", "capture"]
    assert plan.target_frame_count == 4
    assert plan.align_to_transcript is True
