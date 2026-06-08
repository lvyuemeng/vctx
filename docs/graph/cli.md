# CLI Module Graph

## Purpose
Parse command-line intent, call application services, and print concise results.

## Dependencies
```text
cli -> app -> errors
```
No dependency on provider libraries, file-writing internals, subtitle parsers, renderers, or model providers.

## API graph
```text
prepare_command(INPUT, --out DIR, options)
  -> build_prepare_request(args)
  -> app.prepare_context_pack(request)
  -> print result paths
```

Other commands:
```text
metadata_command -> app.inspect_metadata
chunk_command    -> app.chunk_existing_transcript
render_command   -> app.render_existing_artifacts
doctor_command   -> app.inspect_environment
```

## Atomic isolation
CLI is an adapter from terminal syntax to request models. It must not perform business logic.

## Tree dependency rule
```text
cli -> app -> lower modules
```
Never:
```text
cli -> yt_dlp
cli -> faster_whisper
cli -> render internals
cli -> direct artifact writing
```

## Verification
- help output is readable
- invalid args map to documented exit codes
- stdout reports final result paths
- stderr contains warnings/errors/progress
