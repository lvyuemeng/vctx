from __future__ import annotations

from vctx.models.transcript import Transcript, TranscriptProvenance, TranscriptSegment
from vctx.transforms.visual_cases import (
    EssentialVisualCase,
    dedupe_cases_by_window,
    deterministic_essential_cases,
)
from vctx.transforms.visual_planning import (
    VisualOperation,
    VisualSourceSignals,
    plan_visual_acquisition,
)


def _transcript(*segments: TranscriptSegment) -> Transcript:
    return Transcript(
        video_id="video-1",
        provenance=TranscriptProvenance(method="local_file", format="json"),
        segments=list(segments),
    )


def test_deterministic_essential_cases_extracts_visual_transcript_cues() -> None:
    cases = deterministic_essential_cases(
        _transcript(
            TranscriptSegment(
                id="seg_000001",
                start=10.0,
                end=14.0,
                text="This architecture diagram shows the request flow.",
            ),
            TranscriptSegment(
                id="seg_000002",
                start=30.0,
                end=35.0,
                text="Now derive the formula shown on the slide.",
            ),
            TranscriptSegment(
                id="seg_000003",
                start=60.0,
                end=62.0,
                text="This part is spoken explanation only.",
            ),
        )
    )

    assert [(case.segment_id, case.case_type, case.timestamp_seconds) for case in cases] == [
        ("seg_000001", "diagram", 12.0),
        ("seg_000002", "formula", 32.5),
    ]
    assert cases[0].actions == ["describe", "capture"]
    assert cases[1].actions == ["ocr", "describe", "capture"]
    assert "architecture diagram" in cases[0].reason


def test_dedupe_cases_by_window_keeps_highest_priority_nearby_case() -> None:
    cases = [
        EssentialVisualCase(
            segment_id="low",
            timestamp_seconds=101.0,
            case_type="screen_demo",
            priority=0.5,
            reason="nearby lower priority",
            actions=["ocr", "capture"],
        ),
        EssentialVisualCase(
            segment_id="high",
            timestamp_seconds=100.0,
            case_type="diagram",
            priority=0.9,
            reason="nearby higher priority",
            actions=["describe", "capture"],
        ),
        EssentialVisualCase(
            segment_id="far",
            timestamp_seconds=125.0,
            case_type="table",
            priority=0.7,
            reason="far enough",
            actions=["ocr", "capture"],
        ),
    ]

    selected = dedupe_cases_by_window(cases, min_gap_s=8.0, budget=10)

    assert [case.segment_id for case in selected] == ["high", "far"]


def test_visual_plan_uses_essential_cases_as_sampling_anchors() -> None:
    assessment = plan_visual_acquisition(
        VisualSourceSignals(
            has_video=True,
            duration_seconds=900,
            transcript_timestamps=True,
            operations=[
                VisualOperation(name="sample"),
                VisualOperation(name="describe"),
                VisualOperation(name="capture"),
            ],
            essential_cases=[
                EssentialVisualCase(
                    segment_id="seg_000001",
                    timestamp_seconds=12.0,
                    case_type="diagram",
                    priority=0.9,
                    reason="diagram referenced by transcript",
                    actions=["describe", "capture"],
                )
            ],
        )
    )

    sample = assessment.recipe[0]
    assert sample.name == "sample"
    assert sample.params["strategy"] == "essential_cases"
    assert sample.params["budget"] == 1
    assert sample.params["min_gap_s"] == 8
    assert sample.params["cases"] == [
        {
            "segment_id": "seg_000001",
            "timestamp_seconds": 12.0,
            "case_type": "diagram",
            "priority": 0.9,
            "reason": "diagram referenced by transcript",
            "actions": ["describe", "capture"],
        }
    ]
    assert [action.name for action in assessment.recipe] == ["sample", "describe", "capture"]
