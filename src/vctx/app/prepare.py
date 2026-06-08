from __future__ import annotations

from vctx.app.config import PrepareRequest, resolve_config
from vctx.app.result import PrepareResult
from vctx.chunking.chunker import chunk_transcript
from vctx.io.cache import build_cache
from vctx.io.writer import validate_output_policy, write_artifact_bundle, write_manifest
from vctx.models.chunks import ChunkOptions
from vctx.models.manifest import ManifestBuilder
from vctx.render.bundle import render_artifact_bundle
from vctx.sources.detect import detect_source_adapter
from vctx.subtitles.parse import parse_transcript_payload
from vctx.transcript.normalize import normalize_transcript
from vctx.transforms.planning import SourceState, TransformEnvironment, plan_asr
from vctx.util.versions import vctx_version


def prepare_context_pack(request: PrepareRequest) -> PrepareResult:
    resolved = resolve_config(request)
    manifest = ManifestBuilder.start(input=request.input, tool_version=vctx_version())

    validate_output_policy(request.out_dir, overwrite=request.overwrite)
    cache = build_cache(resolved.runtime.cache_dir)

    adapter = detect_source_adapter(request.input)
    manifest.add_step("source.detect", "ok", adapter.name)

    metadata = adapter.extract_metadata(request.input)
    manifest.add_step("metadata.extract", "ok")

    payload = adapter.extract_transcript(
        request.input, preferred_language=resolved.source.preferred_language, cache=cache
    )
    manifest.add_step("transcript.extract", "ok", payload.provenance_label())

    asr_plan = plan_asr(
        resolved.transforms.asr,
        TransformEnvironment(offline=resolved.runtime.offline),
        SourceState(has_transcript=True, has_media=False),
    )
    manifest.add_step(
        "transform.asr",
        "skipped" if asr_plan.selected == "skipped" else "ok",
        asr_plan.reason,
    )

    raw = parse_transcript_payload(payload, video_id=metadata.id)
    manifest.add_step("transcript.parse", "ok", raw.provenance.format)

    clean = normalize_transcript(raw)
    manifest.add_step("transcript.normalize", "ok", f"{len(clean.segments)} segments")

    chunks = chunk_transcript(
        clean,
        ChunkOptions(
            max_chars=resolved.output.chunk_max_chars,
            max_seconds=resolved.output.chunk_max_seconds,
        ),
    )
    manifest.add_step("chunk", "ok", f"{len(chunks.chunks)} chunks")

    bundle = render_artifact_bundle(
        metadata=metadata,
        raw_transcript=raw,
        clean_transcript=clean,
        chunks=chunks,
        formats=resolved.output.formats,
    )
    artifact_refs = write_artifact_bundle(request.out_dir, bundle)
    final_manifest = manifest.finish(status="ok", artifacts=artifact_refs)
    write_manifest(request.out_dir, final_manifest)

    return PrepareResult(out_dir=request.out_dir, manifest=final_manifest, artifacts=artifact_refs)
