from __future__ import annotations

from pathlib import Path
from typing import Literal

from vctx.app.errors import NoTranscriptError
from vctx.io.cache import Cache
from vctx.models.common import SourceRef
from vctx.models.media import MediaAsset
from vctx.models.metadata import VideoMetadata
from vctx.models.transcript import TranscriptPayload, TranscriptProvenance

SUPPORTED_TRANSCRIPT_SUFFIXES: dict[str, Literal["srt", "vtt"]] = {".srt": "srt", ".vtt": "vtt"}
SUPPORTED_MEDIA_SUFFIXES = {".wav", ".mp3", ".m4a", ".mp4", ".webm"}
AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a"}
VIDEO_SUFFIXES = {".mp4", ".webm"}


class LocalFileSourceAdapter:
    name = "local-file"

    def can_handle(self, value: str) -> bool:
        path = Path(value)
        return path.exists() and path.suffix.lower() in (
            SUPPORTED_TRANSCRIPT_SUFFIXES.keys() | SUPPORTED_MEDIA_SUFFIXES
        )

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
        fmt = SUPPORTED_TRANSCRIPT_SUFFIXES.get(path.suffix.lower())
        if fmt is None:
            raise NoTranscriptError(f"no transcript found for media input: {value}")
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

    def extract_media(
        self, value: str, *, preferred_language: str | None, cache: Cache
    ) -> MediaAsset:
        del cache
        path = Path(value)
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_MEDIA_SUFFIXES:
            raise NoTranscriptError(f"no media found for input: {value}")
        media_type: Literal["audio", "video", "unknown"] = "unknown"
        if suffix in AUDIO_SUFFIXES:
            media_type = "audio"
        elif suffix in VIDEO_SUFFIXES:
            media_type = "video"
        return MediaAsset(
            id=f"local__{path.stem}",
            source=SourceRef(kind="file", value=str(path)),
            local_path=path,
            media_type=media_type,
            container=suffix.removeprefix("."),
            language_hint=preferred_language,
            provider="local-file",
        )
