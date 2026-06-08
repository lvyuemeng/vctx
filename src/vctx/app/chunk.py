from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from vctx.app.errors import InvalidTranscriptError
from vctx.chunking.chunker import chunk_transcript
from vctx.models.chunks import ChunkOptions, ChunkSet
from vctx.models.transcript import Transcript


def chunk_transcript_file(
    transcript_path: Path,
    *,
    max_chars: int = 6000,
    max_seconds: int | None = None,
) -> ChunkSet:
    try:
        transcript = Transcript.model_validate_json(transcript_path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise InvalidTranscriptError(f"invalid transcript file: {transcript_path}") from exc
    return chunk_transcript(
        transcript,
        ChunkOptions(max_chars=max_chars, max_seconds=max_seconds),
    )
