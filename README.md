# vctx

`vctx` is a CLI for turning video URLs and media files into clean, readable, timestamped context packs.

It is designed for AI agents, scripts, and technical users who need source-grounded video context without a monolithic video-note application.

## What it does

Given a video URL or local media file, `vctx` prepares artifacts such as:

```text
manifest.json
metadata.json
transcript.clean.json
transcript.md
chunks.json
context.md
readable.md
```

The primary output is a directory of transparent files that can be read by humans or injected into an AI agent's context.

## What it is not

`vctx` is not:

- an AI chat app
- a video Q&A system
- a knowledge base
- a RAG framework
- an Electron desktop app
- a web service
- an Obsidian/Notion replacement
- a summarizer that silently depends on paid AI APIs

The tool prepares context. Downstream agents or users decide how to summarize, analyze, or store it.

## Intended workflow

```bash
vctx prepare "https://example.com/video" --out ./out/video-001
```

Then a human or agent can read:

```text
./out/video-001/context.md
./out/video-001/readable.md
./out/video-001/manifest.json
```

Conceptually:

```text
video / audio / URL
  -> metadata extraction
  -> subtitle or transcript acquisition
  -> transcript normalization
  -> timestamp-preserving chunking
  -> readable Markdown
  -> agent-ready context Markdown
  -> manifest
```

## Design priorities

- CLI-first
- readable output
- machine-readable artifacts
- no embedded chat layer
- no knowledge-management scope creep
- deterministic by default
- AI optional and explicit
- side effects isolated at the edges
- uniform internal data models
- external providers hidden behind adapters

## Documentation

- [`docs/context.md`](docs/context.md): project goal, stack, style, and constraints
- [`docs/architecture.md`](docs/architecture.md): concrete module layout, data flow, dependency boundaries, and pseudocode
- [`docs/api.md`](docs/api.md): CLI commands, artifact contract, JSON shapes, and agent interaction model
- [`docs/graph.md`](docs/graph.md): function-level module graph, pseudocode, and dependency direction rules

## Current status

Early design/bootstrap stage.

The repository currently defines the project direction and architectural constraints before implementation begins.
