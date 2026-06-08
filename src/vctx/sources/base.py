from __future__ import annotations

from typing import Protocol

from vctx.io.cache import Cache
from vctx.models.metadata import VideoMetadata
from vctx.models.transcript import TranscriptPayload


class SourceAdapter(Protocol):
    name: str

    def can_handle(self, value: str) -> bool: ...

    def extract_metadata(self, value: str) -> VideoMetadata: ...

    def extract_transcript(
        self,
        value: str,
        *,
        preferred_language: str | None,
        cache: Cache,
    ) -> TranscriptPayload: ...
