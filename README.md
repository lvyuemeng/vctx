# vctx

`vctx` turns video URLs, local media, and transcript files into clean, timestamped context packs.

It is built for AI agents, scripts, and technical users who want inspectable source context without a monolithic video-note app.

## What it produces

A `vctx prepare` run writes a directory of transparent artifacts such as:

```text
manifest.json
metadata.json
transcript.clean.json
transcript.md
chunks.json
context.md
readable.md
```

Humans can open the Markdown files. AI agents can inject `context.md` or `chunks.json` into their working context.

## Basic workflow

```bash
vctx prepare ./captions.srt --out ./out/video-001
```

Then inspect:

```text
./out/video-001/readable.md
./out/video-001/context.md
./out/video-001/manifest.json
```

## What it is not

`vctx` is not:

- an AI chat app
- a video Q&A system
- a personal knowledge base
- a RAG framework
- a desktop/web application
- a summarizer that silently depends on paid AI APIs

The tool prepares context. Users or downstream AI agents decide how to summarize, analyze, compare, or store it.

## Design priorities

- clean CLI interface
- useful defaults and auto-adaptation
- readable output files
- machine-readable JSON artifacts
- source-grounded timestamps and provenance
- no embedded chat layer
- no knowledge-management scope creep
- no hidden paid/cloud model calls

## Current status

Current working workflow:

```text
local .srt / .vtt transcript
  -> parsed transcript
  -> normalized transcript
  -> chunks
  -> context/readable Markdown
  -> manifest
```

Planned workflow:

```text
video URL / media file
  -> metadata and subtitles when available
  -> auto-adapted transcript fallback when needed
  -> optional visual context when useful
  -> context pack artifacts
```
