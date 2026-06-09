from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from vctx.transforms.visual_planning import Evidence

FrameSource = Literal["cover", "scene_change", "transcript_anchor", "probe"]
VisualRecordKind = Literal["ocr", "description", "capture"]


class FrameAsset(BaseModel):
    id: str
    timestamp_seconds: float | None = None
    path: Path
    source: FrameSource
    evidence: list[Evidence] = Field(default_factory=list)


class VisualUncertainty(BaseModel):
    prior_uncertainty: float = 0.0
    posterior_uncertainty: float = 0.0
    reduction: float = 0.0
    missing_referents: list[str] = Field(default_factory=list)
    resolved_referents: list[str] = Field(default_factory=list)


class VisualEvidenceScore(BaseModel):
    keep: bool
    novelty_score: float = 0.0
    overlap_score: float = 0.0
    grounding_score: float = 0.0
    reason: str
    uncertainty: VisualUncertainty = Field(default_factory=VisualUncertainty)


class VisualRecord(BaseModel):
    id: str
    timestamp_seconds: float | None = None
    frame_id: str
    kind: VisualRecordKind
    text: str | None = None
    artifact_path: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    score: VisualEvidenceScore | None = None


class VisualRecordSet(BaseModel):
    records: list[VisualRecord] = Field(default_factory=list)
