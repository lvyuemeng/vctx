from __future__ import annotations

from vctx.models.chunks import ChunkSet
from vctx.models.metadata import VideoMetadata
from vctx.models.transcript import Transcript
from vctx.util.timefmt import format_timestamp


def render_readable_markdown(
    metadata: VideoMetadata, transcript: Transcript, chunks: ChunkSet
) -> str:
    transcript_source = (
        f"Transcript source: {transcript.provenance.method} / "
        f"{transcript.provenance.language or 'unknown'}"
    )
    lines = [
        f"# {metadata.title or metadata.id}",
        "",
        f"Source: {metadata.source.value}  ",
        f"Duration: {format_timestamp(metadata.duration_seconds)}  ",
        transcript_source,
        "",
    ]
    for chunk in chunks.chunks:
        lines.extend(
            [
                f"## {format_timestamp(chunk.start)}–{format_timestamp(chunk.end)}",
                "",
                chunk.text,
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
