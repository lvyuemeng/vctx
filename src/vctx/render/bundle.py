from __future__ import annotations

from typing import Literal, cast

from pydantic import BaseModel

from vctx.io.json_dump import model_to_json
from vctx.models.artifacts import Artifact, ArtifactBundle, ArtifactKind
from vctx.models.chunks import ChunkSet
from vctx.models.metadata import VideoMetadata
from vctx.models.transcript import Transcript
from vctx.models.visual import VisualRecordSet
from vctx.render.context_md import render_context_markdown
from vctx.render.readable_md import render_readable_markdown
from vctx.render.transcript_md import render_transcript_markdown

OutputFormat = Literal["json", "context", "readable", "transcript"]
DEFAULT_FORMATS: set[OutputFormat] = {"json", "context", "readable", "transcript"}


def json_artifact(name: str, kind: str, model: BaseModel) -> Artifact:
    return Artifact(
        name=name,
        kind=cast(ArtifactKind, kind),
        media_type="application/json",
        content=model_to_json(model),
    )


def markdown_artifact(name: str, kind: str, content: str) -> Artifact:
    return Artifact(
        name=name,
        kind=cast(ArtifactKind, kind),
        media_type="text/markdown",
        content=content,
    )


def render_artifact_bundle(
    *,
    metadata: VideoMetadata,
    raw_transcript: Transcript,
    clean_transcript: Transcript,
    chunks: ChunkSet,
    formats: set[OutputFormat],
    visual_records: VisualRecordSet | None = None,
) -> ArtifactBundle:
    artifacts: list[Artifact] = []
    if "json" in formats:
        artifacts.extend(
            [
                json_artifact("metadata.json", "metadata", metadata),
                json_artifact("transcript.raw.json", "transcript_raw", raw_transcript),
                json_artifact("transcript.clean.json", "transcript_clean", clean_transcript),
                json_artifact("chunks.json", "chunks", chunks),
            ]
        )
        if visual_records is not None and visual_records.records:
            artifacts.append(json_artifact("visual_records.json", "visual_records", visual_records))
    if "context" in formats:
        artifacts.append(
            markdown_artifact(
                "context.md",
                "context",
                render_context_markdown(metadata, clean_transcript, chunks, visual_records),
            )
        )
    if "readable" in formats:
        artifacts.append(
            markdown_artifact(
                "readable.md",
                "readable",
                render_readable_markdown(metadata, clean_transcript, chunks, visual_records),
            )
        )
    if "transcript" in formats:
        artifacts.append(
            markdown_artifact(
                "transcript.md",
                "transcript_md",
                render_transcript_markdown(metadata, clean_transcript),
            )
        )
    return ArtifactBundle(artifacts=artifacts)
