# vctx Function Graph

This document describes the concrete function-level graph for the initial `vctx` implementation.

It aligns with:

- [`docs/context.md`](context.md): project principles and dependency boundaries
- [`docs/api.md`](api.md): CLI and artifact contract
- [`docs/architecture.md`](architecture.md): abstract architecture, boundaries, and behavior model

The goal is to make implementation straightforward without drifting into a monolith. The graph below is not a knowledge-management graph; it is the internal data-flow graph of a CLI context-pack compiler.

## Design rules

The function graph follows these rules:

1. CLI functions parse and display only.
2. Application functions orchestrate only.
3. Source adapters own external integrations.
4. Pure transformation functions accept internal models and return internal models or strings.
5. Renderers do not fetch, parse, normalize, or write files.
6. Writers do not understand video providers or transcript semantics.
7. Every stage records enough information for `manifest.json`.
8. Default graph uses no AI dependency.
9. Optional internal AI transformations are explicit adapter nodes, not user-facing chat nodes.

## Top-level graph

```text
vctx CLI
  prepare_command(input, options)
    -> build_prepare_request(...)
    -> prepare_context_pack(request)
       -> validate_output_policy(...)
       -> build_cache(...)
       -> detect_source_adapter(input)
       -> adapter.extract_metadata(input)
       -> acquire_text_or_media(input, options)
       -> route_preparation_strategy(acquired, options)
       -> maybe_run_internal_transformations(acquired, route, options)
       -> parse_transcript_payload(payload)
       -> normalize_transcript(raw_transcript)
       -> maybe_run_transcript_transformations(clean_transcript, route, options)
       -> chunk_transcript(clean_transcript, chunk_options)
       -> render_artifact_bundle(metadata, transcripts, chunks, options)
       -> write_artifact_bundle(out_dir, bundle, overwrite)
       -> build_final_manifest(...)
       -> write_manifest(out_dir, manifest)
    -> print_prepare_result(result)
```

Side-effecting nodes:

```text
prepare_command                 # stdout/stderr
validate_output_policy          # filesystem checks
build_cache                     # cache path discovery / possible directory creation
detect_source_adapter           # may check local path existence
adapter.extract_metadata         # network/extractor/file reads
adapter.extract_transcript       # network/extractor/file reads/cache writes
adapter.extract_media            # optional media download or file reads
run_transform_adapter            # optional local/online AI/tool calls
write_artifact_bundle            # filesystem writes
write_manifest                   # filesystem write
print_prepare_result             # stdout
```

Pure nodes:

```text
build_prepare_request
route_preparation_strategy from explicit options and available capabilities
parse_transcript_payload once payload text is available
normalize_transcript
chunk_transcript
render_* functions
build_final_manifest before writing
```

## Module graph

```text
src/vctx/cli.py
  depends on -> app.prepare, app.errors, app.result

src/vctx/app/prepare.py
  depends on -> models.*, sources.detect, transforms.routing,
                subtitles.parse, transcript.normalize, chunking.chunker,
                render.*, io.writer, io.cache, util.versions

src/vctx/sources/detect.py
  depends on -> sources.base, sources.ytdlp_source, sources.local_file_source

src/vctx/sources/ytdlp_source.py
  depends on -> yt_dlp, models.metadata, sources.base, io.cache

src/vctx/sources/local_file_source.py
  depends on -> pathlib, models.metadata, sources.base

src/vctx/transforms/*.py
  depends on -> models.*, io.cache, optional provider adapters

src/vctx/subtitles/parse.py
  depends on -> subtitles.webvtt_parser, subtitles.srt_parser, models.transcript

src/vctx/transcript/normalize.py
  depends on -> transcript.clean_text, models.transcript

src/vctx/chunking/chunker.py
  depends on -> chunking.tokens, models.transcript, models.chunks

src/vctx/render/*.py
  depends on -> models.metadata, models.transcript, models.chunks, util.timefmt

src/vctx/io/writer.py
  depends on -> pathlib, models.artifacts, models.manifest
```

Forbidden dependency directions:

```text
models -> anything else
render -> sources
render -> io.writer
chunking -> sources
transcript -> sources
sources -> render
sources -> chunking
transforms -> render
transforms -> CLI
CLI -> yt_dlp directly
CLI -> filesystem artifact writing directly
```

## Public CLI function API

### `src/vctx/cli.py`

```python
app = typer.Typer(no_args_is_help=True)

@app.command("prepare")
def prepare_command(
    input: str,
    out: Path,
    language: str | None = None,
    overwrite: bool = False,
    chunk_max_chars: int = 6000,
    chunk_max_seconds: int | None = None,
    cache_dir: Path | None = None,
    keep_temp: bool = False,
    formats: list[OutputFormat] = DEFAULT_FORMATS,
) -> None: ...

@app.command("metadata")
def metadata_command(input: str, json_output: bool = False) -> None: ...

@app.command("chunk")
def chunk_command(
    transcript: Path,
    out: Path,
    chunk_max_chars: int = 6000,
    chunk_max_seconds: int | None = None,
) -> None: ...

@app.command("render")
def render_command(
    metadata: Path,
    chunks: Path | None,
    transcript: Path | None,
    out: Path,
    format: RenderFormat,
) -> None: ...

@app.command("doctor")
def doctor_command() -> None: ...
```

CLI responsibilities:

- convert CLI args into request models
- catch `VctxError`
- map exceptions to exit codes from `docs/api.md`
- print concise final paths to stdout
- print warnings/errors to stderr

CLI must not:

- call `yt-dlp` directly
- parse subtitle text directly
- render Markdown inline
- write artifact files inline

## Application function API

### `src/vctx/app/prepare.py`

```python
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
    asr: AsrMode | None = None
    ai_transforms: list[TransformRequest] = []
    on_missing_transcript: MissingTranscriptPolicy = "partial"


def prepare_context_pack(request: PrepareRequest) -> PrepareResult: ...
```

Pseudocode:

```python
def prepare_context_pack(request: PrepareRequest) -> PrepareResult:
    manifest = ManifestBuilder.start(input=request.input)

    validate_output_policy(request.out_dir, overwrite=request.overwrite)
    cache = build_cache(request.cache_dir)

    adapter = detect_source_adapter(request.input)
    manifest.add_step("source.detect", "ok", adapter.name)

    metadata = adapter.extract_metadata(request.input)
    manifest.add_step("metadata.extract", "ok")

    acquisition = acquire_transcript_or_media(
        adapter=adapter,
        input=request.input,
        preferred_language=request.language,
        cache=cache,
        asr=request.asr,
        on_missing_transcript=request.on_missing_transcript,
    )
    manifest.extend(acquisition.steps)

    if acquisition.status == "partial":
        partial_refs = write_partial_artifacts(request.out_dir, metadata, acquisition.warnings)
        partial_manifest = manifest.finish(status="partial", artifacts=partial_refs)
        write_manifest(request.out_dir, partial_manifest)
        return PrepareResult(out_dir=request.out_dir, manifest=partial_manifest, artifacts=partial_refs)

    payload = acquisition.transcript_payload
    raw = parse_transcript_payload(payload, video_id=metadata.id)
    manifest.add_step("transcript.parse", "ok", raw.provenance.format)

    clean = normalize_transcript(raw)
    manifest.add_step("transcript.normalize", "ok", f"{len(clean.segments)} segments")

    transform_result = run_requested_transforms(
        clean,
        requests=request.ai_transforms,
        cache=cache,
    )
    clean = transform_result.transcript
    manifest.extend(transform_result.steps)

    chunks = chunk_transcript(
        clean,
        ChunkOptions(
            max_chars=request.chunk_max_chars,
            max_seconds=request.chunk_max_seconds,
        ),
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

    return PrepareResult(
        out_dir=request.out_dir,
        manifest=final_manifest,
        artifacts=artifact_refs,
    )
```

### `src/vctx/app/result.py`

```python
class PrepareResult(BaseModel):
    out_dir: Path
    manifest: Manifest
    artifacts: list[ArtifactRef]

    def artifact_path(self, kind: ArtifactKind) -> Path | None: ...
```

## Model function API

Models are the uniform internal language. Provider payloads must be converted into these models before entering core transformations.

### `src/vctx/models/metadata.py`

```python
class VideoMetadata(BaseModel): ...

def stable_metadata_id(metadata: VideoMetadata) -> str: ...
```

### `src/vctx/models/transcript.py`

```python
class TranscriptSegment(BaseModel): ...
class TranscriptProvenance(BaseModel): ...
class Transcript(BaseModel): ...
class TranscriptPayload(BaseModel): ...

def reassign_segment_ids(segments: Sequence[TranscriptSegment]) -> list[TranscriptSegment]: ...
def transcript_time_range(transcript: Transcript) -> TimeRange | None: ...
```

### `src/vctx/models/chunks.py`

```python
class ChunkOptions(BaseModel):
    max_chars: int = 6000
    max_seconds: int | None = None

class TranscriptChunk(BaseModel): ...
class ChunkSet(BaseModel): ...
```

### `src/vctx/models/artifacts.py`

```python
class Artifact(BaseModel):
    name: str
    kind: ArtifactKind
    media_type: str
    content: str | bytes

class ArtifactBundle(BaseModel):
    artifacts: list[Artifact]

    def get(self, kind: ArtifactKind) -> Artifact | None: ...
```

### `src/vctx/models/manifest.py`

```python
class ManifestStep(BaseModel): ...
class ArtifactRef(BaseModel): ...
class Manifest(BaseModel): ...

class ManifestBuilder:
    @classmethod
    def start(cls, input: str) -> ManifestBuilder: ...
    def add_step(self, name: str, status: StepStatus, detail: str | None = None) -> None: ...
    def warn(self, message: str) -> None: ...
    def finish(self, status: RunStatus, artifacts: list[ArtifactRef]) -> Manifest: ...
```

## Source adapter function API

### `src/vctx/sources/base.py`

```python
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
```

### `src/vctx/sources/detect.py`

```python
def detect_source_adapter(value: str) -> SourceAdapter:
    adapters: list[SourceAdapter] = [
        LocalFileSourceAdapter(),
        YtDlpSourceAdapter(),
    ]
    for adapter in adapters:
        if adapter.can_handle(value):
            return adapter
    raise UnsupportedSourceError(value)
```

Local files should be checked before URL fallback so `.vtt`, `.srt`, and transcript JSON inputs are deterministic and do not accidentally go through network extraction.

### `src/vctx/sources/ytdlp_source.py`

```python
class YtDlpSourceAdapter:
    name = "yt-dlp"

    def can_handle(self, value: str) -> bool:
        return looks_like_url(value)

    def extract_metadata(self, value: str) -> VideoMetadata: ...
    def extract_transcript(self, value: str, *, preferred_language: str | None, cache: Cache) -> TranscriptPayload: ...
```

Internal helper graph:

```text
extract_metadata(url)
  -> ytdlp_extract_info(url, download=False)
  -> metadata_from_ytdlp_info(info, original_url=url)

extract_transcript(url, preferred_language, cache)
  -> ytdlp_extract_info(url, download=False)
  -> choose_subtitle_track(info, preferred_language)
  -> fetch_subtitle_text(track, cache)
  -> TranscriptPayload(text, format, provenance)
```

Dependency use:

- `yt-dlp` only here
- standard `urllib` or `yt-dlp` subtitle download helper inside adapter only
- no renderer/chunker/model leakage from raw provider dictionaries

### `src/vctx/sources/local_file_source.py`

```python
class LocalFileSourceAdapter:
    name = "local-file"

    def can_handle(self, value: str) -> bool:
        return Path(value).exists() and Path(value).suffix.lower() in SUPPORTED_SUFFIXES

    def extract_metadata(self, value: str) -> VideoMetadata: ...
    def extract_transcript(self, value: str, *, preferred_language: str | None, cache: Cache) -> TranscriptPayload: ...
```

Supported suffixes initially:

```text
.vtt
.srt
.json
```

Plain `.txt` can be added later only if the warning and timestamp-loss behavior is explicit.

## Internal AI transformation function API

Internal AI transformations are optional source-preparation nodes. They are not chat, Q&A, memory, or final summarization features.

### Conceptual module layout

```text
src/vctx/transforms/
  __init__.py
  base.py
  routing.py
  result.py
  asr.py
  cleanup.py
  visual.py

src/vctx/transforms/providers/
  local_faster_whisper.py      # curated local ASR default when enabled
  local_ocr.py                 # curated local OCR default when enabled
  online_http.py               # curated online provider bridge when local quality is not enough
  external_command.py          # developer escape hatch, not primary UX
```

Provider modules should remain leaf adapters. Core pipeline code talks to the abstract transform API, not to provider SDKs directly.

### Request models

```python
TransformKind = Literal[
    "asr",
    "ocr",
    "frame_description",
    "transcript_cleanup",
    "chapter_suggestion",
    "language_detection",
    "route",
]

TransformProvider = Literal[
    "local",
    "free-online",
    "configured-online",
    "external-command",  # escape hatch only; not primary UX
]

class TransformRequest(BaseModel):
    kind: TransformKind
    provider: TransformProvider
    name: str | None = None       # e.g. faster-whisper, openai, local-vlm
    model: str | None = None
    options: dict[str, JsonValue] = {}
```

CLI should expose capability-level choices, not a broad provider menu. Examples:

```text
--asr auto             # curated route: subtitles -> local -> free-online if allowed
--asr local            # curated local ASR route
--asr online           # curated configured-online ASR route, explicit because it may cost/upload
--cleanup auto         # deterministic/local/free-online route when enabled
--cleanup local        # curated local cleanup if available
--cleanup online       # curated configured-online cleanup, explicit
--visual-context auto  # curated route: local OCR/VLM -> free-online if useful
--visual-context local
--visual-context online
```

The graph rule is stable: every AI/model-mediated transformation becomes an explicit `TransformRequest`, but the CLI should keep choices minimal. If multiple implementations can do the same job, choose the best project default instead of asking the user to choose among many raw providers.

### Adapter protocol

```python
class TransformAdapter(Protocol):
    kind: TransformKind
    provider: TransformProvider
    name: str

    def can_handle(self, request: TransformRequest) -> bool: ...

    def run(self, input: TransformInput, request: TransformRequest, cache: Cache) -> TransformResult: ...
```

### Input and result envelopes

```python
class TransformInput(BaseModel):
    metadata: VideoMetadata | None = None
    transcript: Transcript | None = None
    media: MediaAsset | None = None
    frames: list[FrameAsset] = []

class TransformEvidence(BaseModel):
    kind: TransformKind
    provider: TransformProvider
    name: str
    model: str | None = None
    source_artifacts: list[str] = []
    output_artifacts: list[str] = []
    deterministic: bool = False
    warnings: list[str] = []

class TransformResult(BaseModel):
    transcript: Transcript | None = None
    visual_records: list[VisualRecord] = []
    chapter_candidates: list[ChapterCandidate] = []
    language: str | None = None
    evidence: TransformEvidence
```

Transform results are converted back into normal internal records before chunking/rendering.

### ASR fallback graph

```text
acquire_transcript_or_media(input, asr=local)
  -> adapter.extract_transcript(...)
       -> if subtitles exist: TranscriptPayload
       -> if subtitles missing: NoTranscript
  -> adapter.extract_media(...)
  -> select_transform_adapter(kind="asr", provider="local")
  -> asr_adapter.run(media, request, cache)
  -> TranscriptPayload or Transcript
  -> manifest step: transform.asr
```

ASR is acceptable because its bounded behavior is:

```text
audio -> timestamped transcript
```

It must not produce final notes or answers.

### Transcript cleanup graph

```text
clean Transcript
  -> TransformRequest(kind="transcript_cleanup", provider=...)
  -> cleanup_adapter.run(transcript, request, cache)
  -> cleaned Transcript
  -> manifest step: transform.transcript_cleanup
  -> chunking
```

Cleanup must preserve timestamps and segment/source ids when practical. If a cleanup step rewrites text semantically, the manifest must make that visible.

### Visual enrichment graph

```text
media
  -> sample frames
  -> TransformRequest(kind="ocr" or "frame_description")
  -> visual_adapter.run(frames, request, cache)
  -> timestamped visual records
  -> optional visual artifacts
  -> manifest step: transform.visual
```

Visual records may later be rendered into `readable.md` or `context.md`, but the renderer still receives normalized records, not raw provider responses.

### Provider selection

```python
def select_transform_adapter(
    request: TransformRequest,
    adapters: Sequence[TransformAdapter],
) -> TransformAdapter:
    for adapter in adapters:
        if adapter.can_handle(request):
            return adapter
    raise UnsupportedTransformError(request)
```

Provider selection should be curated and small. It must not silently choose online providers. Online providers require explicit configuration and explicit request selection. External-command adapters are escape hatches for development or unusual integrations, not the recommended user workflow.

### Transformation route policy

The route policy chooses the best implementation for a capability with minimal user choice.

```text
Capability requested?
  -> no: skip
  -> yes/auto:
       use deterministic source data first when available
       else prefer curated local route if quality is good enough
       else use free zero-config online route if available, useful, and allowed by policy
       else require explicit configured-online route
       else fail clearly or write partial manifest
```

Recommended defaults by capability:

| Capability | Auto route | Local route | Free-online route | Configured-online route | Notes |
| --- | --- | --- | --- | --- | --- |
| ASR | subtitles first, then local ASR, then free-online if allowed | `faster-whisper` small/base | acceptable only if free, zero-config, stable enough, and upload behavior is clear | explicit `--asr online` if quality/speed requires it | ASR solves the no-transcript case. |
| OCR | local OCR first; free-online if local OCR is poor and allowed | curated local OCR | useful for slide/screenshot text if available without config | explicit online vision/OCR when quality matters | Keep OCR output timestamped by frame. |
| Frame description | local only if good; otherwise free-online/configured-online | local VLM only if efficient and good enough | preferred over weak local models if free/zero-config exists | likely best quality | Must be labeled as generated visual description. |
| Transcript cleanup | deterministic cleanup first, then local/free-online if enabled | small local cleanup model only if quality is good enough | acceptable for punctuation/format cleanup if no config/cost | explicit configured online cleanup for quality | Must preserve timestamps/source ids. |
| Chapter suggestion | deterministic/time-based first; model route optional | local if good enough | acceptable for rough chapter candidates | configured online if quality matters | Produces candidates, not final summary. |
| Language detection | lightweight local first | heuristic/library | free-online only if local fails | configured online rarely needed | Should not become a general LLM call by default. |

This policy keeps the interface small:

```text
--asr auto|local|online|off
--visual-context auto|local|online|off
--cleanup auto|local|online|off
--chapters auto|local|online|off
--allow-free-online / --no-allow-free-online
```

No provider-specific selection should appear unless necessary for configuration or debugging.

### Manifest requirements

Every transform step must add manifest evidence:

```text
transform.<kind>
  status: ok | skipped | warning | error
  provider: local | free-online | configured-online | external-command
  name: provider/tool name
  model: optional model id
  deterministic: false unless guaranteed
  source_artifacts: paths or ids used
  output_artifacts: paths or ids produced
```

This lets external agents inspect whether a context pack is purely subtitle-derived or model-mediated.

## Subtitle parser function API

### `src/vctx/subtitles/parse.py`

```python
def parse_transcript_payload(payload: TranscriptPayload, video_id: str) -> Transcript:
    if payload.format == "vtt":
        return parse_webvtt(payload, video_id=video_id)
    if payload.format == "srt":
        return parse_srt(payload, video_id=video_id)
    if payload.format == "json":
        return parse_transcript_json(payload, video_id=video_id)
    raise InvalidTranscriptError(payload.format)
```

### `src/vctx/subtitles/webvtt_parser.py`

```python
def parse_webvtt(payload: TranscriptPayload, *, video_id: str) -> Transcript: ...
```

Dependency: `webvtt-py`.

### `src/vctx/subtitles/srt_parser.py`

```python
def parse_srt(payload: TranscriptPayload, *, video_id: str) -> Transcript: ...
```

Dependency: `srt`.

## Transcript transformation function API

### `src/vctx/transcript/clean_text.py`

```python
def clean_subtitle_text(text: str) -> str:
    text = strip_subtitle_markup(text)
    text = normalize_whitespace(text)
    return text.strip()


def strip_subtitle_markup(text: str) -> str: ...
def normalize_whitespace(text: str) -> str: ...
```

### `src/vctx/transcript/normalize.py`

```python
def normalize_transcript(raw: Transcript) -> Transcript:
    segments = [clean_segment(seg) for seg in raw.segments]
    segments = [seg for seg in segments if seg.text]
    segments = sort_segments(segments)
    segments = merge_duplicate_segments(segments)
    segments = reassign_segment_ids(segments)
    return raw.model_copy(update={"segments": segments})
```

This layer must remain deterministic and non-semantic. It does not summarize, classify, or rewrite meaning.

## Chunking function API

### `src/vctx/chunking/tokens.py`

```python
def approximate_token_count(text: str) -> int:
    return max(1, len(text) // 4)
```

No default `tiktoken` or model-specific tokenizer.

### `src/vctx/chunking/chunker.py`

```python
def chunk_transcript(transcript: Transcript, options: ChunkOptions) -> ChunkSet:
    chunks: list[TranscriptChunk] = []
    pending: list[TranscriptSegment] = []

    for segment in transcript.segments:
        if pending and should_flush(pending, segment, options):
            chunks.append(build_chunk(len(chunks) + 1, pending))
            pending = []
        pending.append(segment)

    if pending:
        chunks.append(build_chunk(len(chunks) + 1, pending))

    if not chunks:
        raise EmptyChunksError(transcript.video_id)

    return ChunkSet(video_id=transcript.video_id, strategy="chars-v1", chunks=chunks)


def should_flush(pending: Sequence[TranscriptSegment], next_segment: TranscriptSegment, options: ChunkOptions) -> bool: ...
def build_chunk(index: int, segments: Sequence[TranscriptSegment]) -> TranscriptChunk: ...
```

Flush criteria:

```text
current_chars + next_chars > max_chars
or current_end - current_start > max_seconds when max_seconds is set
```

## Rendering function API

### `src/vctx/render/context_md.py`

```python
def render_context_markdown(
    metadata: VideoMetadata,
    transcript: Transcript,
    chunks: ChunkSet,
) -> str: ...
```

Output: `context.md`, matching `docs/api.md`.

Purpose: agent context injection.

### `src/vctx/render/readable_md.py`

```python
def render_readable_markdown(
    metadata: VideoMetadata,
    transcript: Transcript,
    chunks: ChunkSet,
) -> str: ...
```

Output: `readable.md`.

Purpose: human-readable review, still source-grounded.

### `src/vctx/render/transcript_md.py`

```python
def render_transcript_markdown(metadata: VideoMetadata, transcript: Transcript) -> str: ...
```

Output: `transcript.md`.

Purpose: timestamped cleaned transcript.

### `src/vctx/render/bundle.py`

```python
def render_artifact_bundle(
    *,
    metadata: VideoMetadata,
    raw_transcript: Transcript,
    clean_transcript: Transcript,
    chunks: ChunkSet,
    formats: set[OutputFormat],
) -> ArtifactBundle:
    artifacts = [
        json_artifact("metadata.json", "metadata", metadata),
        json_artifact("transcript.raw.json", "transcript_raw", raw_transcript),
        json_artifact("transcript.clean.json", "transcript_clean", clean_transcript),
        json_artifact("chunks.json", "chunks", chunks),
    ]
    if "context" in formats:
        artifacts.append(markdown_artifact("context.md", "context", render_context_markdown(...)))
    if "readable" in formats:
        artifacts.append(markdown_artifact("readable.md", "readable", render_readable_markdown(...)))
    if "transcript" in formats:
        artifacts.append(markdown_artifact("transcript.md", "transcript_md", render_transcript_markdown(...)))
    return ArtifactBundle(artifacts=artifacts)
```

Renderers are pure. They should be easy to snapshot-test.

## IO function API

### `src/vctx/io/cache.py`

```python
class Cache(BaseModel):
    root: Path

    def path_for(self, key: str) -> Path: ...


def build_cache(cache_dir: Path | None) -> Cache:
    root = cache_dir or platformdirs.user_cache_path("vctx")
    root.mkdir(parents=True, exist_ok=True)
    return Cache(root=root)
```

Dependency: `platformdirs`.

### `src/vctx/io/writer.py`

```python
def validate_output_policy(out_dir: Path, *, overwrite: bool) -> None: ...
def write_artifact_bundle(out_dir: Path, bundle: ArtifactBundle) -> list[ArtifactRef]: ...
def write_manifest(out_dir: Path, manifest: Manifest) -> ArtifactRef: ...
```

Pseudocode:

```python
def write_artifact_bundle(out_dir: Path, bundle: ArtifactBundle) -> list[ArtifactRef]:
    out_dir.mkdir(parents=True, exist_ok=True)
    refs = []
    for artifact in bundle.artifacts:
        final_path = out_dir / artifact.name
        temp_path = out_dir / f".{artifact.name}.tmp"
        write_content(temp_path, artifact.content)
        temp_path.replace(final_path)
        refs.append(ArtifactRef(kind=artifact.kind, path=artifact.name, media_type=artifact.media_type))
    return refs
```

Manifest should be written last so consumers never see a manifest that points at missing artifacts after a successful run.

## Utility function API

### `src/vctx/util/timefmt.py`

```python
def format_timestamp(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    # HH:MM:SS or HH:MM:SS.mmm when precision is needed
```

### `src/vctx/util/versions.py`

```python
def vctx_version() -> str: ...
def dependency_versions() -> dict[str, str]: ...
```

`doctor` and `manifest` can use these functions. Core transformations should not.

## Command-specific subgraphs

### `vctx metadata INPUT`

```text
metadata_command
  -> detect_source_adapter(input)
  -> adapter.extract_metadata(input)
  -> print metadata text or JSON
```

No output directory. No transcript extraction.

### `vctx chunk transcript.clean.json --out chunks.json`

```text
chunk_command
  -> read Transcript JSON
  -> validate as Transcript model
  -> chunk_transcript(transcript, options)
  -> write chunks JSON to --out
```

No network calls. No renderer.

### `vctx render ...`

```text
render_command
  -> read metadata/chunks/transcript JSON
  -> validate models
  -> render selected Markdown
  -> write selected output file
```

No network calls. No transcript normalization unless explicitly added as a separate command later.

### `vctx doctor`

```text
doctor_command
  -> check Python version
  -> check import versions
  -> check cache dir writability
  -> check optional ffmpeg availability
  -> print report
```

No network calls by default.

## Alignment with project principles

### CLI first

Every function graph starts at an explicit command and ends with explicit files or stdout.

### No embedded AI communication layer

The graph may include explicit internal AI transformation nodes such as ASR, OCR, frame description, cleanup, chapter suggestion, language detection, or routing.

There are still no graph nodes for chat, user-facing Q&A, memory, RAG, knowledge management, or final answer generation.

### Readable and machine-readable

The render bundle always includes JSON artifacts and Markdown artifacts unless the user narrows formats.

### Source-grounded

`TranscriptSegment.id`, timestamps, and `TranscriptChunk.segment_ids` preserve traceability from chunk back to transcript.

### Deterministic by default

Default graph uses subtitle extraction, deterministic normalization, deterministic chunking, and pure renderers.

### Explicit storage

Only `io.writer` writes durable output, and only under `--out`.

### Separate side effects

Side effects live in `cli`, `sources`, `io.cache`, and `io.writer`. Core modules are testable with in-memory models.

### Uniform internal representation

All adapters produce `VideoMetadata` and `TranscriptPayload`; all later stages consume `Transcript`, `ChunkSet`, and artifact models.

### Decoupled external integrations

`yt-dlp`, `webvtt-py`, `srt`, and `platformdirs` are each isolated to narrow modules.

## First implementation slice

Implement in this order:

1. `models/*`
2. `util/timefmt.py`
3. `transcript/clean_text.py`
4. `transcript/normalize.py`
5. `chunking/tokens.py`
6. `chunking/chunker.py`
7. `render/*.py`
8. `io/writer.py`
9. `subtitles/srt_parser.py` and `subtitles/webvtt_parser.py`
10. `sources/local_file_source.py`
11. `cli.py` local-file-only `prepare`
12. `sources/ytdlp_source.py`
13. URL-backed `prepare`

This sequence keeps early work testable and avoids beginning with the most side-effect-heavy integration.
