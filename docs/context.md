# vctx Project Context

## Goal

`vctx` is a small CLI utility that converts video URLs, local media, or transcript files into clean, timestamped context packs for downstream AI agents and automation.

Primary flow:

```text
source input
  -> metadata
  -> transcript / visual context when available
  -> normalized source records
  -> chunks
  -> readable Markdown
  -> agent-ready context Markdown
  -> manifest
```

The product is the artifact directory, not an embedded assistant.

## Non-goals

Do not build these into `vctx`:

- chat UI or Q&A interface
- final summarization as the default product behavior
- personal knowledge management
- RAG/vector database
- cross-video memory or concept store
- desktop/web app backend
- provider-heavy configuration UI
- hidden paid/cloud model calls

External AI agents should read `context.md`, `chunks.json`, `manifest.json`, and other artifacts to summarize, explain, compare, or build knowledge flow.

## Core principles

### CLI first

Every capability must be callable non-interactively:

```bash
vctx prepare INPUT --out DIR
```

The CLI should be clean enough for an AI agent to call through context injection.

### Auto-adaptive by default

Prefer automatic routing and sensible defaults over provider/mode menus.

Default policy:

```text
deterministic source data first
  -> curated zero-config route if needed
  -> free zero-config online route if it is better and allowed
  -> configured online route only when explicitly configured/enabled
```

Users should normally choose capability intent, not provider details.

### Internal AI is allowed as transformation

Model-mediated behavior is acceptable when it transforms source material into source-grounded records:

```text
audio -> timestamped transcript
frame -> OCR text
frame -> visual description
noisy transcript -> cleaned transcript
transcript/chunks -> chapter candidates
```

It must not become a user-facing assistant layer. Every model-mediated step must be recorded in `manifest.json`.

### Source-grounded artifacts

Preserve timestamps, source ids, provenance, and warnings wherever practical. Generated model output must be labeled as generated, not source text.

### Atomic modules and tree dependencies

Implementation modules should be isolated and atomic. Dependencies should form a tree/DAG from outer orchestration toward inner data models. Avoid cycles and provider-specific leakage.

See [`docs/graph/`](graph/) for per-module dependency/API graphs.

## Expected artifacts

Typical output directory:

```text
out/video-001/
  manifest.json
  metadata.json
  transcript.raw.json
  transcript.clean.json
  transcript.md
  chunks.json
  context.md
  readable.md
```

Optional capability artifacts:

```text
visual_records.json
chapter_candidates.json
assets/frames/
audio/
```

Heavy temporary artifacts should stay in cache/temp unless explicitly requested.

## Technology stack

Default runtime dependencies:

| Dependency | Role |
| --- | --- |
| `typer` | CLI framework |
| `pydantic` | internal models and JSON artifacts |
| `yt-dlp` | metadata/subtitle/media extraction adapter |
| `platformdirs` | cache/config directories |
| `webvtt-py` | WebVTT parsing |
| `srt` | SRT parsing |

Development/build:

| Dependency | Role |
| --- | --- |
| `uv` | environment, lock, run, publish workflow |
| `hatchling` | build backend |
| `pytest` | tests |
| `ruff` | lint/format |
| `ty` | type checking |

Detailed model-transformation stack lives in [`docs/graph/model-transforms.md`](graph/model-transforms.md).

## Dependency policy

- Keep default install small.
- Add optional extras per capability, not as global provider dependencies.
- Prefer Pydantic models over raw dictionaries at internal boundaries.
- Do not leak provider response shapes beyond adapters.
- Avoid `tiktoken`, `orjson`, `jsonschema`, provider SDKs, web servers, vector DBs, and RAG dependencies by default.
- External command adapters may exist as escape hatches, but they are not the primary UX.

## Commit style

Use prefix-based commit messages:

```text
[prefix]: content
```

Examples:

```text
[docs]: define module graph
[feat]: add url subtitle acquisition
[fix]: handle empty transcript chunks
[test]: cover subtitle parsing
[chore]: update lockfile
```

## Quality bar

A feature is not done until:

- it is covered by tests where practical
- artifacts are readable and machine-readable
- errors are understandable
- `manifest.json` reflects what happened
- generated JSON is stable enough for agent use
- `ruff`, `ty`, and `pytest` pass
