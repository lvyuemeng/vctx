from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from vctx.app.result import PrepareResult
from vctx.chunking.chunker import chunk_transcript
from vctx.io.cache import build_cache
from vctx.io.writer import validate_output_policy, write_artifact_bundle, write_manifest
from vctx.models.chunks import ChunkOptions
from vctx.models.manifest import ManifestBuilder
from vctx.render.bundle import DEFAULT_FORMATS, OutputFormat, render_artifact_bundle
from vctx.sources.detect import detect_source_adapter
from vctx.subtitles.parse import parse_transcript_payload
from vctx.transcript.normalize import normalize_transcript
from vctx.util.versions import vctx_version


class PrepareRequest(BaseModel):
    input: str
    out_dir: Path
    language: str | None = None
    overwrite: bool = False
    chunk_max_chars: int = 6000
    chunk_max_seconds: int | None = None
    cache_dir: Path | None = None
    keep_temp: bool = False
    formats: set[OutputFormat] = DEFAULT_FORMATS


def prepare_context_pack(request: PrepareRequest) -> PrepareResult:
    manifest = ManifestBuilder.start(input=request.input, tool_version=vctx_version())

    validate_output_policy(request.out_dir, overwrite=request.overwrite)
    cache = build_cache(request.cache_dir)

    adapter = detect_source_adapter(request.input)
    manifest.add_step("source.detect", "ok", adapter.name)

    metadata = adapter.extract_metadata(request.input)
    manifest.add_step("metadata.extract", "ok")

    payload = adapter.extract_transcript(
        request.input, preferred_language=request.language, cache=cache
    )
    manifest.add_step("transcript.extract", "ok", payload.provenance_label())

    raw = parse_transcript_payload(payload, video_id=metadata.id)
    manifest.add_step("transcript.parse", "ok", raw.provenance.format)

    clean = normalize_transcript(raw)
    manifest.add_step("transcript.normalize", "ok", f"{len(clean.segments)} segments")

    chunks = chunk_transcript(
        clean,
        ChunkOptions(max_chars=request.chunk_max_chars, max_seconds=request.chunk_max_seconds),
    )
    manifest.add_step("chunk", "ok", f"{len(chunks.chunks)} chunks")

    bundle = render_artifact_bundle(
        metadata=metadata,
        raw_transcript=raw,
        clean_transcript=clean,
        chunks=chunks,
        formats=request.formats,
    )
    artifact_refs = write_artifact_bundle(request.out_dir, bundle)
    final_manifest = manifest.finish(status="ok", artifacts=artifact_refs)
    write_manifest(request.out_dir, final_manifest)

    return PrepareResult(out_dir=request.out_dir, manifest=final_manifest, artifacts=artifact_refs)
