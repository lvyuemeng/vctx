# vctx Verifiable Workflow Checklist

This document defines how to verify `vctx` when the implemented code only covers part of the public API.

The project should be developed as small, independently verifiable workflow slices. Each slice must say:

- what inputs it accepts
- what artifacts it must write
- what it must not do
- what command verifies it
- what failure mode is acceptable

This prevents the docs from promising an invisible monolith and lets users inspect exactly which part of the pipeline works today.

## Capability levels

`vctx prepare` should be understood as a capability ladder, not a single all-or-nothing feature.

```text
Level 0: local transcript pack
Level 1: URL metadata pack
Level 2: URL subtitle pack
Level 3: explicit ASR fallback
Level 4: optional visual/context enrichment
Level 5: optional internal AI cleanup/routing
```

The current implementation is expected to pass Level 0.

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
tmp=$(mktemp -d)
printf '1\n00:00:00,000 --> 00:00:01,000\nhello vctx\n' > "$tmp/demo.srt"
uv run vctx prepare "$tmp/demo.srt" --out "$tmp/out"
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

## Level 1 — URL metadata pack

Purpose:

```text
video URL
  -> normalized metadata
  -> metadata.json
  -> manifest.json
```

This verifies URL handling through `yt-dlp` without requiring subtitles to exist.

### Command

```bash
uv run vctx metadata "https://www.youtube.com/watch?v=..." --json
```

or, once partial prepare is implemented:

```bash
uv run vctx prepare "https://..." --out ./out/url-demo --metadata-only
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
1. user-provided transcript file, if supplied
2. official subtitles matching --language
3. official subtitles in any acceptable fallback language
4. automatic subtitles matching --language
5. automatic subtitles in fallback language
6. no transcript found
```

### Required behavior when subtitles exist

- Record whether subtitles were official or automatic.
- Record language and format.
- Preserve timestamps.
- Continue through the same internal transcript/chunk/render pipeline as Level 0.

### Required behavior when subtitles do not exist

Default behavior must not silently switch to expensive AI.

It should either:

```text
A. write metadata.json + manifest.json with status = partial
```

or:

```text
B. fail clearly with an actionable message
```

Preferred future behavior is partial output:

```json
{
  "status": "partial",
  "warnings": [
    "No subtitles found for selected language",
    "ASR was not enabled"
  ]
}
```

The error/warning should tell the caller what to do next:

```text
Provide a transcript file, install the default ASR extra, configure an online fallback, or accept a metadata-only partial output.
```

## Level 3 — auto-adapted ASR fallback

Purpose:

```text
video URL or media file without subtitles
  -> audio extraction/download
  -> transcription
  -> normalized transcript
  -> context pack
```

### Command

```bash
uv run vctx prepare "https://..." --out ./out/video
```

or:

```bash
uv run vctx prepare ./lecture.mp4 --out ./out/lecture
```

The command stays simple. `vctx` routes to the curated default fallback when subtitles are missing.

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

## Level 4 — optional visual/context enrichment

Purpose:

```text
video
  -> representative frames or OCR
  -> timestamp-associated visual artifacts
```

This level is optional. It should not block transcript-centric workflows.

### Command examples

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

## Level 5 — optional internal AI cleanup/routing

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

## Standard verification command

Every implemented level must pass:

```bash
uv run ruff check .
uv run ty check .
uv run pytest -q
```

For Level 0, the project currently has an automated integration test:

```bash
uv run pytest tests/test_local_prepare.py -q
```

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
