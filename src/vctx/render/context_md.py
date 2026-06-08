from __future__ import annotations

from vctx.models.chunks import ChunkSet
from vctx.models.metadata import VideoMetadata
from vctx.models.transcript import Transcript
from vctx.util.timefmt import format_timestamp


def render_context_markdown(
    metadata: VideoMetadata, transcript: Transcript, chunks: ChunkSet
) -> str:
    lines = [
        "# Agent Context Pack",
        "",
        "## Metadata",
        "",
        f"- Title: {metadata.title or metadata.id}",
        f"- Source: {metadata.source.value}",
        f"- Duration: {format_timestamp(metadata.duration_seconds)}",
        "- Transcript source: "
        f"{transcript.provenance.method} / {transcript.provenance.language or 'unknown'} / "
        f"{transcript.provenance.format}",
        "",
        "## Usage",
        "",
        "The chunks below are timestamped source text extracted from the video or transcript.",
        "Preserve timestamps when citing claims.",
        "",
        "## Chunks",
        "",
    ]
    for chunk in chunks.chunks:
        lines.extend(
            [
                f'<chunk id="{chunk.id}" start="{format_timestamp(chunk.start)}" '
                f'end="{format_timestamp(chunk.end)}">',
                chunk.text,
                "</chunk>",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
