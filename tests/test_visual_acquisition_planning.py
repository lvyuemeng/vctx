from __future__ import annotations

from vctx.transforms.visual_planning import (
    Evidence,
    VisualAssessment,
    VisualSourceSignals,
    plan_visual_acquisition,
)


def _action_names(assessment: VisualAssessment) -> list[str]:
    return [action.name for action in assessment.recipe]


def test_visual_assessment_is_a_compact_score_and_recipe_contract() -> None:
    assessment = plan_visual_acquisition(
        VisualSourceSignals(
            has_video=True,
            title="Distributed systems lecture with slides",
            duration_seconds=3600,
            transcript_timestamps=True,
            evidence=[
                Evidence(kind="transcript", name="visual-reference", weight=0.4),
                Evidence(kind="frame", name="dense-text", weight=0.7),
                Evidence(kind="frame", name="low-motion", weight=0.2),
            ],
        )
    )

    assert assessment.visual_yield >= 0.8
    assert assessment.audio_sufficiency <= 0.2
    assert _action_names(assessment) == ["sample", "ocr", "capture"]
    assert assessment.recipe[0].params == {
        "strategy": "changes+anchors",
        "budget": 40,
        "min_gap_s": 8,
    }


def test_audio_sufficient_sources_keep_only_a_cover_capture() -> None:
    assessment = plan_visual_acquisition(
        VisualSourceSignals(
            has_video=True,
            title="Long-form podcast interview",
            duration_seconds=5400,
            evidence=[
                Evidence(kind="transcript", name="audio-complete", weight=0.8),
                Evidence(kind="frame", name="low-text", weight=0.5),
                Evidence(kind="frame", name="low-change", weight=0.4),
            ],
        )
    )

    assert assessment.visual_yield == 0.0
    assert assessment.audio_sufficiency >= 0.9
    assert _action_names(assessment) == ["sample", "capture"]
    assert assessment.recipe[0].params == {"strategy": "cover", "budget": 1}


def test_diagram_formula_evidence_composes_ocr_description_and_capture() -> None:
    assessment = plan_visual_acquisition(
        VisualSourceSignals(
            has_video=True,
            duration_seconds=900,
            transcript_timestamps=True,
            evidence=[
                Evidence(kind="transcript", name="formula-reference", weight=0.7),
                Evidence(kind="frame", name="layout-heavy", weight=0.8),
                Evidence(kind="frame", name="dense-text", weight=0.3),
            ],
        )
    )

    assert assessment.visual_yield >= 0.9
    assert _action_names(assessment) == ["sample", "ocr", "describe", "capture"]
    assert assessment.recipe[0].params == {
        "strategy": "changes+anchors",
        "budget": 15,
        "min_gap_s": 5,
    }
    assert assessment.cautions == ["description is model output; keep source frames"]


def test_no_video_has_empty_recipe_without_extra_triggers() -> None:
    assessment = plan_visual_acquisition(
        VisualSourceSignals(
            has_video=False,
            evidence=[Evidence(kind="transcript", name="audio-complete", weight=1.0)],
        )
    )

    assert assessment.visual_yield == 0.0
    assert assessment.recipe == []
    assert assessment.evidence[0].name == "audio-complete"
