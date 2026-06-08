# vctx Verifiable Workflow Checklist

This document tracks what the implementation can actually do today versus what the module graphs in `docs/graph/` require.

The project should be developed as small, independently verifiable workflow slices. Each slice must say:

- what inputs it accepts
- what artifacts it must write
- what it must not do
- what command verifies it
- what failure mode is acceptable

This prevents the docs from promising an invisible monolith and lets users inspect exactly which part of the pipeline works today.

## Current implementation status

As of the current codebase, the implemented product surface is:

```text
vctx prepare   local .srt/.vtt/json transcript -> full context pack
vctx prepare   video URL with available subtitles -> full context pack
vctx prepare   --workflow metadata or no subtitles -> metadata-only partial pack
vctx metadata  local transcript or video URL -> normalized VideoMetadata
vctx chunk     existing Transcript JSON -> ChunkSet JSON
vctx render    existing metadata/transcript/chunks JSON -> Markdown
vctx doctor    local environment report
```

The current implementation is strongest for deterministic transcript/subtitle workflows. It has config resolution and transform route planning, but most model-mediated execution paths in `docs/graph/model-transforms.md` are not implemented yet.

## Missing functionality by graph module

### `docs/graph/app.md`

Implemented:

- `PrepareRequest` and `ResolvedConfig` models exist.
- Missing request fields resolve to default/auto values.
- `prepare_context_pack()` orchestrates source detection, metadata extraction, transcript parsing, normalization, chunking, rendering, artifact writing, and manifest writing.
- Workflow profiles exist: `default`, `transcript`, `visual`, `full`, `metadata`.

- `workflow=metadata` makes `vctx prepare` produce a metadata-only partial pack.
- Missing-subtitle sources write `metadata.json` + `manifest.json(status=partial)` instead of failing before artifacts.

Missing or incomplete:

- Config layering is not implemented yet:

  ```text
  BuiltInDefaults -> project config -> user config -> environment -> CLI/request overrides
  ```

  Current behavior is request/default resolution only; `config_path`, project config, user config, and environment-driven provider settings are placeholders.

- `prepare` only records an ASR planning skip for transcript-present flows. It does not invoke ASR fallback when transcript payload is missing.
- Cleanup, visual context, and chapters are planned in config/transform code, but not executed in the app workflow.

### `docs/graph/sources.md`

Implemented:

- `LocalFileSourceAdapter` for `.srt`, `.vtt`, and transcript JSON files.
- `YtDlpSourceAdapter` for `http/https` URLs.
- URL metadata extraction through `yt-dlp`.
- Official subtitle selection before automatic captions.
- Subtitle payload extraction into the shared `TranscriptPayload` contract.

Missing or incomplete:

- `extract_media()` / `MediaAsset` is not implemented. The graph requires source adapters to provide media only when ASR or visual context needs it.
- URL/video download for ASR fallback is not implemented.
- Frame/media acquisition for visual context is not implemented.
- Source-access errors are not yet normalized into a richer source error taxonomy beyond existing `VctxError` subclasses.

### `docs/graph/model-transforms.md`

Implemented:

- Route planning models and functions exist:

  ```text
  plan_asr
  plan_visual_context
  plan_cleanup
  plan_chapters
  ```

- Plans can return `skipped`, `deterministic`, `local`, `free-online`, `configured-online`, or `unavailable`.
- Offline policy disables network/upload routes.

Missing or incomplete:

- Execution APIs are not implemented:

  ```text
  run_asr
  run_visual_context
  run_cleanup
  run_chapters
  ```

- Adapter protocols/classes are not implemented:

  ```text
  AsrAdapter
  VisualAdapter
  CleanupAdapter
  ChapterAdapter
  ```

- Concrete adapters are missing:

  ```text
  local_asr / faster-whisper
  local_ocr
  free_online_asr
  free_online_vision
  configured_online_asr
  configured_online_vision
  configured/free text cleanup
  chapter suggestion
  ```

- Transform output models are missing or incomplete:

  ```text
  TransformResult
  VisualRecord
  ChapterCandidate
  MediaAsset
  FrameAsset
  ```

- Transform evidence is only partially represented by `RoutePlan.evidence_seed`; it is not yet written into manifest steps.

### `docs/graph/manifest.md`

Implemented:

- `Manifest`, `ManifestStep`, `ArtifactRef`, and `ManifestBuilder` exist.
- Successful prepare runs write `manifest.json`.
- Steps, artifacts, warnings, and run status are represented.

Missing or incomplete:

- `ManifestStep` does not yet include structured transform evidence.
- Provider/model/cost/upload/privacy fields from model-mediated steps are not recorded.
- Partial manifests for missing subtitles / unavailable optional capabilities are not yet produced by `prepare`.
- Error manifests are not written when the app fails early.

### `docs/graph/cli.md`

Implemented:

- Thin command surface exists for:

  ```text
  prepare
  metadata
  chunk
  render
  doctor
  ```

- Public flags avoid `--no-*` negation pairs.
- `--workflow` is the main decisive workflow instance selector for `prepare`.

Missing or incomplete:

- The graph says CLI should not write artifacts directly. Today, `chunk` and `render` command functions still write their output files inline after calling app helpers. This should move behind app use-case functions so CLI remains argument parsing + result printing only.
- `prepare` does not yet print partial-output guidance because partial prepare is not implemented.

### `docs/graph/io.md`

Implemented:

- Cache root construction exists.
- Output directory validation exists.
- Artifact bundle writing exists.
- Manifest writing exists.

Missing or incomplete:

- No explicit `CacheContext` model exists.
- No explicit `OutputPolicyResult` model exists.
- Temp asset lifecycle for downloaded media/frames is not implemented.
- `keep_temp` is accepted in request/config, but no media/temp workflow currently uses it.

### `docs/graph/render.md`

Implemented:

- Context Markdown renderer.
- Human-readable Markdown renderer.
- Transcript Markdown renderer.
- Artifact bundle rendering.
- Standalone `vctx render` command.

Missing or incomplete:

- Renderers do not yet include visual records, chapters, transform evidence, or partial-run warnings.
- `readable.md` and `context.md` do not reference frames or visual artifacts because those artifacts do not exist yet.

### `docs/graph/chunking.md`

Implemented:

- Character-budget chunking.
- Optional max-duration chunking.
- Stable chunk IDs.
- Segment ID preservation.
- Approximate token counts.
- Standalone `vctx chunk` command.

Missing or incomplete:

- No separate `ContextChunk` model exists.
- No chapter-aware or semantic chunking exists.
- No speaker-aware chunking exists.

### `docs/graph/transcript.md`

Implemented:

- Deterministic transcript normalization.
- Segment sorting.
- Basic text cleanup.
- Stable segment IDs.

Missing or incomplete:

- Empty segments are dropped, not separately flagged in an artifact/manifest.
- No speaker-label normalization.
- No model-mediated cleanup execution path.

### `docs/graph/subtitles.md`

Implemented:

- SRT parsing.
- WebVTT parsing.
- Transcript JSON parsing.
- Unified `Transcript` model output.

Missing or incomplete:

- Subtitle parser dependency behavior is minimal; richer malformed-subtitle diagnostics are not implemented.
- Provider subtitle metadata is preserved only through the current provenance fields, not full provider evidence.

### `docs/graph/models.md`

Implemented:

- Core Pydantic models exist for metadata, transcript, chunks, artifacts, and manifest.

Missing or incomplete:

- Model-transform records are incomplete or absent:

  ```text
  MediaAsset
  FrameAsset
  VisualRecord
  ChapterCandidate
  TransformResult
  structured TransformEvidence in manifest steps
  ```

- Partial/error run artifact contracts are not fully modeled.

## Capability levels

`vctx prepare` should be understood as a capability ladder, not a single all-or-nothing feature.

```text
Level 0: local transcript pack
Level 1: URL metadata inspection
Level 2: URL subtitle pack
Level 3: metadata-only / partial prepare for no-transcript sources
Level 4: auto-adapted ASR fallback
Level 5: optional visual/context enrichment
Level 6: optional internal AI cleanup/chapters
```

Current status:

| Level | Status | Notes |
| --- | --- | --- |
| 0 local transcript pack | Implemented and tested | `vctx prepare local.srt --out out` writes full pack. |
| 1 URL metadata inspection | Implemented and tested with mocked/unit coverage | `vctx metadata URL --json` uses `yt-dlp`. |
| 2 URL subtitle pack | Implemented in code path, needs real/network fixture strategy | `vctx prepare URL --out out` works when subtitles are available. |
| 3 metadata-only / partial prepare | Implemented and tested | `workflow=metadata` writes metadata-only partial output; missing subtitles produce metadata partial output. |
| 4 ASR fallback | Missing execution | Route planning exists; media acquisition and ASR adapters do not. |
| 5 visual/context enrichment | Missing execution | Route planning exists; frame extraction/OCR/VLM records do not. |
| 6 AI cleanup/chapters | Missing execution | Route planning exists; cleanup/chapter adapters and artifacts do not. |

Later levels should be added without breaking earlier levels.

## Level 0 — local transcript pack

Purpose:

```text
.srt/.vtt transcript file
  -> normalized transcript
  -> chunks
  -> JSON artifacts
  -> readable Markdown
  -> agent context Markdown
  -> manifest
```

This verifies the core internal pipeline without relying on network, video sites, subtitle availability, ffmpeg, ASR, or AI.

### Command

```bash
uv run vctx prepare ./examples/demo.srt --out ./out/demo
```

For an ad-hoc check:

```bash
mkdir -p .tmp
printf '1\n00:00:00,000 --> 00:00:01,000\nhello vctx\n' > .tmp/demo.srt
uv run vctx prepare .tmp/demo.srt --out .tmp/out --workflow transcript
```

### Required artifacts

```text
out/demo/
  manifest.json
  metadata.json
  transcript.raw.json
  transcript.clean.json
  transcript.md
  chunks.json
  context.md
  readable.md
```

### Required manifest properties

`manifest.json` must contain:

```json
{
  "schema_version": "0.1",
  "tool": "vctx",
  "status": "ok"
}
```

It must list at least these steps:

```text
source.detect
metadata.extract
transcript.extract
transform.asr
transcript.parse
transcript.normalize
chunk
```

It must list every durable artifact that was written.

### Required readability properties

`context.md` must contain:

```text
# Agent Context Pack
<chunk id="chunk_0001" start="00:00:00" end="...">
```

`readable.md` must contain human-readable timestamp sections.

`transcript.md` must contain timestamped transcript lines.

### Required failure behavior

If the output directory already contains files and `--overwrite` is not set, the command must fail without deleting existing files:

```bash
uv run vctx prepare ./demo.srt --out ./out/demo
# exit code 5
```

## Level 1 — URL metadata inspection

Purpose:

```text
video URL
  -> normalized metadata
```

This verifies URL handling through `yt-dlp` without requiring subtitles to exist.

### Command

```bash
uv run vctx metadata "https://www.youtube.com/watch?v=..." --json
```

### Required behavior

- Use `yt-dlp` only at the source-adapter boundary.
- Convert provider payload into `VideoMetadata` immediately.
- Do not leak raw provider dictionaries into chunking/rendering.
- Do not require subtitles.
- Do not run ASR.
- Do not call an LLM.

### Acceptable failure

If `yt-dlp` cannot access the URL, fail with a clear source-access error.

## Level 2 — URL subtitle pack

Purpose:

```text
video URL
  -> metadata
  -> official or automatic subtitles when available
  -> normalized transcript
  -> chunks
  -> artifacts
```

### Command

```bash
uv run vctx prepare "https://..." --out ./out/video
```

### Subtitle acquisition order

Default order:

```text
1. official subtitles matching --language
2. official subtitles in source/fallback language
3. automatic subtitles matching --language
4. automatic subtitles in source/fallback language
5. no transcript found
```

Local transcript files bypass this order and are parsed directly.

### Required behavior when subtitles exist

- Record whether subtitles were official or automatic.
- Record language and format.
- Preserve timestamps.
- Continue through the same internal transcript/chunk/render pipeline as Level 0.

### Required behavior when subtitles do not exist

Current behavior:

```text
fail clearly with NoTranscriptError before writing partial artifacts
```

Target behavior from the app/manifest graph:

```text
write metadata.json + manifest.json with status = partial
```

Preferred future manifest shape:

```json
{
  "status": "partial",
  "warnings": [
    "No subtitles found for selected language",
    "ASR route unavailable or not selected"
  ]
}
```

The warning should tell the caller what to do next:

```text
Provide a transcript file, install the default ASR extra, configure an online fallback, or use metadata-only output.
```

## Level 3 — metadata-only / partial prepare

Purpose:

```text
video URL or media input without transcript
  -> metadata.json
  -> manifest.json(status=partial)
```

This workflow is implemented. It closes the gap between URL metadata support and full URL subtitle packs by producing inspectable partial artifacts instead of failing before output.

### Commands

```bash
uv run vctx prepare "https://..." --out ./out/video --workflow metadata
uv run vctx prepare "https://..." --out ./out/video
```

The first command explicitly selects metadata-only output. The second command writes metadata-only partial output when subtitle extraction finds no transcript and ASR execution is unavailable.

### Required behavior

- Extract and write `metadata.json`.
- Write `manifest.json` with `status = partial`.
- Record `transcript.extract` as `warning` or `skipped` with an actionable detail.
- Do not create empty transcript/chunk/context artifacts.
- Do not run ASR, visual context, cleanup, chapters, or LLM calls.

## Level 4 — auto-adapted ASR fallback

Purpose:

```text
video URL or media file without subtitles
  -> audio extraction/download
  -> transcription
  -> normalized transcript
  -> context pack
```

### Target command

```bash
uv run vctx prepare "https://..." --out ./out/video
uv run vctx prepare ./lecture.mp4 --out ./out/lecture
```

The command stays simple. `vctx` routes to the curated default fallback when subtitles are missing and policy allows it.

### AI boundary

ASR is an AI/model step, but it is acceptable because it is a bounded internal transformation:

```text
audio -> timestamped transcript segments
```

It must not become a chat interface.

It must be explicit in the manifest.

### Required manifest properties

The manifest must say:

```text
route.selected = local | free-online | configured-online | unavailable
route.provider = faster-whisper or curated/default provider id
route.model = ...
route.cost_mode = local/free/configured/unknown
```

### Required behavior

- Do not run paid/configured cloud ASR unless configured by project/user policy.
- Do not hide long or costly work.
- Keep ASR provider types behind an adapter.
- Convert ASR result into the same `Transcript` model used by subtitles.

## Level 5 — optional visual/context enrichment

Purpose:

```text
video
  -> representative frames or OCR
  -> timestamp-associated visual artifacts
```

This level is optional. It should not block transcript-centric workflows.

### Target command examples

```bash
uv run vctx prepare "https://..." --out ./out/video --workflow visual
uv run vctx prepare "https://..." --out ./out/video --workflow transcript
```

### Required behavior

- Frame extraction and OCR are side-effecting adapter steps.
- Visual artifacts must be timestamped.
- `readable.md` may reference frames.
- `context.md` may reference frames in a machine-readable way.
- Do not make screenshots a knowledge base.

## Level 6 — optional internal AI cleanup/chapters

Purpose:

Use AI internally only when it improves source preparation, not to replace the external agent.

Acceptable internal AI examples:

```text
noisy transcript cleanup
speaker label normalization
chapter-boundary suggestion
language detection fallback
OCR/VLM frame description
ASR provider routing
```

Not acceptable as `vctx` default UI behavior:

```text
chat with the user
answer questions over the video
produce final study notes by default
maintain long-term memory
build cross-video knowledge graphs
```

### Required behavior

- AI steps must be explicit or clearly configured.
- The manifest must identify every AI-mediated step.
- Raw source text should remain available when practical.
- AI-generated transformations should not erase source timestamps.
- Online AI providers must not be called silently.

## Utility command verification

### `vctx metadata`

```bash
uv run vctx metadata ./demo.srt
uv run vctx metadata ./demo.srt --json
```

Automated test:

```bash
uv run pytest tests/test_metadata_command.py -q
```

### `vctx chunk`

```bash
uv run vctx chunk transcript.clean.json --out chunks.json --chunk-max-chars 6000
```

Automated test:

```bash
uv run pytest tests/test_chunk_command.py -q
```

### `vctx render`

```bash
uv run vctx render --metadata metadata.json --transcript transcript.clean.json --chunks chunks.json --out context.md --format context
uv run vctx render --metadata metadata.json --transcript transcript.clean.json --out transcript.md --format transcript
```

Automated test:

```bash
uv run pytest tests/test_render_command.py -q
```

### `vctx doctor`

```bash
uv run vctx doctor
```

Automated test:

```bash
uv run pytest tests/test_doctor_command.py -q
```

## Standard verification command

Every implemented level must pass:

```bash
uv run ruff check .
uv run ty check .
uv run pytest -q
```

The current implementation has automated coverage for the implemented deterministic surfaces:

```bash
uv run pytest tests/test_local_prepare.py tests/test_ytdlp_source.py tests/test_metadata_command.py tests/test_chunk_command.py tests/test_render_command.py tests/test_doctor_command.py -q
```

## Recommended next implementation order

Based on the graph gaps, implement in this order:

1. **Move CLI file writing behind app use cases**
   - Add app-level `chunk_existing_transcript()` and `render_existing_artifacts()` result objects.
   - Keep CLI as parse arguments -> call app -> print result paths.

2. **Manifest evidence schema**
   - Add structured evidence to manifest steps.
   - Record route/provider/model/cost/upload/privacy for transform plans.

3. **Source media asset contract**
   - Add `MediaAsset` and optional `SourceAdapter.extract_media()`.
   - Keep downloads lazy: only when ASR/visual workflows require media.

4. **ASR execution adapter**
   - Implement `run_asr()` and one curated default route.
   - Convert ASR output into `TranscriptPayload` / `Transcript` without changing downstream pipeline.

5. **Visual records and rendering**
   - Add frame extraction, `VisualRecord`, and renderer support.
   - Keep visual workflows optional and timestamped.

6. **Cleanup and chapters**
   - Implement only after evidence/manifest structure is solid.
   - Preserve raw transcript and timestamps.

## Release checklist for a new capability

Before claiming a level or sub-feature is implemented:

- [ ] The command exists.
- [ ] The accepted input shape is documented.
- [ ] The output artifacts are documented.
- [ ] The manifest records what happened.
- [ ] Failure behavior is documented and tested.
- [ ] The feature has at least one automated test where practical.
- [ ] The feature preserves timestamps when transcript/video time exists.
- [ ] Side effects stay at adapter/IO boundaries.
- [ ] Provider-specific payloads do not leak into core models.
- [ ] CLI help avoids vague `--no-*` negation pairs.
- [ ] `uv run ruff check .` passes.
- [ ] `uv run ty check .` passes.
- [ ] `uv run pytest -q` passes.

## How a user or agent should inspect a run

After any successful or partial run, inspect in this order:

```text
1. manifest.json       What happened? What failed? What artifacts exist?
2. metadata.json       What source was processed?
3. transcript.clean.json / chunks.json
                       What timestamped text exists?
4. context.md          What should an AI agent inject?
5. readable.md         What should a human open?
```

This inspection order is the practical contract between `vctx` and an external AI agent.
