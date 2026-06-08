# vctx Module API Graph

This directory contains separated implementation graphs. Each module file defines:

```text
purpose
dependencies
API graph
atomic isolation rule
tree dependency rule
verification checklist
```

Abstract architecture remains in `../architecture.md`. Public CLI/artifact contracts remain in `../api.md`.

## Dependency tree

Dependencies must point downward. No module may depend on a parent/sibling through implementation details.

```text
cli
  -> app
      -> sources
          -> provider libraries / local files
      -> transforms
          -> transform providers
      -> subtitles
      -> transcript
      -> chunking
      -> render
      -> io
      -> manifest
          -> models
              -> stdlib / pydantic only
```

Shared leaves:

```text
models
errors
util
```

Forbidden directions:

```text
models -> app/cli/sources/transforms/render/io
render -> sources/transforms/io
chunking -> sources/transforms/render/io
transcript -> sources/transforms/render/io
sources -> render/chunking/transcript/transforms
transforms -> render/io/cli
io -> sources/transforms/render
cli -> provider libraries directly
```

## Module files

| Module | File |
| --- | --- |
| CLI boundary | `cli.md` |
| Application orchestration | `app.md` |
| Internal models | `models.md` |
| Source acquisition | `sources.md` |
| Model transformations and tech stack | `model-transforms.md` |
| Subtitle parsing | `subtitles.md` |
| Transcript normalization | `transcript.md` |
| Chunking | `chunking.md` |
| Rendering | `render.md` |
| IO/cache/artifact writing | `io.md` |
| Manifest evidence | `manifest.md` |

## Auto-adaptation rule

Prefer auto-adaptation/default configuration:

```text
caller intent
  -> route by available source data and capability policy
  -> choose curated default implementation
  -> record actual route in manifest
```

Do not expose raw provider choices in normal module APIs.
