from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

EvidenceKind = Literal["metadata", "transcript", "frame", "probe"]
ActionName = Literal["sample", "ocr", "describe", "capture"]


class Evidence(BaseModel):
    kind: EvidenceKind
    name: str
    weight: float = 1.0

    @field_validator("weight")
    @classmethod
    def clamp_weight(cls, value: float) -> float:
        return _clamp(value)


class VisualSourceSignals(BaseModel):
    has_video: bool = False
    duration_seconds: float | None = None
    title: str | None = None
    description: str | None = None
    transcript_timestamps: bool = False
    evidence: list[Evidence] = Field(default_factory=list)


class AcquisitionAction(BaseModel):
    name: ActionName
    params: dict[str, Any] = Field(default_factory=dict)


class VisualAssessment(BaseModel):
    visual_yield: float
    audio_sufficiency: float
    recipe: list[AcquisitionAction] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    rationale: str
    cautions: list[str] = Field(default_factory=list)


def plan_visual_acquisition(signals: VisualSourceSignals) -> VisualAssessment:
    evidence = _with_textual_evidence(signals)
    audio = _audio_sufficiency(evidence)
    visual = 0.0 if not signals.has_video else _visual_yield(evidence, audio)

    if not signals.has_video:
        return VisualAssessment(
            visual_yield=0.0,
            audio_sufficiency=audio,
            recipe=[],
            evidence=evidence,
            rationale="no video stream is available",
        )

    if visual <= 0.15 and audio >= 0.75:
        return VisualAssessment(
            visual_yield=0.0,
            audio_sufficiency=audio,
            recipe=[
                AcquisitionAction(name="sample", params={"strategy": "cover", "budget": 1}),
                AcquisitionAction(name="capture"),
            ],
            evidence=evidence,
            rationale="audio is sufficient; keep only a visual provenance cover",
        )

    recipe = [
        AcquisitionAction(
            name="sample",
            params=_sample_params(signals, evidence),
        )
    ]
    recipe.extend(_extraction_actions(evidence))

    cautions = []
    if _score(evidence, {"layout-heavy", "formula-reference", "diagram-reference"}) > 0:
        cautions.append("description is model output; keep source frames")

    return VisualAssessment(
        visual_yield=visual,
        audio_sufficiency=audio,
        recipe=recipe,
        evidence=evidence,
        rationale="visual evidence contributes source information beyond the transcript",
        cautions=cautions,
    )


def _with_textual_evidence(signals: VisualSourceSignals) -> list[Evidence]:
    evidence = list(signals.evidence)
    text = " ".join(part.lower() for part in (signals.title, signals.description) if part)
    derived: list[tuple[str, float]] = []
    if any(token in text for token in ("podcast", "interview", "audio only")):
        derived.append(("audio-complete", 0.7))
    if any(token in text for token in ("lecture", "slides", "presentation", "ppt")):
        derived.extend([("dense-text", 0.5), ("visual-reference", 0.3)])
    if any(token in text for token in ("screen", "demo", "coding", "walkthrough")):
        derived.extend([("screen-content", 0.6), ("dense-text", 0.3)])
    if any(token in text for token in ("diagram", "architecture", "flowchart", "graph")):
        derived.append(("diagram-reference", 0.7))
    if any(token in text for token in ("formula", "equation", "proof", "derivation")):
        derived.append(("formula-reference", 0.7))
    evidence.extend(Evidence(kind="metadata", name=name, weight=weight) for name, weight in derived)
    return evidence


def _audio_sufficiency(evidence: list[Evidence]) -> float:
    return _clamp(
        0.15
        + _score(evidence, {"audio-complete"})
        + 0.2 * _score(evidence, {"low-text", "low-change"})
        - 0.4 * _score(
            evidence,
            {
                "visual-reference",
                "dense-text",
                "layout-heavy",
                "diagram-reference",
                "formula-reference",
                "screen-content",
            },
        )
    )


def _visual_yield(evidence: list[Evidence], audio_sufficiency: float) -> float:
    positive = _score(
        evidence,
        {
            "visual-reference",
            "dense-text",
            "layout-heavy",
            "diagram-reference",
            "formula-reference",
            "screen-content",
        },
    )
    negative = 0.7 * _score(evidence, {"low-text", "low-change", "audio-complete"})
    return _clamp(0.15 + positive - negative - 0.2 * audio_sufficiency)


def _sample_params(
    signals: VisualSourceSignals, evidence: list[Evidence]
) -> dict[str, int | float | str]:
    strategy = "changes+anchors" if signals.transcript_timestamps else "changes"
    min_gap = 5 if _score(evidence, {"layout-heavy", "formula-reference"}) > 0 else 8
    seconds_per_frame = 60 if min_gap == 5 else 90
    return {
        "strategy": strategy,
        "budget": _target_frames(
            signals.duration_seconds,
            seconds_per_frame=seconds_per_frame,
            minimum=6 if min_gap == 8 else 8,
            maximum=80 if min_gap == 8 else 100,
        ),
        "min_gap_s": min_gap,
    }


def _extraction_actions(evidence: list[Evidence]) -> list[AcquisitionAction]:
    actions: list[AcquisitionAction] = []
    if _score(evidence, {"dense-text", "screen-content", "layout-heavy"}) > 0:
        actions.append(AcquisitionAction(name="ocr"))
    if _score(evidence, {"layout-heavy", "diagram-reference", "formula-reference"}) > 0:
        actions.append(AcquisitionAction(name="describe"))
    actions.append(AcquisitionAction(name="capture"))
    return actions


def _score(evidence: list[Evidence], names: set[str]) -> float:
    return _clamp(sum(item.weight for item in evidence if item.name in names))


def _target_frames(
    duration_seconds: float | None, *, seconds_per_frame: int, minimum: int, maximum: int
) -> int:
    if duration_seconds is None or duration_seconds <= 0:
        return minimum
    estimated = round(duration_seconds / seconds_per_frame)
    return min(max(estimated, minimum), maximum)


def _clamp(value: float) -> float:
    return round(min(max(value, 0.0), 1.0), 3)
