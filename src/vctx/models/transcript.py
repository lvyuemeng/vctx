from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel


class TranscriptSegment(BaseModel):
    id: str
    start: float
    end: float | None = None
    text: str
    source_id: str | None = None


class TranscriptProvenance(BaseModel):
    method: Literal["official_subtitles", "automatic_subtitles", "local_file", "asr"]
    language: str | None = None
    format: Literal["vtt", "srt", "json", "plain", "unknown"] = "unknown"
    provider: str | None = None


class Transcript(BaseModel):
    video_id: str
    provenance: TranscriptProvenance
    segments: list[TranscriptSegment]


class TranscriptPayload(BaseModel):
    text: str
    format: Literal["vtt", "srt", "json", "plain", "unknown"]
    provenance: TranscriptProvenance

    def provenance_label(self) -> str:
        parts: list[str] = [self.provenance.method]
        if self.provenance.language:
            parts.append(self.provenance.language)
        parts.append(self.format)
        return ":".join(parts)


def reassign_segment_ids(segments: Sequence[TranscriptSegment]) -> list[TranscriptSegment]:
    return [
        segment.model_copy(update={"id": f"seg_{index:06d}"})
        for index, segment in enumerate(segments, start=1)
    ]
