from __future__ import annotations

from vctx.app.config import (
    CapabilityEnabled,
    PrepareRequest,
    ResolvedConfig,
    WorkflowProfile,
    resolve_config,
)
from vctx.app.credentials import CredentialError, resolve_env_credential
from vctx.app.errors import NoTranscriptError
from vctx.app.result import PrepareResult
from vctx.chunking.chunker import chunk_transcript
from vctx.io.cache import build_cache
from vctx.io.json_dump import model_to_json
from vctx.io.writer import (
    validate_output_policy,
    write_artifact,
    write_artifact_bundle,
    write_manifest,
)
from vctx.models.artifacts import Artifact
from vctx.models.chunks import ChunkOptions
from vctx.models.manifest import ArtifactRef, ManifestBuilder
from vctx.models.media import MediaAsset
from vctx.models.metadata import VideoMetadata
from vctx.models.visual import VisualRecordSet
from vctx.render.bundle import render_artifact_bundle
from vctx.sources.detect import detect_source_adapter
from vctx.subtitles.parse import parse_transcript_payload
from vctx.transcript.normalize import normalize_transcript
from vctx.transforms.asr import AsrExecutionError, run_asr
from vctx.transforms.planning import SourceState, TransformEnvironment, plan_asr
from vctx.transforms.visual_execute import VisualExecutionError, run_visual_context
from vctx.transforms.visual_planning import (
    VisualAssessment,
    VisualSourceSignals,
    plan_visual_acquisition,
)
from vctx.transforms.visual_routes import discover_visual_operations
from vctx.util.versions import vctx_version


def prepare_context_pack(request: PrepareRequest) -> PrepareResult:
    resolved = resolve_config(request)
    manifest = ManifestBuilder.start(input=request.input, tool_version=vctx_version())

    validate_output_policy(request.out_dir, overwrite=request.overwrite)
    cache = build_cache(resolved.runtime.cache_dir)

    adapter = detect_source_adapter(request.input)
    manifest.add_step("source.detect", "ok", adapter.name)
    media_asset: MediaAsset | None = None

    metadata = adapter.extract_metadata(request.input)
    manifest.add_step("metadata.extract", "ok")

    if resolved.runtime.workflow == WorkflowProfile.METADATA:
        manifest.add_step(
            "transcript.extract",
            "skipped",
            "metadata workflow selected",
        )
        manifest.warn("metadata workflow selected; transcript pipeline skipped")
        return _write_metadata_partial_result(request, manifest, metadata)

    try:
        payload = adapter.extract_transcript(
            request.input, preferred_language=resolved.source.preferred_language, cache=cache
        )
    except NoTranscriptError as exc:
        manifest.add_step("transcript.extract", "warning", str(exc))
        pre_media_asr_plan = plan_asr(
            resolved.transforms.asr,
            _asr_environment(resolved),
            SourceState(has_transcript=False, has_media=True),
        )
        if pre_media_asr_plan.selected not in {"local", "configured-online"}:
            manifest.add_transform_evidence(pre_media_asr_plan.evidence_seed)
            manifest.add_step("source.media", "skipped", "no executable ASR route selected")
            manifest.add_step("transform.asr", "warning", pre_media_asr_plan.reason)
            manifest.warn(_capitalize_warning(str(exc)))
            manifest.warn(
                "Provide a transcript file, install the default ASR extra, "
                "configure an online fallback, or use metadata-only output."
            )
            return _write_metadata_partial_result(request, manifest, metadata)
        try:
            media_asset = adapter.extract_media(
                request.input, preferred_language=resolved.source.preferred_language, cache=cache
            )
        except NoTranscriptError as media_exc:
            asr_plan = plan_asr(
                resolved.transforms.asr,
                _asr_environment(resolved),
                SourceState(has_transcript=False, has_media=False),
            )
            manifest.add_step("source.media", "warning", str(media_exc))
            manifest.add_transform_evidence(asr_plan.evidence_seed)
            manifest.add_step("transform.asr", "warning", asr_plan.reason)
            manifest.warn(_capitalize_warning(str(exc)))
            manifest.warn(
                "Provide a transcript file, install the default ASR extra, "
                "configure an online fallback, or use metadata-only output."
            )
            return _write_metadata_partial_result(request, manifest, metadata)

        manifest.add_step("source.media", "ok", str(media_asset.local_path))
        asr_plan = plan_asr(
            resolved.transforms.asr,
            _asr_environment(resolved),
            SourceState(has_transcript=False, has_media=True),
        )
        if asr_plan.selected not in {"local", "configured-online"}:
            manifest.add_transform_evidence(asr_plan.evidence_seed)
            manifest.add_step("transform.asr", "warning", asr_plan.reason)
            manifest.warn(_capitalize_warning(str(exc)))
            manifest.warn(asr_plan.reason)
            return _write_metadata_partial_result(request, manifest, metadata)
        instance_name = resolved.transforms.asr.instance
        instance = resolved.instances.asr.get(instance_name) if instance_name else None
        if instance is None:
            manifest.add_step("transform.asr", "warning", "ASR instance is not configured")
            manifest.warn("ASR instance is not configured")
            return _write_metadata_partial_result(request, manifest, metadata)
        manifest.add_transform_evidence(asr_plan.evidence_seed)
        api_key: str | None = None
        if asr_plan.selected == "configured-online":
            try:
                api_key = resolve_env_credential(
                    instance.api_key_env,
                    env_files=resolved.runtime.env_files,
                )
            except CredentialError as credential_exc:
                manifest.add_step("transform.asr", "warning", str(credential_exc))
                manifest.warn(str(credential_exc))
                return _write_metadata_partial_result(request, manifest, metadata)
        try:
            payload = run_asr(
                asr_plan,
                media_asset,
                instance=instance,
                cache_root=cache.root,
                offline=resolved.runtime.offline,
                api_key=api_key,
            )
        except AsrExecutionError as asr_exc:
            manifest.add_step("transform.asr", "warning", str(asr_exc))
            manifest.warn(str(asr_exc))
            return _write_metadata_partial_result(request, manifest, metadata)
        manifest.add_step("transform.asr", "ok", payload.provenance_label())
    else:
        manifest.add_step("transcript.extract", "ok", payload.provenance_label())

        asr_plan = plan_asr(
            resolved.transforms.asr,
            TransformEnvironment(offline=resolved.runtime.offline),
            SourceState(has_transcript=True, has_media=False),
        )
        manifest.add_transform_evidence(asr_plan.evidence_seed)
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

    visual_records = None
    visual_frame_refs: list[ArtifactRef] = []
    if _visual_enabled(resolved):
        if media_asset is None:
            try:
                media_asset = adapter.extract_media(
                    request.input,
                    preferred_language=resolved.source.preferred_language,
                    cache=cache,
                )
                manifest.add_step("source.media", "ok", str(media_asset.local_path))
            except NoTranscriptError as media_exc:
                manifest.add_step("source.media", "skipped", str(media_exc))
        if media_asset is not None and media_asset.media_type == "video":
            assessment = plan_visual_acquisition(
                VisualSourceSignals(
                    has_video=True,
                    duration_seconds=media_asset.duration_seconds or metadata.duration_seconds,
                    title=metadata.title,
                    description=None,
                    transcript_timestamps=bool(clean.segments),
                    operations=discover_visual_operations(
                        resolved.transforms.visual_context,
                        vision_providers=resolved.providers.vision,
                    ),
                )
            )
            manifest.add_step("transform.visual_plan", "ok", _visual_plan_detail(assessment))
            try:
                visual_records = run_visual_context(
                    assessment,
                    media_asset,
                    request.out_dir,
                    vision_providers=resolved.providers.vision,
                    env_files=resolved.runtime.env_files,
                )
            except VisualExecutionError as visual_exc:
                manifest.add_step("transform.visual_capture", "warning", str(visual_exc))
            else:
                manifest.add_step(
                    "transform.visual_capture",
                    "ok",
                    f"{len(visual_records.records)} records",
                )
                visual_frame_refs = _visual_frame_refs(visual_records)
        else:
            manifest.add_step("transform.visual_plan", "skipped", "no video media asset")

    bundle = render_artifact_bundle(
        metadata=metadata,
        raw_transcript=raw,
        clean_transcript=clean,
        chunks=chunks,
        formats=resolved.output.formats,
        visual_records=visual_records,
    )
    artifact_refs = write_artifact_bundle(request.out_dir, bundle)
    artifact_refs.extend(visual_frame_refs)
    final_manifest = manifest.finish(status="ok", artifacts=artifact_refs)
    write_manifest(request.out_dir, final_manifest)

    return PrepareResult(out_dir=request.out_dir, manifest=final_manifest, artifacts=artifact_refs)


def _asr_environment(resolved: ResolvedConfig) -> TransformEnvironment:
    instance_name = resolved.transforms.asr.instance
    instance = resolved.instances.asr.get(instance_name) if instance_name else None
    if instance is None:
        return TransformEnvironment(offline=resolved.runtime.offline)
    if instance.type == "local-faster-whisper":
        return TransformEnvironment(
            offline=resolved.runtime.offline,
            installed_asr=True,
            configured_asr_model_id=instance.model or instance.model_policy,
            configured_asr_cost_mode="local",
        )
    if instance.type == "openai-compatible-audio":
        return TransformEnvironment(
            offline=resolved.runtime.offline,
            configured_asr=True,
            configured_asr_provider_id=instance_name,
            configured_asr_model_id=instance.model,
            configured_asr_cost_mode=instance.cost,
        )
    return TransformEnvironment(offline=resolved.runtime.offline)


def _visual_enabled(resolved: ResolvedConfig) -> bool:
    return resolved.transforms.visual_context.enabled == CapabilityEnabled.TRUE


def _visual_frame_refs(visual_records: VisualRecordSet) -> list[ArtifactRef]:
    refs: list[ArtifactRef] = []
    seen: set[str] = set()
    for record in visual_records.records:
        if record.kind != "capture" or record.artifact_path is None:
            continue
        if record.artifact_path in seen:
            continue
        seen.add(record.artifact_path)
        refs.append(
            ArtifactRef(
                kind="visual_frame",
                path=record.artifact_path,
                media_type=_visual_frame_media_type(record.artifact_path),
            )
        )
    return refs


def _visual_frame_media_type(path: str) -> str:
    if path.lower().endswith(".png"):
        return "image/png"
    if path.lower().endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    return "application/octet-stream"


def _visual_plan_detail(assessment: VisualAssessment) -> str:
    route_details = []
    for action in assessment.recipe:
        provider_id = action.params.get("provider_id")
        if action.name == "ocr" and provider_id is not None:
            route_details.append(f"local OCR: {provider_id}")
        if action.name == "describe" and provider_id is not None:
            route = action.params.get("route")
            label = "free VLM" if route == "free-online" else "configured VLM"
            route_details.append(f"{label}: {provider_id}")
    if route_details:
        return "; ".join(route_details)
    return assessment.rationale


def _capitalize_warning(message: str) -> str:
    if not message:
        return message
    return message[:1].upper() + message[1:]


def _write_metadata_partial_result(
    request: PrepareRequest,
    manifest: ManifestBuilder,
    metadata: VideoMetadata,
) -> PrepareResult:
    request.out_dir.mkdir(parents=True, exist_ok=True)
    artifact_ref = write_artifact(
        request.out_dir,
        Artifact(
            name="metadata.json",
            kind="metadata",
            media_type="application/json",
            content=model_to_json(metadata),
        ),
    )
    final_manifest = manifest.finish(status="partial", artifacts=[artifact_ref])
    write_manifest(request.out_dir, final_manifest)
    return PrepareResult(
        out_dir=request.out_dir,
        manifest=final_manifest,
        artifacts=[artifact_ref],
    )
