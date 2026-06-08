# Application Module Graph

## Purpose
Orchestrate workflows. Application code coordinates modules but does not implement provider-specific behavior or pure transformations inline.

## Dependencies
```text
app
  -> models
  -> sources
  -> transforms
  -> subtitles
  -> transcript
  -> chunking
  -> render
  -> io
  -> manifest
  -> errors
```

## API graph
```text
PrepareRequest
  -> prepare_context_pack(request)
      -> validate output policy
      -> create cache/session context
      -> detect source
      -> acquire metadata
      -> acquire transcript or media
      -> auto-route missing capabilities
      -> parse transcript payload
      -> normalize transcript
      -> run auto/requested transformations
      -> chunk records
      -> render bundle
      -> write artifacts
      -> write manifest
      -> PrepareResult
```

## Auto-adaptation
```text
if transcript exists:
  use transcript
elif ASR policy allows auto:
  choose curated ASR route
else:
  fail clearly or write partial manifest
```
The caller should not need provider details.

## Atomic isolation
Application owns order and policy only. It must not parse VTT/SRT, call provider SDKs, or write Markdown by hand.

## Tree dependency rule
Application is a root orchestrator. Lower modules must not import `app`.

## Verification
- tests cover happy, partial, and failure paths
- manifest records every routed stage
- existing output directory policy is enforced
- provider payloads never leak beyond adapters
