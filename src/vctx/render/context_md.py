from __future__ import annotations

from vctx.models.chunks import ChunkSet
from vctx.models.metadata import VideoMetadata
from vctx.models.transcript import Transcript
from vctx.models.visual import VisualRecordSet
from vctx.util.timefmt import format_timestamp


def render_context_markdown(
    metadata: VideoMetadata,
    transcript: Transcript,
    chunks: ChunkSet,
    visual_records: VisualRecordSet | None = None,
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
    ]
    if visual_records is not None and visual_records.records:
        renderable_records = [
            record
            for record in visual_records.records
            if record.score is None or record.score.keep
        ]
        if renderable_records:
            lines.extend(["## Visual records", ""])
            for record in renderable_records:
                timestamp = (
                    format_timestamp(record.timestamp_seconds)
                    if record.timestamp_seconds is not None
                    else "unknown"
                )
                detail = record.text or record.artifact_path or record.frame_id
                score = (
                    f" (novelty {record.score.novelty_score:.2f})"
                    if record.score is not None and record.kind != "capture"
                    else ""
                )
                lines.extend([f"- [{timestamp}] {record.kind}: {detail}{score}"])
            lines.append("")
    lines.extend([
        "## Chunks",
        "",
    ])
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
