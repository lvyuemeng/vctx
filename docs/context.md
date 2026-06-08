# vctx Project Context

## Project goal

`vctx` is a small CLI tool that converts video URLs or local media files into clean, readable, timestamped context packs for downstream AI agents and automation.

The tool prepares source material. It does not try to become an AI assistant, video-note application, knowledge base, RAG system, or chat interface.

Primary job:

```text
video / audio / supported URL
  -> metadata
  -> transcript
  -> normalized transcript
  -> chunks
  -> readable Markdown
  -> agent-ready context Markdown
  -> manifest
```

The output should be easy for a human to inspect and easy for an AI agent to inject into context.

## Non-goals

`vctx` should not grow into a monolith.

Out of scope by default:

- embedded AI chat
- Q&A over videos as a user interface
- personal knowledge management
- cross-video concept stores
- RAG indexes
- desktop UI
- web application backend
- task-history database
- provider-heavy configuration UI
- implicit or unconfigured cloud AI calls
- opinionated GitHub / Obsidian / Notion syncing

Optional features may exist only when they preserve the CLI's role as a context-preparation utility.

Internal AI use is allowed when it is a bounded transformation step, for example ASR, OCR, VLM frame description, language detection, noisy transcript cleanup, chapter-boundary suggestion, or provider routing. The boundary is not "no AI". The boundary is "no AI user-interface/assistant layer inside `vctx`." External agents should handle user conversation, final summarization, Q&A, memory, and knowledge workflows.

## Intended users

`vctx` is for:

- AI agents that need clean video context
- technical users who want transparent artifacts
- scripts and batch workflows
- developers who want a predictable media-to-context primitive

The main interface is the command line. The output format is the product.

## Design principles

### CLI first

Every core capability should be callable non-interactively:

```bash
vctx prepare URL --out DIR
```

Commands should have clear inputs, outputs, exit codes, stdout/stderr behavior, and file artifacts.

### No embedded AI communication layer

Do not build a chat layer inside the tool. External agents already provide that.

If AI is used internally, it must be for a bounded internal step such as transcription, OCR, or optional structural cleanup. It should be explicit, replaceable, and not required for default usage.

Default behavior should require no paid model configuration.

### Readable and machine-readable

Each run should produce both:

- human-readable Markdown
- machine-readable JSON

Readable output should not be an afterthought. A user should be able to open the output directory and understand what happened.

### Source-grounded

Preserve timestamps and source metadata everywhere practical.

Downstream agents should be able to cite or inspect the source ranges behind a chunk.

### Deterministic by default

Default steps should be deterministic where possible:

- metadata extraction
- subtitle extraction
- transcript normalization
- chunking
- rendering
- manifest generation

AI-mediated or heuristic behavior should be clearly identified in the manifest.

### Explicit storage

The caller chooses where artifacts are written:

```bash
vctx prepare URL --out ./out/video-001
```

The tool should not assume a knowledge-store repo, application database, or long-term memory system.

A cache may exist for temporary media files, but durable output belongs in the explicit `--out` directory.

## Expected artifacts

A typical output directory should look like:

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

Optional artifacts:

```text
assets/
  frames/
audio/
transcription.json
ocr.json
```

Heavy temporary artifacts should stay out of durable output unless explicitly requested.

## Technology stack and dependencies

### Stack choice

Use a modern Python CLI stack:

- Python 3.12 as the preferred development target
- Python 3.11+ as the compatibility floor unless a dependency forces otherwise
- `uv` for environment management, dependency locking, running tools, and publishing workflows
- `hatchling` as the build backend
- `pytest` for tests
- `ruff` for linting and formatting
- `ty` for fast static type checking while the project is young and changing

Keep dependencies modest. Do not add frameworks unless they directly support the CLI's core role.

### Runtime dependencies

Use these as the default runtime dependency set:

| Dependency | Role | Reason |
| --- | --- | --- |
| `typer` | CLI framework | Modern type-hint-based CLI with good help output. Prefer `typer` over raw `click` for this project because command signatures stay readable and typed. |
| `pydantic` | Internal models and artifact schemas | Gives one uniform internal representation and JSON serialization/validation. Use Pydantic v2 style. |
| `yt-dlp` | Media metadata, subtitle discovery, subtitle download, optional media download | Best-supported active extractor for YouTube, Bilibili, and many video sites. Treat it as an adapter at the edge. |
| `platformdirs` | Cache/config directory discovery | Avoid hard-coded OS paths for cache directories. |
| `webvtt-py` | WebVTT subtitle parsing | Useful for `.vtt` subtitles from video platforms. Keep subtitle parsing behind an adapter. |
| `srt` | SRT subtitle parsing | Small focused parser for `.srt` subtitle files. Keep subtitle parsing behind an adapter. |

Notes:

- `rich` is acceptable for readable terminal output. If using `typer[standard]`, `rich` may arrive through Typer's standard extras. Keep rich formatting at the CLI boundary; do not leak console concerns into core logic.
- Prefer Pydantic models over raw dictionaries at internal boundaries. Raw provider payloads should be converted immediately at adapter boundaries.
- Avoid `tiktoken` as a default dependency. It is useful for model-specific counting but makes the core too provider-shaped. Default chunking can use approximate token counts; model-specific tokenizers can be optional later.
- Avoid `orjson` as a default dependency until JSON performance is a proven bottleneck. Standard library JSON is good enough for initial artifacts.
- Avoid `jsonschema` as a default dependency if Pydantic validation and schema export are sufficient. Add it only if independent JSON Schema validation becomes a real CLI feature.

### Optional dependencies

Optional extras should map to isolated capabilities:

| Extra | Candidate dependency | Purpose | Rule |
| --- | --- | --- | --- |
| `asr` | `faster-whisper` | Local transcription fallback when subtitles are unavailable | Must be explicit; not required for default `prepare` when subtitles exist. |
| `online-ai` | `httpx` or provider-specific SDKs behind adapters | Optional online ASR/OCR/VLM/cleanup calls | Must never be required by default; provider calls must be explicit and manifest-recorded. |
| `ocr` | OCR tool wrapper or external command bridge | Optional OCR over extracted frames | Prefer external command adapters first to avoid bloating the runtime dependency set. |
| `dev` | `pytest`, `ruff`, `ty` | Development and CI | Not runtime dependencies. |

Internal AI dependencies should be selected per capability, not as global core dependencies. Prefer these integration shapes, in order:

1. Existing local executable via an external-command adapter.
2. Small focused Python dependency behind an optional extra.
3. Online provider through a narrow adapter and explicit configuration.
4. Provider-specific SDK only when plain HTTP is insufficient.

Do not add model/provider dependencies to the default runtime path.

External command-line tools may be required for specific features:

| Tool | Purpose | Default requirement |
| --- | --- | --- |
| `ffmpeg` | Audio extraction, subtitle conversion, frame extraction | Optional at first; required only for media download/transcription/frame features. |
| `yt-dlp` executable | Alternative to Python API usage | Prefer Python package integration first; shell out only behind the adapter if needed. |

### Dependency selection rules

Before adding a dependency, check:

1. Is it actively maintained?
2. Does it solve a real current problem?
3. Can it stay behind an adapter or boundary?
4. Does it avoid pulling the project toward an app/server/knowledge-base shape?
5. Is the standard library good enough for now?

Prefer small, focused libraries over frameworks.

Do not add dependencies for:

- chat
- RAG
- vector databases
- web servers
- desktop UI
- cloud LLM providers as required/default dependencies
- provider SDKs in core modules
- knowledge management
- provider-specific token counting by default

Internal AI dependencies are allowed only when tied to an explicit transformation capability such as ASR, OCR, frame description, transcript cleanup, chapter suggestion, language detection, or routing.

## Code style

Code should be boring, typed, and explicit.

Prefer:

- small pure functions
- typed data models
- narrow interfaces
- explicit errors
- predictable file writes
- unit tests around transformation logic
- integration tests around CLI behavior

Avoid:

- hidden global state
- long procedural scripts
- implicit network calls in pure logic
- provider-specific types leaking across the codebase
- deeply nested conditionals
- stringly typed internal data
- business logic mixed into CLI argument parsing

## Separation of side effects

Keep side effects at the edges.

Side-effecting operations include:

- network requests
- running `yt-dlp`
- reading/writing files
- invoking ffmpeg
- invoking ASR/OCR tools
- shelling out to external processes

Core transformation logic should accept data and return data:

```text
TranscriptSegment[] -> CleanTranscript
CleanTranscript -> Chunk[]
Chunks -> Markdown
Artifacts -> Manifest
```

This makes the tool easier to test and prevents spaghetti architecture.

## Uniform internal representation

External sources differ, but internal logic should use one consistent representation.

Examples:

```text
YouTube subtitle line
Bilibili subtitle line
Whisper segment
manual transcript segment
```

should normalize into the same internal transcript segment model.

Do not let external provider shape leak into chunking, rendering, or manifest generation.

## Decouple external integrations

External integrations should be adapters.

Examples:

- `yt-dlp` adapter
- subtitle adapter
- local file adapter
- ASR adapter
- OCR adapter

Adapters convert external formats into internal models. Internal code should not depend on provider-specific response shapes.

## Commit style

Use short prefix-based commit messages:

```text
[prefix]: content
```

Examples:

```text
[docs]: define project context and architecture
[feat]: add local transcript prepare pipeline
[fix]: handle empty transcript chunks
[test]: cover subtitle parsing
[chore]: update dependency lockfile
```

Prefer prefixes such as:

- `[docs]` for documentation-only changes
- `[feat]` for user-visible features
- `[fix]` for bug fixes
- `[test]` for test-only changes
- `[refactor]` for internal restructuring without behavior changes
- `[chore]` for tooling, dependencies, and maintenance

Keep the content part concise and imperative where possible.

## Quality bar

A feature is not done until:

- it is covered by tests where practical
- it writes clear artifacts
- errors are understandable
- the manifest reflects what happened
- generated Markdown is readable
- generated JSON is stable enough for agent use
