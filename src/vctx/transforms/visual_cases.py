from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from vctx.models.transcript import Transcript, TranscriptSegment

EssentialCaseType = Literal[
    "diagram",
    "formula",
    "screen_demo",
    "table",
    "code",
    "slide_title",
    "visual_summary",
    "other",
]
EssentialCaseAction = Literal["ocr", "describe", "capture"]


class EssentialVisualCase(BaseModel):
    segment_id: str
    timestamp_seconds: float
    case_type: EssentialCaseType
    priority: float = 0.5
    reason: str
    actions: list[EssentialCaseAction] = Field(default_factory=list)

    @field_validator("priority")
    @classmethod
    def clamp_priority(cls, value: float) -> float:
        return round(min(max(value, 0.0), 1.0), 3)


def deterministic_essential_cases(transcript: Transcript) -> list[EssentialVisualCase]:
    """Extract bounded visual sampling cases from timestamped transcript cues."""

    cases: list[EssentialVisualCase] = []
    for segment in transcript.segments:
        cue = _segment_case(segment)
        if cue is None:
            continue
        case_type, priority, actions, reason = cue
        cases.append(
            EssentialVisualCase(
                segment_id=segment.id,
                timestamp_seconds=_segment_timestamp(segment),
                case_type=case_type,
                priority=priority,
                reason=reason,
                actions=actions,
            )
        )
    return cases


def dedupe_cases_by_window(
    cases: list[EssentialVisualCase], *, min_gap_s: float, budget: int
) -> list[EssentialVisualCase]:
    """Keep high-priority case anchors with only simple time-window dedup."""

    if budget <= 0:
        return []
    selected: list[EssentialVisualCase] = []
    for case in sorted(cases, key=lambda item: item.priority, reverse=True):
        if len(selected) >= budget:
            break
        if all(
            abs(case.timestamp_seconds - existing.timestamp_seconds) >= min_gap_s
            for existing in selected
        ):
            selected.append(case)
    return sorted(selected, key=lambda item: item.timestamp_seconds)


def _segment_case(
    segment: TranscriptSegment,
) -> tuple[EssentialCaseType, float, list[EssentialCaseAction], str] | None:
    text = segment.text.lower()
    if _contains_any(text, ("diagram", "architecture", "flowchart", "system flow")):
        return (
            "diagram",
            0.9,
            ["describe", "capture"],
            _reason(segment, "diagram or architecture visual reference"),
        )
    if _contains_any(text, ("formula", "equation", "derive", "derivation", "proof")):
        return (
            "formula",
            0.85,
            ["ocr", "describe", "capture"],
            _reason(segment, "formula or derivation visual reference"),
        )
    if _contains_any(text, ("screen", "click", "open", "terminal", "demo", "walkthrough")):
        return (
            "screen_demo",
            0.75,
            ["ocr", "describe", "capture"],
            _reason(segment, "screen or demo visual reference"),
        )
    if _contains_any(text, ("table", "row", "column", "compare", "comparison")):
        return (
            "table",
            0.7,
            ["ocr", "capture"],
            _reason(segment, "table or comparison visual reference"),
        )
    if _contains_any(text, ("code", "function", "class", "snippet")):
        return (
            "code",
            0.7,
            ["ocr", "capture"],
            _reason(segment, "code visual reference"),
        )
    return None


def _segment_timestamp(segment: TranscriptSegment) -> float:
    if segment.end is None or segment.end <= segment.start:
        return segment.start
    return round((segment.start + segment.end) / 2, 3)


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _reason(segment: TranscriptSegment, cue: str) -> str:
    excerpt = " ".join(segment.text.split())
    if len(excerpt) > 120:
        excerpt = f"{excerpt[:117]}..."
    return f"{cue}: {excerpt}"
