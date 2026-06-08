# Chunking Module Graph

## Purpose
Prepare normalized records for context injection while preserving source traceability.

## Dependencies
```text
chunking -> models -> util
```

## API graph
```text
chunk_transcript(transcript, options)
  -> accumulate segments by approximate budget
  -> preserve segment ids/timestamps
  -> Chunk[]
```
Future:
```text
chunk_mixed_records(transcript_segments, visual_records, options)
  -> ContextChunk[]
```

## Atomic isolation
Chunking is pure. It does not fetch, transform with models, render Markdown, or write files.

## Tree dependency rule
```text
app -> chunking -> models/util
```
Never:
```text
chunking -> sources/transforms/render/io
```

## Verification
- chunk budgets are respected approximately
- timestamps and segment ids are preserved
- empty transcript behavior is explicit
- chunking works without provider/model dependencies
