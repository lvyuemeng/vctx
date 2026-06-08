from __future__ import annotations

from pathlib import Path
from typing import Literal

from vctx.io.cache import Cache
from vctx.models.common import SourceRef
from vctx.models.metadata import VideoMetadata
from vctx.models.transcript import TranscriptPayload, TranscriptProvenance

SUPPORTED_SUFFIXES: dict[str, Literal["srt", "vtt"]] = {".srt": "srt", ".vtt": "vtt"}


class LocalFileSourceAdapter:
    name = "local-file"

    def can_handle(self, value: str) -> bool:
        path = Path(value)
        return path.exists() and path.suffix.lower() in SUPPORTED_SUFFIXES

    def extract_metadata(self, value: str) -> VideoMetadata:
        path = Path(value)
        return VideoMetadata(
            id=f"local__{path.stem}",
            source_type="local-file",
            source=SourceRef(kind="file", value=str(path)),
            title=path.stem,
            raw_provider="local-file",
        )

    def extract_transcript(
        self, value: str, *, preferred_language: str | None, cache: Cache
    ) -> TranscriptPayload:
        del cache
        path = Path(value)
        fmt = SUPPORTED_SUFFIXES[path.suffix.lower()]
        return TranscriptPayload(
            text=path.read_text(encoding="utf-8"),
            format=fmt,
            provenance=TranscriptProvenance(
                method="local_file",
                language=preferred_language,
                format=fmt,
                provider="local-file",
            ),
        )
