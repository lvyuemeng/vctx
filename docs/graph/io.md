# IO Module Graph

## Purpose
Own filesystem/cache boundaries and artifact writing.

## Dependencies
```text
io
  -> models
  -> errors
  -> platformdirs
  -> pathlib/json/stdlib
```

## API graph
```text
build_cache(config)
  -> CacheContext

validate_output_policy(out_dir, overwrite)
  -> OutputPolicyResult

write_artifact_bundle(out_dir, bundle)
  -> ArtifactRef[]

write_manifest(out_dir, manifest)
  -> ArtifactRef
```

## Atomic isolation
IO writes bytes and paths only. It does not understand provider semantics, parse transcripts, route models, or render content from raw records.

## Tree dependency rule
```text
app -> io -> filesystem/platformdirs
```
Never:
```text
io -> sources/transforms/render/app
```

## Verification
- output overwrite policy is tested
- writes are predictable and relative paths are manifest-safe
- partial outputs are inspectable
- cache paths are platform-safe
