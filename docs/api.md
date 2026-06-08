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
| `--overwrite / --no-overwrite` | `--no-overwrite` | Whether an existing output directory can be reused. |
| `--chunk-max-chars INT` | `6000` | Maximum approximate characters per chunk before flushing. |
| `--chunk-max-seconds INT` | unset | Optional maximum chunk duration. |
| `--cache-dir DIR` | platform cache dir | Override cache location. |
| `--keep-temp / --no-keep-temp` | `--no-keep-temp` | Preserve temporary downloads/intermediate files. |
| `--format NAME` | all default formats | Repeatable output selector. Initial values: `json`, `context`, `readable`, `transcript`. |

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
error: no transcript found for input; rerun with an ASR-enabled build or provide a transcript file
```

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
    }
  ],
  "warnings": []
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
| `steps` | Ordered pipeline steps. |
| `warnings` | Recoverable issues. |

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
