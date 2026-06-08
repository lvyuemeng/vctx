# Rendering Module Graph

## Purpose
Turn prepared records into readable and agent-ready artifact content.

## Dependencies
```text
render -> models -> util
```

## API graph
```text
render_context(metadata, chunks, optional_records)
  -> context.md text

render_readable(metadata, transcript, chunks, optional_records)
  -> readable.md text

render_transcript(transcript)
  -> transcript.md text

render_json_artifacts(models)
  -> serializable artifact content
```

## Atomic isolation
Renderers format only. They do not fetch, parse, run AI, choose routes, or write files.

## Tree dependency rule
```text
app -> render -> models/util
```
Never:
```text
render -> sources/transforms/io.writer/app
```

## Verification
- Markdown is readable
- generated/model-mediated records are labeled
- context output includes enough provenance for agents
- renderer output is deterministic for same inputs
