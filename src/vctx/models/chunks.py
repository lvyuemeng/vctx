from __future__ import annotations

from pydantic import BaseModel


class ChunkOptions(BaseModel):
    max_chars: int = 6000
    max_seconds: int | None = None


class TranscriptChunk(BaseModel):
    id: str
    start: float
    end: float | None
    text: str
    segment_ids: list[str]
    char_count: int
    approx_token_count: int


class ChunkSet(BaseModel):
    video_id: str
    strategy: str
    chunks: list[TranscriptChunk]
