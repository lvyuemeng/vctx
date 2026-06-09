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

The current implementation is strongest for deterministic transcript/subtitle workflows and ASR fallback. It has config resolution, transform route planning, local faster-whisper ASR, configured OpenAI-compatible ASR, URL media download for ASR, transform evidence in manifests, and explicit visual/full workflow capture plus local RapidOCR text extraction and configured OpenAI-compatible VLM descriptions. Cleanup and chapter model-mediated execution paths in `docs/graph/model-transforms.md` remain mostly planned.

## Missing functionality by graph module

### `docs/graph/app.md`

Implemented:

- `PrepareRequest` and `ResolvedConfig` models exist.
- Missing request fields resolve to default/auto values.
- Optional TOML `--config` loading exists for runtime/source/output/transform/provider defaults.
- Configured provider entries are parsed into `ResolvedConfig.providers` without exposing provider menu flags.
- CLI/request values override config defaults where current request shape can distinguish the override.
- `prepare_context_pack()` orchestrates source detection, metadata extraction, transcript parsing, normalization, chunking, rendering, artifact writing, and manifest writing.
- Workflow profiles exist: `default`, `transcript`, `visual`, `full`, `metadata`.

- `workflow=metadata` makes `vctx prepare` produce a metadata-only partial pack.
- Missing-subtitle sources write `metadata.json` + `manifest.json(status=partial)` instead of failing before artifacts.

Missing or incomplete:

- Full config layering is incomplete:

  ```text
  BuiltInDefaults -> explicit --config file -> CLI/request overrides
  ```

  Project config discovery, user config discovery, and environment-derived provider availability are not implemented yet.

- Cleanup, visual context execution, and chapters are planned in config/transform code, but not executed in the app workflow.

### `docs/graph/sources.md`

Implemented:

- `LocalFileSourceAdapter` for `.srt`, `.vtt`, and transcript JSON files.
- `YtDlpSourceAdapter` for `http/https` URLs.
- URL metadata extraction through `yt-dlp`.
- Official subtitle selection before automatic captions.
- Subtitle payload extraction into the shared `TranscriptPayload` contract.

Missing or incomplete:

- `extract_media()` / `MediaAsset` is implemented for local media files (`.wav`, `.mp3`, `.m4a`, `.mp4`, `.webm`).
- URL/video download for ASR fallback is implemented through yt-dlp into `runtime.cache_dir/media/yt-dlp`.
- Frame/media acquisition for explicit visual/full workflow capture is implemented for local/URL media when video media can be acquired.
- Evidence-guided frame-anchor acquisition for visual context is not implemented yet.
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
- ASR planning uses configured provider identity/model from policy/environment when configured-online is selected.
- Paid configured ASR routes are rejected unless policy sets `allow_paid=true`.

Missing or incomplete:

- Execution APIs implemented:

  ```text
  run_asr
  run_visual_context      # sample + capture + local RapidOCR + configured VLM slice
  ```

- Execution APIs not implemented:

  ```text
  run_cleanup
  run_chapters
  ```

- `run_asr()` exists for local `local-faster-whisper` and configured `openai-compatible-audio` instances.

- Adapter protocols/classes are partially implemented:

  ```text
  RapidOcrAdapter
  OpenAiCompatibleVisionAdapter
  ```

- Adapter protocols/classes are not implemented:

  ```text
  AsrAdapter
  VisualAdapter
  CleanupAdapter
  ChapterAdapter
  ```

- Concrete adapters/routes are missing or incomplete:

  ```text
  configured/free text cleanup
  chapter suggestion
  ```

- Transform output models are partially implemented:

  ```text
  MediaAsset
  FrameAsset
  VisualRecord
  ```

- Transform output models still missing or incomplete:

  ```text
  ChapterCandidate
  TransformResult
  structured TransformEvidence in manifest steps
  ```

- Transform evidence is written to `manifest.transform_evidence` for ASR planning/execution.
- Deterministic full CLI integration tests cover local media -> fake faster-whisper ASR and URL -> yt-dlp media download -> ASR -> transcript/chunks/context pack.

Implemented ASR execution slice:

- `MediaAsset` model exists.
- Local media files can be detected and exposed as `MediaAsset`.
- URL media can be downloaded through yt-dlp for ASR fallback.
- `run_asr()` exists for local `local-faster-whisper` and configured `openai-compatible-audio` instances.
- `FasterWhisperAsrAdapter` performs real transcription when the optional ASR extra is installed; without the extra it raises an actionable error.
- `OpenAiCompatibleAsrAdapter` performs multipart audio POSTs using a selected instance and credential resolved from shell env/`runtime.env_files`.
- Persistent model cache, offline/no-download behavior, credential redaction, and cache-write errors are unit-tested.
- `prepare` can fall back from missing local/URL transcript to ASR and then continue through parse/normalize/chunk/render.

### `docs/graph/manifest.md`

Implemented:

- `Manifest`, `ManifestStep`, `ArtifactRef`, and `ManifestBuilder` exist.
- Successful prepare runs write `manifest.json`.
- Steps, artifacts, warnings, and run status are represented.

- Structured ASR transform evidence is recorded in `manifest.transform_evidence`, including provider/model/upload/cost route evidence.

Missing or incomplete:

- Non-ASR provider/model/cost/upload/privacy fields are not recorded because those model-mediated steps are not implemented.
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

- Renderers include visual capture records, OCR text records, VLM description records, and frame artifact references when explicit visual/full workflows produce them.
- Renderers do not yet include chapters, transform evidence, or partial-run warnings.

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
| 2 URL subtitle pack | Implemented and fixture-tested; optional network smoke available | `vctx prepare URL --out out` writes full pack when subtitles are available. |
| 3 metadata-only / partial prepare | Implemented and tested | `workflow=metadata` writes metadata-only partial output; missing subtitles produce metadata partial output. |
| 4 ASR fallback | Implemented and tested | URL/local media can flow through local faster-whisper or configured OpenAI-compatible ASR; manifest records route evidence. |
| 5 visual/context enrichment | Configured VLM + prefix/auto OpenRouter VLM + deterministic essential-case sampling + novelty scoring slices implemented | Explicit visual/full workflows can plan sample+OCR+describe+capture when current provider-alias routes are available, extract PNG frame artifacts, write `visual_records.json`, and render kept OCR/description/frame refs. Deterministic transcript cues now produce typed essential visual cases, window-deduped `sample(strategy="essential_cases")` anchors, and frame extraction at transcript-anchor timestamps. Prefix resolver can wire explicit `transforms.visual_context.model = "openrouter:<model-id>"` into visual route discovery/execution, and `model = "auto"` now uses cached/fetched OpenRouter registry metadata to select a free text+image VLM when `OPENROUTER_API_KEY` exists. OCR/VLM records receive deterministic novelty/overlap/grounding scores plus prior/posterior uncertainty direction; low-novelty text records are omitted from rendered context but retained in `visual_records.json`. LLM essential-case extraction remains missing. |
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

### Test strategy

Level 2 is covered by a deterministic mocked-`yt-dlp` fixture test that invokes the real `vctx prepare URL --out OUT` CLI and verifies the full artifact contract. This is the required always-on test because it is stable, fast, and does not depend on public video-site behavior.

Real network verification is optional and manual:

```bash
VCTX_SMOKE_VIDEO_URL="https://..." uv run python scripts/smoke_url_subtitles.py
```

Real local ASR verification is also optional because it may install/download `faster-whisper` dependencies and model weights:

```bash
uv sync --extra asr
VCTX_ASR_SMOKE_MEDIA="./sample.wav" uv run python scripts/smoke_local_asr.py
```

The first real ASR run may download a model into the persistent vctx cache. Use `runtime.offline = true` only after the model is already cached or when `model` points to a local model path.

Do not put a public video URL into normal tests by default. Captions, rate limits, cookies, geo availability, model hosting, and extractor behavior change independently of this project.

### Required behavior when subtitles do not exist

Current behavior:

```text
write metadata.json + manifest.json with status = partial
```

Manifest warning shape:

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

### Proposed ASR model design

Keep ASR as a bounded model transform, not a user-facing AI chat surface.

Core records:

```text
MediaAsset
  id: str
  source_uri: str | path
  local_path: Path | None
  media_type: audio | video
  container: mp3 | m4a | wav | mp4 | webm | unknown
  duration_seconds: float | None
  language_hint: str | None
  provenance: source adapter + extraction command/evidence

AsrOptions
  language: str | None
  timestamp_granularity: segment | word
  compute_policy: local-default | local-fast | local-quality | configured-online

AsrAdapter
  provider_id: str
  model_id: str
  transcribe(media_asset, options) -> TranscriptPayload
```

ASR returns the existing transcript boundary type:

```text
TranscriptPayload
  text: subtitle-like serialized text or normalized provider text
  format: vtt | srt | json | plain | unknown
  provenance:
    method = asr
    provider = faster-whisper | configured provider id
    language = detected/requested language
```

Then the existing pipeline remains unchanged:

```text
TranscriptPayload
  -> parse_transcript_payload()
  -> normalize_transcript()
  -> chunk_transcript()
  -> render_artifact_bundle()
```

### Proposed default ASR route

Use one best default instead of a provider menu:

```text
1. If subtitles exist: do not run ASR.
2. If media is unavailable: partial metadata output with ASR unavailable evidence.
3. If local ASR extra is installed: run local faster-whisper default adapter.
4. If a curated free/no-config online ASR route exists and policy allows network/upload: use it only when materially better or local is unavailable.
5. If user/project configured an online ASR provider and policy allows upload: use configured-online.
6. Otherwise: write partial metadata output with actionable ASR requirements.
```

Initial practical default:

```text
local ASR adapter: faster-whisper
optional dependency group: asr
model policy: auto-select one local default by hardware/cache
CPU default: base or small int8
GPU default: small or medium when available
```

No external command adapter should be the primary UX. Shelling to `ffmpeg` is acceptable for media conversion because it is an infrastructure tool, not the ASR provider UX.

### Online ASR route policy

Do not invent or silently depend on a public online ASR service.

`free-online` means a project-shipped registry entry that has all of these properties:

```text
- no user account required
- no API key required
- no payment required
- license/terms allow this use
- stable enough for automated fallback
- explicit upload disclosure in manifest
- deterministic request/response adapter tested with fixtures
```

If no such registry entry exists, `free-online` is simply unavailable and the planner should not select it. The first Level 4 implementation should therefore ship with:

```text
free_online_registry.asr = None
```

and prefer local ASR.

Configured online ASR is different: the user explicitly selects a composable ASR instance. Public config should be shaped like this:

```toml
[runtime]
env_files = [".env"]

[transforms.asr]
instance = "openai-whisper"

[instances.asr.local-default]
type = "local-faster-whisper"
model_policy = "auto"
# model ids use managed persistent cache under runtime.cache_dir/models/

[instances.asr.local-model]
type = "local-faster-whisper"
model = "D:/models/faster-whisper-tiny"  # explicit path => no managed cache/download

[instances.asr.openai-whisper]
type = "openai-compatible-audio"
base_url = "https://api.openai.com/v1/audio/transcriptions"
api_key_env = "OPENAI_API_KEY"
model = "whisper-1"
cost = "paid"
upload = "required"
```

Rules:

```text
- Local vs online is separated by instance type, not by boolean route flags.
- Explicitly naming an online instance is the positive user action that permits upload/cost evidence for that instance.
- API keys are referenced by environment variable name, not stored in config.
- `runtime.env_files` can point at `.env` files for convenient local credential loading.
- Normal users should not need provider flags; config names a reusable instance.
- If `model` is an explicit local path, vctx treats the instance as local-only: no managed cache, no model download, and no separate cache flag needed.
- If managed cache is full or unwritable, the error should suggest freeing space, moving `runtime.cache_dir`, or using an explicit local model path.
```

### Local ASR model storage

For `faster-whisper`, model files should be stored under the normal vctx cache root, not inside output packs:

```text
<cache-root>/models/faster-whisper/<model-id>/
```

Default cache root:

```text
platformdirs.user_cache_path("vctx", appauthor=False)
```

On this Windows dev machine that resolves to:

```text
C:\Users\nostalgia\AppData\Local\vctx\Cache
```

Request override:

```bash
vctx prepare input.mp4 --out out --cache-dir ./.cache/vctx
```

Artifact output remains separate:

```text
out/                 # manifest/transcript/chunks/rendered artifacts
cache/models/...     # reusable ASR model weights
cache/media/...      # temporary/downloaded media assets
```

The manifest should record the model id and cache location class, but not dump large model paths unless useful for debugging.

When `model` is a filesystem path, the instance is a local-model instance. In that case vctx does not pass a `download_root`, forces `local_files_only`, and does not require a separate `cache = "disabled"` setting. This avoids mixed config semantics.

### Local ASR model auto-selection

Auto-selection should be conservative and deterministic. It should inspect local capability before downloading a model:

```text
1. Detect CUDA availability through faster-whisper/CTranslate2 if installed.
2. Detect available RAM and, when CUDA exists, available VRAM.
3. Inspect media duration.
4. Choose the smallest model expected to be useful and finish reliably.
5. Reuse an already cached suitable model when possible.
6. Never download multiple candidate models just to benchmark.
```

Initial policy:

```text
if CUDA VRAM >= 8 GB:      small, compute_type=float16
elif CUDA VRAM >= 4 GB:    base, compute_type=float16
elif system RAM >= 8 GB:   base, compute_type=int8
else:                      tiny, compute_type=int8
```

Duration adjustment:

```text
if duration > 2 hours and CPU-only: prefer tiny/base int8 and warn about runtime
if duration < 10 minutes and RAM is sufficient: base is acceptable
```

Model download timing:

```text
plan_asr(): never downloads
run_asr(): downloads selected model on first use through faster-whisper/HuggingFace cache into vctx cache
```

### How Level 4 should work end-to-end

```text
vctx prepare URL --out out
  -> source.extract_metadata(URL)
  -> source.extract_transcript(URL)
  -> NoTranscript
  -> source.extract_media(URL, cache, purpose=asr)
  -> plan_asr(policy, environment, source_state)
  -> run_asr(plan, media_asset, cache)
  -> TranscriptPayload(method=asr, provider=...)
  -> same transcript/chunk/render pipeline as Level 0/2
  -> manifest records ASR route/evidence/cost/upload policy
```

For local media:

```text
vctx prepare lecture.mp4 --out out
  -> local media source adapter extracts synthetic metadata
  -> no subtitles
  -> local media asset path is already available
  -> same ASR route planning/execution
```

### Level 4 implementation order

1. Add `MediaAsset` model and `SourceAdapter.extract_media()` contract.
2. Implement local media file detection for `.mp4/.m4a/.mp3/.wav/.webm`.
3. Implement `yt-dlp` media acquisition for ASR purpose without downloading media unless ASR is selected.
4. Add pure `plan_asr()` with environment detection and no side effects.
5. Add `FasterWhisperAsrAdapter` behind optional `asr` dependency.
6. Wire `prepare` no-subtitle path from partial output to ASR when route is available.
7. Add manifest evidence for route, provider, model, upload/network/cost flags, and generated transcript provenance.
8. Keep current partial metadata output when ASR is unavailable.

## Level 5 — optional visual/context enrichment

Purpose:

```text
video
  -> use transcript/evidence signals to decide whether visual context may reduce uncertainty
  -> evidence-guided frame acquisition plan
  -> OCR / visual description / source image capture intents
  -> timestamp-associated visual artifacts
```

This level is optional. It should not block transcript-centric workflows, and it should not spend OCR/VLM budget on podcast-like videos whose useful information is already in the audio/transcript.

### Target command examples

```bash
uv run vctx prepare "https://..." --out ./out/video --workflow visual
uv run vctx prepare "https://..." --out ./out/video --workflow transcript
```

### Required behavior

- Visual acquisition planning is pure and side-effect free: derive a sampling/evidence recipe before downloading/extracting frames.
- The sampling objective is maximal information extraction with minimal relative entropy against the transcript-grounded state, not uniform video coverage and not direct visual informativeness detection.
- Directly deciding whether a video frame is informative from the visual stream alone is treated as a recursive circuit; when timestamps/transcript exist, prefer transcript-anchored hypotheses and use frame extraction as evidence generation across different aspects.
- Frame extraction and OCR/VLM execution are side-effecting adapter steps.
- Visual artifacts must be timestamped.
- Sampling should combine transcript anchors, aspect-specific probes, minimum intervals, and near-duplicate removal; scene/keyframe signals may be weak evidence, not ground truth.
- Podcast/audio-first sources should default to no visual enrichment beyond an optional sparse cover frame.
- Slide/screen lectures should favor OCR plus source-frame capture.
- Diagrams/formulas should keep source images and use both OCR and visual description because layout/structure matters.
- Scenery/low-text visual sources should favor sparse visual descriptions plus source-frame capture.
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

Based on the remaining graph gaps, implement in this order:

1. **Visual records and rendering**
   - Add frame extraction, `VisualRecord`, and renderer support.
   - Use `VisualAssessment.recipe` before side-effecting frame extraction.
   - Keep visual workflows optional and timestamped.

2. **Cleanup and chapters**
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
