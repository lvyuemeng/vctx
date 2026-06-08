# vctx Architecture

## Purpose

This document turns the project abstractions into a concrete initial module layout, data flow, and pseudocode for `vctx`.

The layout is concrete enough to implement, but the architectural rule remains: external integrations stay at the edges, internal models stay uniform, and pure transformations stay separate from side effects.

## System overview

`vctx` is a CLI pipeline:

```text
User / agent
  -> CLI command
  -> application use case
  -> source adapter
  -> internal metadata + transcript models
  -> transcript normalization
  -> chunking
  -> rendering
  -> artifact writing
  -> manifest + stdout result
```

The output directory is the integration boundary for downstream agents.

## Concrete module layout

Initial package layout:

```text
src/vctx/
  __init__.py
  __main__.py
  cli.py

  app/
    __init__.py
    prepare.py
    errors.py
    result.py

  models/
    __init__.py
    common.py
    metadata.py
    transcript.py
    chunks.py
    artifacts.py
    manifest.py

  sources/
    __init__.py
    base.py
    detect.py
    ytdlp_source.py
    local_file_source.py

  subtitles/
    __init__.py
    parse.py
    webvtt_parser.py
    srt_parser.py

  transcript/
    __init__.py
    normalize.py
    clean_text.py

  chunking/
    __init__.py
    chunker.py
    tokens.py

  render/
    __init__.py
    context_md.py
    readable_md.py
    transcript_md.py

  io/
    __init__.py
    cache.py
    writer.py
    json_dump.py

  util/
    __init__.py
    timefmt.py
    paths.py
    versions.py
```

Keep this layout boring. Do not add `services`, `managers`, or framework-style layers unless a real need appears.

## Dependency use by stage

| Stage | Modules | Dependencies | Side effects? | Output |
| --- | --- | --- | --- | --- |
| CLI parsing | `cli.py` | `typer`, optionally `rich` via Typer standard extras | stdout/stderr only | `PrepareOptions` / command invocation |
| Use-case orchestration | `app/prepare.py` | standard library, internal models | coordinates side effects | `PrepareResult` |
| Source detection | `sources/detect.py` | standard library URL/path checks | no, except path existence checks | `SourceAdapter` |
| URL metadata/subtitles | `sources/ytdlp_source.py` | `yt-dlp` Python API | network / extractor calls | `VideoMetadata`, raw subtitle files or text |
| Local file input | `sources/local_file_source.py` | standard library | file reads | metadata or imported transcript |
| Subtitle parsing | `subtitles/*` | `webvtt-py`, `srt` | no once text/file is available | `RawTranscript` |
| Normalization | `transcript/*` | standard library, `pydantic` models | no | `CleanTranscript` |
| Chunking | `chunking/*` | standard library | no | `ChunkSet` |
| Rendering | `render/*` | standard library | no | Markdown strings / serializable JSON |
| Artifact writing | `io/writer.py` | standard library | filesystem writes | files in `--out` |
| Cache paths | `io/cache.py`, `util/paths.py` | `platformdirs` | creates/uses cache dirs when needed | cache paths |
| Manifest | `models/manifest.py`, `io/json_dump.py` | `pydantic`, standard JSON | no until writer writes | `manifest.json` |

## User interaction model

`vctx` is non-interactive by default.

Primary command:

```bash
vctx prepare URL_OR_PATH --out DIR
```

Expected user-visible behavior:

1. Parse options.
2. Fail early if input is empty or output policy is invalid.
3. Print concise progress to stderr or terminal progress UI.
4. Write artifacts to `--out`.
5. Print final artifact paths to stdout.
6. Return exit code `0` on success.

Example stdout:

```text
Wrote context pack: ./out/video-001
Manifest: ./out/video-001/manifest.json
Context: ./out/video-001/context.md
Readable: ./out/video-001/readable.md
```

Warnings go to stderr and into the manifest:

```text
warning: official subtitles not found; used automatic subtitles
```

Errors should be actionable:

```text
error: no transcript found for URL; rerun with --asr local after installing the asr extra
```

No command should ask the user questions during normal operation. If a decision is required, expose it as a flag.

## Command-level data flow

### `vctx prepare`

Input:

```text
URL_OR_PATH
--out DIR
--language LANG?              # optional preferred subtitle language
--overwrite / --no-overwrite  # default no-overwrite
--chunk-max-chars INT         # default deterministic chunking
--chunk-max-seconds INT?      # optional duration cap
--cache-dir DIR?              # optional override
--keep-temp                   # optional; default false
--format context,readable,transcript,json
```

Output directory:

```text
DIR/
  manifest.json
  metadata.json
  transcript.raw.json
  transcript.clean.json
  transcript.md
  chunks.json
  context.md
  readable.md
```

Pipeline:

```text
PrepareRequest
  -> select SourceAdapter
  -> extract metadata
  -> extract transcript/subtitles
  -> parse subtitle format into RawTranscript
  -> normalize transcript into CleanTranscript
  -> chunk clean transcript into ChunkSet
  -> render artifacts
  -> write artifacts
  -> write manifest
  -> return PrepareResult
```

Pseudocode:

```python
def prepare(request: PrepareRequest) -> PrepareResult:
    run = ManifestBuilder.start(request)

    out_dir = validate_output_dir(request.out_dir, overwrite=request.overwrite)
    cache = Cache.from_options(request.cache_dir)

    adapter = detect_source(request.input)
    run.step("source.detect", status="ok", detail=adapter.name)

    metadata = adapter.extract_metadata(request.input)
    run.step("metadata.extract", status="ok")

    transcript_payload = adapter.extract_transcript(
        request.input,
        preferred_language=request.language,
        cache=cache,
    )
    run.step(
        "transcript.extract",
        status="ok",
        detail=transcript_payload.provenance,
    )

    raw_transcript = parse_transcript_payload(transcript_payload)
    clean_transcript = normalize_transcript(raw_transcript)

    chunks = chunk_transcript(
        clean_transcript,
        max_chars=request.chunk_max_chars,
        max_seconds=request.chunk_max_seconds,
    )

    artifacts = build_artifacts(
        metadata=metadata,
        raw_transcript=raw_transcript,
        clean_transcript=clean_transcript,
        chunks=chunks,
        manifest=run.preview(),
        formats=request.formats,
    )

    written = write_artifacts(out_dir, artifacts)
    manifest = run.finish(status="ok", artifacts=written)
    write_manifest(out_dir, manifest)

    return PrepareResult(out_dir=out_dir, manifest=manifest, artifacts=written)
```

## Internal models

Use Pydantic v2 models for internal boundaries and artifact serialization.

### Common primitives

```python
class TimeRange(BaseModel):
    start: float
    end: float | None = None

class SourceRef(BaseModel):
    kind: Literal["url", "file"]
    value: str
```

### Metadata

```python
class VideoMetadata(BaseModel):
    id: str
    source_type: str
    source: SourceRef
    title: str | None = None
    uploader: str | None = None
    duration_seconds: float | None = None
    webpage_url: str | None = None
    language: str | None = None
    extractor: str | None = None
    raw_provider: str | None = None
```

Artifact: `metadata.json`.

### Transcript

```python
class TranscriptSegment(BaseModel):
    id: str
    start: float
    end: float | None = None
    text: str
    source_id: str | None = None

class TranscriptProvenance(BaseModel):
    method: Literal["official_subtitles", "automatic_subtitles", "local_file", "asr"]
    language: str | None = None
    format: Literal["vtt", "srt", "json", "plain", "unknown"] = "unknown"
    provider: str | None = None

class Transcript(BaseModel):
    video_id: str
    provenance: TranscriptProvenance
    segments: list[TranscriptSegment]
```

Artifacts:

```text
transcript.raw.json
transcript.clean.json
transcript.md
```

### Chunks

```python
class TranscriptChunk(BaseModel):
    id: str
    start: float
    end: float | None
    text: str
    segment_ids: list[str]
    char_count: int
    approx_token_count: int

class ChunkSet(BaseModel):
    video_id: str
    strategy: str
    chunks: list[TranscriptChunk]
```

Artifact: `chunks.json`.

### Manifest

```python
class ManifestStep(BaseModel):
    name: str
    status: Literal["ok", "skipped", "warning", "error"]
    detail: str | None = None

class ArtifactRef(BaseModel):
    kind: str
    path: str
    media_type: str

class Manifest(BaseModel):
    schema_version: str = "0.1"
    tool: str = "vctx"
    tool_version: str
    status: Literal["ok", "partial", "error"]
    input: str
    artifacts: list[ArtifactRef]
    steps: list[ManifestStep]
    warnings: list[str] = []
```

Artifact: `manifest.json`.

## Source adapters

### Interface

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

### `YtDlpSourceAdapter`

Use for URLs supported by `yt-dlp`.

Dependency:

```python
yt_dlp.YoutubeDL
```

Rules:

- Use `download=False` for metadata.
- Prefer subtitles over audio download.
- Prefer requested language when present.
- Prefer official subtitles over automatic captions.
- Do not expose raw `yt-dlp` dictionaries outside the adapter.
- Record extractor and subtitle provenance.

Pseudocode:

```python
class YtDlpSourceAdapter:
    name = "yt-dlp"

    def extract_metadata(self, url: str) -> VideoMetadata:
        info = ytdlp_extract(url, download=False)
        return VideoMetadata(
            id=stable_video_id(info),
            source_type=info.get("extractor_key", "unknown"),
            source=SourceRef(kind="url", value=url),
            title=info.get("title"),
            uploader=info.get("uploader"),
            duration_seconds=info.get("duration"),
            webpage_url=info.get("webpage_url"),
            extractor=info.get("extractor"),
        )

    def extract_transcript(...):
        info = ytdlp_extract(url, download=False)
        subtitle_choice = choose_subtitle(info, preferred_language)
        if not subtitle_choice:
            raise NoTranscriptError(...)
        subtitle_text = download_subtitle(subtitle_choice, cache)
        return TranscriptPayload(text=subtitle_text, format=subtitle_choice.ext, provenance=...)
```

### `LocalFileSourceAdapter`

Use for local transcript files first; local audio/video support can come later.

Initial support:

```text
.vtt
.srt
.json transcript artifact
.txt plain transcript without timestamps, if explicitly allowed
```

Rules:

- Timestamped transcript files are preferred.
- Plain `.txt` loses timestamp grounding and should produce a warning.
- Local media files requiring ASR are optional later.

## Subtitle parsing

`parse_transcript_payload(payload)` dispatches by format:

```python
def parse_transcript_payload(payload: TranscriptPayload) -> Transcript:
    match payload.format:
        case "vtt":
            return parse_webvtt(payload)
        case "srt":
            return parse_srt(payload)
        case "json":
            return parse_json_transcript(payload)
        case "plain":
            return parse_plain_text(payload)
        case _:
            raise InvalidTranscriptError(...)
```

Dependencies:

- `webvtt-py` for VTT
- `srt` for SRT
- standard `json` for JSON artifacts

## Normalization

Input: `Transcript`.

Output: `Transcript` with cleaned segments.

Pseudocode:

```python
def normalize_transcript(raw: Transcript) -> Transcript:
    segments = []
    for seg in raw.segments:
        text = clean_subtitle_text(seg.text)
        if not text:
            continue
        segments.append(seg.model_copy(update={"text": text}))

    segments = sort_by_start(segments)
    segments = merge_duplicate_or_overlapping_segments(segments)
    return raw.model_copy(update={"segments": reassign_segment_ids(segments)})
```

No summarization. No semantic rewriting.

## Chunking

Default strategy: deterministic character-budget chunking with timestamp preservation.

Inputs:

```text
CleanTranscript
max_chars
max_seconds optional
```

Output:

```text
ChunkSet
```

Pseudocode:

```python
def chunk_transcript(transcript: Transcript, max_chars: int, max_seconds: int | None) -> ChunkSet:
    chunks = []
    current = []

    for segment in transcript.segments:
        if should_flush(current, segment, max_chars, max_seconds):
            chunks.append(build_chunk(current))
            current = []
        current.append(segment)

    if current:
        chunks.append(build_chunk(current))

    if not chunks:
        raise EmptyChunksError(...)

    return ChunkSet(video_id=transcript.video_id, strategy="chars-v1", chunks=chunks)
```

Approximate token count:

```python
def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)
```

Do not add model-specific tokenizers by default.

## Rendering

### `context.md`

Audience: AI agents.

Characteristics:

- compact metadata
- explicit usage note
- chunk boundaries with ids and timestamps
- source text preserved
- easy to parse from context

Example shape:

```markdown
# Agent Context Pack

## Metadata

- Title: ...
- URL: ...
- Duration: ...
- Transcript source: official_subtitles

## Chunks

<chunk id="chunk_001" start="00:00:00" end="00:03:20">
...
</chunk>
```

### `readable.md`

Audience: humans.

Characteristics:

- pleasant Markdown
- readable section headings by time range
- no XML-like tags
- no generated summary by default

### `transcript.md`

Audience: human debugging and source review.

Characteristics:

- timestamped transcript segments
- minimal formatting
- close to the cleaned transcript

## Artifact writing

Write order:

1. Validate output directory policy.
2. Write data artifacts to temporary files.
3. Atomically replace final files where possible.
4. Write Markdown artifacts.
5. Write `manifest.json` last.

Pseudocode:

```python
def write_artifacts(out_dir: Path, artifacts: ArtifactBundle) -> list[ArtifactRef]:
    ensure_output_dir(out_dir)
    refs = []
    for artifact in artifacts:
        tmp = out_dir / f".{artifact.name}.tmp"
        tmp.write_text(artifact.content, encoding="utf-8")
        tmp.replace(out_dir / artifact.name)
        refs.append(artifact.ref)
    return refs
```

## Error handling

Use domain errors under `app/errors.py`:

```python
class VctxError(Exception): ...
class UnsupportedSourceError(VctxError): ...
class MetadataExtractionError(VctxError): ...
class NoTranscriptError(VctxError): ...
class InvalidTranscriptError(VctxError): ...
class OutputExistsError(VctxError): ...
class EmptyChunksError(VctxError): ...
```

CLI maps errors to exit codes:

| Exit code | Meaning |
| --- | --- |
| `0` | success |
| `1` | generic failure |
| `2` | invalid CLI usage/options |
| `3` | unsupported source |
| `4` | transcript unavailable |
| `5` | output error |

## AI boundary

No AI dependency in the default architecture.

Later optional AI-mediated internals must be adapters:

```text
asr/local_whisper_adapter.py
ocr/tesseract_adapter.py
chunking/topic_boundary_adapter.py
```

Rules:

- optional extra dependency
- explicit CLI flag
- no chat interface
- no cloud provider SDK by default
- record step and provider in manifest

## Implementation order

1. Define Pydantic models.
2. Implement timestamp formatting utilities.
3. Implement transcript normalization.
4. Implement deterministic chunking.
5. Implement Markdown renderers.
6. Implement artifact writer and manifest.
7. Implement local `.vtt` / `.srt` transcript input.
8. Implement `yt-dlp` URL metadata/subtitle extraction.
9. Wire `vctx prepare`.
10. Add tests around pure transformations and one CLI smoke test.
