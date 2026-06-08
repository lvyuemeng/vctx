from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from vctx.app.errors import VctxError
from vctx.models.chunks import ChunkSet
from vctx.models.metadata import VideoMetadata
from vctx.models.transcript import Transcript
from vctx.render.context_md import render_context_markdown
from vctx.render.readable_md import render_readable_markdown
from vctx.render.transcript_md import render_transcript_markdown


class RenderFormat(StrEnum):
    CONTEXT = "context"
    READABLE = "readable"
    TRANSCRIPT = "transcript"


class RenderInputError(VctxError):
    exit_code = 4


def render_from_files(
    *,
    metadata_path: Path,
    transcript_path: Path,
    chunks_path: Path | None,
    format: RenderFormat,
) -> str:
    metadata = _load_model(metadata_path, VideoMetadata)
    transcript = _load_model(transcript_path, Transcript)
    if format == RenderFormat.TRANSCRIPT:
        return render_transcript_markdown(metadata, transcript)

    if chunks_path is None:
        raise RenderInputError(f"--chunks is required for {format} render")
    chunks = _load_model(chunks_path, ChunkSet)
    if format == RenderFormat.CONTEXT:
        return render_context_markdown(metadata, transcript, chunks)
    if format == RenderFormat.READABLE:
        return render_readable_markdown(metadata, transcript, chunks)
    raise RenderInputError(f"unsupported render format: {format}")


TModel = TypeVar("TModel", bound=BaseModel)


def _load_model(path: Path, model_type: type[TModel]) -> TModel:
    try:
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise RenderInputError(f"invalid {model_type.__name__} file: {path}") from exc
