from __future__ import annotations

from vctx.models.metadata import VideoMetadata
from vctx.models.transcript import Transcript
from vctx.util.timefmt import format_timestamp


def render_transcript_markdown(metadata: VideoMetadata, transcript: Transcript) -> str:
    lines = [f"# Transcript — {metadata.title or metadata.id}", ""]
    for segment in transcript.segments:
        lines.append(
            f"[{format_timestamp(segment.start)}–{format_timestamp(segment.end)}] {segment.text}"
        )
    return "\n".join(lines).rstrip() + "\n"
