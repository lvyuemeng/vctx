from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

VisualContentClass = Literal[
    "unknown",
    "podcast",
    "talking_head",
    "slides",
    "screen_demo",
    "diagram",
    "formula",
    "scenery",
    "mixed",
]
VisualExtractionIntent = Literal["ocr", "describe", "capture"]
VisualSamplingStrategy = Literal[
    "none",
    "sparse_cover",
    "transcript_aligned",
    "scene_change",
    "fixed_interval",
    "hybrid",
]


class VisualSourceSignals(BaseModel):
    has_video: bool = False
    duration_seconds: float | None = None
    title: str | None = None
    description: str | None = None
    transcript_available: bool = False
    transcript_timestamps: bool = False
    speech_density: float | None = None
    text_density_hint: Literal["unknown", "low", "medium", "high"] = "unknown"
    motion_hint: Literal["unknown", "low", "medium", "high"] = "unknown"
    scene_change_hint: Literal["unknown", "low", "medium", "high"] = "unknown"
    content_hint: VisualContentClass = "unknown"


class VisualAcquisitionPlan(BaseModel):
    useful: bool
    content_class: VisualContentClass
    sampling_strategy: VisualSamplingStrategy
    extraction_intents: list[VisualExtractionIntent] = Field(default_factory=list)
    target_frame_count: int = 0
    min_interval_seconds: float | None = None
    align_to_transcript: bool = False
    prefer_keyframes: bool = True
    deduplicate_near_identical: bool = True
    reason: str
    warnings: list[str] = Field(default_factory=list)


def plan_visual_acquisition(signals: VisualSourceSignals) -> VisualAcquisitionPlan:
    if not signals.has_video:
        return VisualAcquisitionPlan(
            useful=False,
            content_class="unknown",
            sampling_strategy="none",
            reason="no video stream is available",
        )

    content_class = _infer_content_class(signals)
    if content_class == "podcast":
        return VisualAcquisitionPlan(
            useful=False,
            content_class=content_class,
            sampling_strategy="sparse_cover",
            extraction_intents=["capture"],
            target_frame_count=1,
            min_interval_seconds=None,
            reason=(
                "podcast-like source; audio/transcript is expected to carry "
                "almost all information"
            ),
        )

    if content_class in {"slides", "screen_demo"}:
        target = _target_frames(
            signals.duration_seconds, seconds_per_frame=90, minimum=6, maximum=80
        )
        return VisualAcquisitionPlan(
            useful=True,
            content_class=content_class,
            sampling_strategy="hybrid",
            extraction_intents=["ocr", "capture"],
            target_frame_count=target,
            min_interval_seconds=8,
            align_to_transcript=signals.transcript_timestamps,
            reason=(
                "slide/screen content should be sampled at visual changes with transcript-aligned "
                "backstops because text on screen is likely high-value source material"
            ),
        )

    if content_class in {"diagram", "formula"}:
        target = _target_frames(
            signals.duration_seconds, seconds_per_frame=60, minimum=8, maximum=100
        )
        return VisualAcquisitionPlan(
            useful=True,
            content_class=content_class,
            sampling_strategy="hybrid",
            extraction_intents=["ocr", "describe", "capture"],
            target_frame_count=target,
            min_interval_seconds=5,
            align_to_transcript=signals.transcript_timestamps,
            reason=(
                "diagrams/formulas need OCR and visual description; preserving "
                "selected images is important because text extraction can lose "
                "layout/structure"
            ),
            warnings=[
                "diagram/formula interpretation is model output; keep source frame references"
            ],
        )

    if content_class == "scenery":
        target = _target_frames(
            signals.duration_seconds, seconds_per_frame=180, minimum=3, maximum=30
        )
        return VisualAcquisitionPlan(
            useful=True,
            content_class=content_class,
            sampling_strategy="scene_change",
            extraction_intents=["describe", "capture"],
            target_frame_count=target,
            min_interval_seconds=20,
            align_to_transcript=False,
            reason=(
                "scenery is better represented by sparse scene-change descriptions "
                "and source frames than OCR"
            ),
        )

    target = _target_frames(
        signals.duration_seconds, seconds_per_frame=120, minimum=4, maximum=60
    )
    return VisualAcquisitionPlan(
        useful=True,
        content_class=content_class,
        sampling_strategy="hybrid" if signals.transcript_timestamps else "scene_change",
        extraction_intents=_default_intents(signals),
        target_frame_count=target,
        min_interval_seconds=10,
        align_to_transcript=signals.transcript_timestamps,
        reason=(
            "unknown/mixed visual source; use conservative scene-change sampling "
            "plus transcript alignment when available"
        ),
    )


def _infer_content_class(signals: VisualSourceSignals) -> VisualContentClass:
    if signals.content_hint != "unknown":
        return signals.content_hint
    text = " ".join(part.lower() for part in (signals.title, signals.description) if part)
    if any(token in text for token in ("podcast", "audio only", "interview")):
        return "podcast"
    if any(token in text for token in ("lecture", "slides", "presentation", "ppt", "keynote")):
        return "slides"
    if any(token in text for token in ("screen", "demo", "coding", "tutorial", "walkthrough")):
        return "screen_demo"
    if any(token in text for token in ("diagram", "architecture", "flowchart", "graph")):
        return "diagram"
    if any(token in text for token in ("formula", "equation", "proof", "derivation")):
        return "formula"
    if signals.text_density_hint == "high":
        return "slides"
    if signals.motion_hint == "low" and signals.speech_density and signals.speech_density > 0.75:
        return "talking_head"
    if signals.motion_hint == "high" and signals.text_density_hint == "low":
        return "scenery"
    return "mixed"


def _default_intents(signals: VisualSourceSignals) -> list[VisualExtractionIntent]:
    if signals.text_density_hint == "high":
        return ["ocr", "capture"]
    if signals.text_density_hint == "low" and signals.motion_hint == "high":
        return ["describe", "capture"]
    return ["ocr", "describe", "capture"]


def _target_frames(
    duration_seconds: float | None, *, seconds_per_frame: int, minimum: int, maximum: int
) -> int:
    if duration_seconds is None or duration_seconds <= 0:
        return minimum
    estimated = round(duration_seconds / seconds_per_frame)
    return min(max(estimated, minimum), maximum)
