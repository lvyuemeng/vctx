# vctx API

This document defines the initial public API for `vctx`: the CLI commands, artifact files, JSON shapes, and user/agent interaction contract.

`vctx` is a CLI-first tool. Python internals may change, but the CLI behavior and artifact shapes should be treated as the stable integration surface.

## CLI principles

- Non-interactive by default.
- No embedded chat or Q&A.
- No AI model configuration required for the default path.
- All durable output goes to the explicit `--out` directory.
- stdout is for final machine/human-consumable result lines.
- stderr is for progress, warnings, and errors.
- `manifest.json` is the first artifact a downstream agent should inspect.

## Commands

### `vctx prepare`

Prepare a complete context pack from a URL or local transcript/media input.

```bash
vctx prepare INPUT --out DIR [OPTIONS]
```

Examples:

```bash
vctx prepare "https://www.youtube.com/watch?v=abc123" --out ./out/abc123
vctx prepare ./lecture.vtt --out ./out/lecture
vctx prepare ./captions.srt --out ./out/captions --overwrite
```

Inputs:

| Argument | Description |
| --- | --- |
| `INPUT` | URL or local path. Initially URL via `yt-dlp`, `.vtt`, `.srt`, or supported transcript JSON. |

Options:

| Option | Default | Description |
| --- | --- | --- |
| `--out DIR` | required | Output directory for durable artifacts. |
| `--language LANG` | auto | Preferred subtitle language, for example `en`, `zh`, `zh-Hans`. |
| `--overwrite` | unset | Allow reusing an existing output directory. |
| `--chunk-max-chars INT` | `6000` | Maximum approximate characters per chunk before flushing. |
| `--chunk-max-seconds INT` | unset | Optional maximum chunk duration. |
| `--cache-dir DIR` | platform cache dir | Override cache location. |
| `--keep-temp` | unset | Preserve temporary downloads/intermediate files. |
| `--format NAME` | all default formats | Repeatable output selector. Initial values: `json`, `context`, `readable`, `transcript`. |
| `--workflow NAME` | `default` | Select a meaningful preparation workflow instance: `default`, `transcript`, `visual`, `full`, or `metadata`. |
| `--offline` | unset | Use the offline workflow policy; network/model-service routes are unavailable. |
| `--config PATH` | unset | Optional TOML config file. Missing fields keep built-in defaults; CLI/request values override config fields. |

Default output files:

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

Successful stdout:

```text
Wrote context pack: DIR
Manifest: DIR/manifest.json
Context: DIR/context.md
Readable: DIR/readable.md
```

Warnings stderr example:

```text
warning: official subtitles not found; used automatic subtitles for language en
```

Failure stderr example:

```text
error: no transcript found for input; no default transcript fallback route is available. Provide a transcript file, install the default ASR extra, configure an online route, or use --workflow metadata for metadata-only output.
```

### Config file contract

Config is optional and exists to provide defaults and advanced provider credentials without turning the CLI into a provider menu.

Layering:

```text
built-in defaults
  -> config file passed by --config
  -> CLI/request overrides
  -> ResolvedConfig
```

Missing fields are not errors. They resolve to built-in instances/defaults. Secrets are never stored directly; instance config references environment variable names. `.env` files are optional convenience inputs for those environment variables.

Preferred example:

```toml
[runtime]
workflow = "transcript"          # default | transcript | visual | full | metadata
cache_dir = ".cache/vctx"        # optional; relative paths resolve from this config file
env_files = [".env"]             # optional; loaded only for provider credentials
keep_temp = false

[source]
preferred_language = "en"
subtitle_fallback_order = ["manual", "automatic", "fallback"]
media_download_policy = "auto"   # auto | never

[output]
formats = ["json", "context", "readable", "transcript"]
chunk_max_chars = 6000
chunk_max_seconds = 900

[transforms.asr]
instance = "local-default"       # names a composable ASR instance

[instances.asr.local-default]
type = "local-faster-whisper"
model_policy = "auto"            # auto | tiny | base | small | medium | large
# managed model weights live under runtime.cache_dir/models/

[instances.asr.local-model]
type = "local-faster-whisper"
model = "D:/models/faster-whisper-tiny"  # explicit path => no managed cache/download

[instances.asr.openai-whisper]
type = "openai-compatible-audio"
base_url = "https://api.openai.com/v1/audio/transcriptions"
api_key_env = "OPENAI_API_KEY"   # value can come from shell env or runtime.env_files
model = "whisper-1"
cost = "paid"                    # free | paid | local | unknown
upload = "required"              # online ASR uploads media/audio
```

Legacy policy fields such as `route`, `allow_upload`, and `allow_paid` may exist internally while the planner is being refactored, but the public config should prefer named instances. Local vs online is separated by instance type, not by fuzzy booleans:

```text
local-default.type = local-faster-whisper
openai-whisper.type = openai-compatible-audio
```

Field semantics:

| Field | Semantics |
| --- | --- |
| `runtime.workflow` | Default workflow profile when CLI `--workflow` is not supplied. |
| `runtime.cache_dir` | Persistent tool cache. Defaults to the platform user cache directory, e.g. Windows `C:\\Users\\<user>\\AppData\\Local\\vctx\\Cache`. Relative config values resolve from the config file directory; CLI `--cache-dir` values stay relative to the caller CWD. |
| `runtime.env_files` | Optional dotenv files to consult during credential resolution. Relative config values resolve from the config file directory. Secrets are not copied into manifests/config dumps. |
| `source.preferred_language` | Default subtitle/ASR language hint; CLI `--language` overrides. |
| `source.subtitle_fallback_order` | Source adapter policy for official/manual subtitles, automatic captions, and fallback language. |
| `source.media_download_policy` | `auto` allows media acquisition only when a selected workflow needs it; `never` blocks media downloads. |
| `output.formats` | Default render/artifact formats when CLI `--format` is not supplied. |
| `transforms.asr.instance` | Name of a composable ASR instance from `[instances.asr.<name>]`. Omit for built-in default selection. |
| `instances.asr.<name>.type` | Capability implementation type. Current planned values: `local-faster-whisper`, `openai-compatible-audio`. |
| `instances.asr.<name>.model_policy` | Local model-size policy for managed-cache instances. `auto` inspects hardware/duration/cache and downloads at most one chosen model. |
| `instances.asr.<name>.model` | Either a model id such as `tiny`/`base` for managed persistent cache, or an explicit local model path. A local path automatically disables managed cache/download. |
| `instances.asr.<name>.cache` | Legacy/internal override. Public config should usually omit it; managed cache is the default for model ids, and local paths are local-only automatically. |
| `instances.asr.<name>.api_key_env` | Environment variable containing a credential. The config stores only the variable name. |
| `instances.asr.<name>.cost` / `upload` | Positive evidence fields used for manifest/planning. Explicitly choosing a paid/uploading instance means the user selected that instance. |

Configured online ASR is selected only when an online instance is explicitly selected or project defaults choose it, required credentials are present, and the manifest can record upload/cost evidence.

### Auto-adaptive transformations

Model transformations are capability-level defaults, not provider menus. The normal API should avoid asking users to choose `local` vs `online` vs provider names.

Default routing semantics:

| Route | Meaning |
| --- | --- |
| deterministic | Use source data such as official subtitles, automatic subtitles, or user-provided transcripts. |
| zero-config | Use the best curated no-config route for the capability: local if good enough, otherwise free zero-config online if safe/stable enough and not offline. |
| configured-online | Use the configured project/user provider when quality requires it and configuration exists. |
| unavailable | Fail clearly or write a partial manifest, depending on request policy. |

API graph for model transformations:

```text
prepare INPUT
  -> deterministic acquisition
       -> platform metadata
       -> official/manual subtitles
       -> automatic subtitles
  -> if transcript unavailable and workflow allows transcript fallback:
       -> route default transcript fallback
       -> local/free-online/configured-online ASR
       -> timestamped transcript
  -> deterministic transcript normalization
  -> if cleanup policy enables cleanup:
       -> route default cleanup
       -> cleaned transcript + transform evidence
  -> if visual-context policy enables visual context:
       -> infer whether visuals are useful for this source
       -> choose adaptive acquisition strategy: sparse cover, transcript-aligned, scene-change, fixed interval, or hybrid
       -> choose extraction intent per selected frame: OCR, visual description, and/or source image capture
       -> route default OCR/frame-description
       -> timestamped visual records + transform evidence
  -> if chapter policy enables chapters:
       -> route default chapter candidates
       -> chapter candidates + transform evidence
  -> chunk/render/write artifacts
  -> manifest records every route and provider actually used
```

The CLI should not expose raw provider choices such as `provider-x:model-y` for normal usage. If two implementations can serve the same capability, `vctx` should choose the best project default and record the actual choice in `manifest.json`.

### `vctx metadata`

Print normalized metadata for an input without preparing a full context pack.

```bash
vctx metadata INPUT [--json]
```

Purpose:

- cheap source inspection
- agent preflight
- debugging extractor behavior

Output:

- human-readable text by default
- `VideoMetadata` JSON with `--json`

### `vctx chunk`

Chunk an existing transcript artifact.

```bash
vctx chunk transcript.clean.json --out chunks.json [--chunk-max-chars 6000]
```

Purpose:

- re-chunk without re-downloading source
- test chunking strategies
- support agent workflows with custom transcript acquisition

Input:

- `transcript.clean.json` or compatible `Transcript` JSON

Output:

- `chunks.json`

### `vctx render`

Render Markdown from existing artifacts.

```bash
vctx render --metadata metadata.json --chunks chunks.json --out context.md --format context
vctx render --metadata metadata.json --transcript transcript.clean.json --out readable.md --format readable
```

Purpose:

- regenerate Markdown after renderer changes
- support external pipelines that already have JSON artifacts

Formats:

```text
context
readable
transcript
```

### `vctx doctor`

Inspect local environment.

```bash
vctx doctor
```

Checks:

- Python version
- package versions
- `yt-dlp` import
- cache directory writability
- optional `ffmpeg` availability
- optional ASR dependencies when installed

No network calls by default.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | Generic runtime failure. |
| `2` | Invalid command usage or options. |
| `3` | Unsupported input/source. |
| `4` | Transcript unavailable. |
| `5` | Output directory or filesystem error. |

## Artifact contract

### `manifest.json`

The run ledger and discovery document.

Downstream agents should read this first.

Shape:

```json
{
  "schema_version": "0.1",
  "tool": "vctx",
  "tool_version": "0.1.0",
  "status": "ok",
  "input": "https://www.youtube.com/watch?v=abc123",
  "created_at": "2026-06-07T12:00:00Z",
  "artifacts": [
    {
      "kind": "metadata",
      "path": "metadata.json",
      "media_type": "application/json"
    },
    {
      "kind": "context",
      "path": "context.md",
      "media_type": "text/markdown"
    }
  ],
  "steps": [
    {
      "name": "source.detect",
      "status": "ok",
      "detail": "yt-dlp"
    },
    {
      "name": "transcript.extract",
      "status": "ok",
      "detail": "official_subtitles:en:vtt"
    },
    {
      "name": "transform.asr",
      "status": "skipped",
      "detail": "transcript already available"
    }
  ],
  "warnings": [],
  "transform_evidence": [
    {
      "capability": "asr",
      "selected_route": "skipped",
      "deterministic": true,
      "reason": "transcript already available"
    }
  ]
}
```

Fields:

| Field | Description |
| --- | --- |
| `schema_version` | Artifact schema version. |
| `tool_version` | Installed `vctx` version. |
| `status` | `ok`, `partial`, or `error`. |
| `input` | Original user input string. |
| `artifacts` | Files written relative to output directory. |
| `steps` | Ordered pipeline steps with compact status/details. |
| `warnings` | Recoverable issues. |
| `transform_evidence` | Structured route evidence for model-mediated capabilities, including selected route, provider/model id, upload/cost flags, deterministic flag, and reason. Secrets are never recorded. |

### `metadata.json`

Normalized source metadata.

Shape:

```json
{
  "id": "youtube__abc123",
  "source_type": "youtube",
  "source": {
    "kind": "url",
    "value": "https://www.youtube.com/watch?v=abc123"
  },
  "title": "Example Video",
  "uploader": "Example Channel",
  "duration_seconds": 1234.5,
  "webpage_url": "https://www.youtube.com/watch?v=abc123",
  "language": "en",
  "extractor": "youtube",
  "raw_provider": "yt-dlp"
}
```

### `transcript.raw.json`

Transcript as parsed from source with minimal cleanup.

Shape:

```json
{
  "video_id": "youtube__abc123",
  "provenance": {
    "method": "official_subtitles",
    "language": "en",
    "format": "vtt",
    "provider": "yt-dlp"
  },
  "segments": [
    {
      "id": "seg_000001",
      "start": 0.0,
      "end": 4.2,
      "text": "Welcome to this video.",
      "source_id": "caption-1"
    }
  ]
}
```

### `transcript.clean.json`

Same shape as `transcript.raw.json`, but after deterministic normalization:

- empty segments removed
- whitespace normalized
- simple subtitle markup removed
- segment IDs reassigned if necessary
- chronological order enforced

No summarization or semantic rewriting.

### `chunks.json`

Chunked transcript for agent processing.

Shape:

```json
{
  "video_id": "youtube__abc123",
  "strategy": "chars-v1",
  "chunks": [
    {
      "id": "chunk_0001",
      "start": 0.0,
      "end": 305.2,
      "text": "Welcome to this video...",
      "segment_ids": ["seg_000001", "seg_000002"],
      "char_count": 5840,
      "approx_token_count": 1460
    }
  ]
}
```

### `context.md`

Agent-optimized Markdown.

Characteristics:

- compact metadata
- clear usage note
- chunk tags with IDs and timestamps
- source text preserved

Shape:

```markdown
# Agent Context Pack

## Metadata

- Title: Example Video
- URL: https://www.youtube.com/watch?v=abc123
- Duration: 00:20:34
- Transcript source: official_subtitles / en / vtt

## Usage

The chunks below are timestamped source text extracted from the video.
Preserve timestamps when citing claims.

## Chunks

<chunk id="chunk_0001" start="00:00:00" end="00:05:05">
Welcome to this video...
</chunk>
```

### `readable.md`

Human-readable transcript pack.

Characteristics:

- pleasant Markdown
- time-range headings
- no XML-like chunk tags
- no generated summary by default

Shape:

```markdown
# Example Video

Source: https://www.youtube.com/watch?v=abc123  
Duration: 00:20:34  
Transcript source: official_subtitles / en

## 00:00:00–00:05:05

Welcome to this video...
```

### `transcript.md`

Timestamped cleaned transcript.

Shape:

```markdown
# Transcript — Example Video

[00:00:00–00:00:04] Welcome to this video.
[00:00:04–00:00:09] Today we will discuss...
```

## Interaction with downstream AI agents

Recommended agent flow:

1. Run `vctx prepare INPUT --out DIR`.
2. Read `DIR/manifest.json`.
3. If `status` is `ok` or `partial`, select artifact:
   - use `context.md` for context injection
   - use `chunks.json` for programmatic chunk-by-chunk processing
   - use `readable.md` for human-facing source review
4. The agent performs summarization, knowledge-flow extraction, Q&A, or memory updates outside `vctx`.

Example agent prompt wrapper:

```text
The following is a context pack generated by vctx from a video source.
Use it as source material. Preserve timestamps when citing claims.
Do not assume content not present in the context.

<video_context>
... context.md ...
</video_context>
```

## Stability policy

For early versions, treat these as semi-stable:

- CLI command names
- output file names
- `manifest.json` discovery fields
- `metadata.json`, `transcript.clean.json`, and `chunks.json` top-level fields

Internal Python module paths are not stable until implementation matures.
