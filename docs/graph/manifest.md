# Manifest Module Graph

## Purpose
Build the audit trail of a run.

## Dependencies
```text
manifest -> models -> util.time
```

## API graph
```text
ManifestBuilder.start(input)
  -> add_step(name, status, detail, evidence?)
  -> add_warning(message)
  -> add_artifact(ref)
  -> finish(status)
  -> Manifest
```

Transform evidence:
```text
provider: local | free-online | configured-online | external-command
provider_name
model
mode
uploaded
cost_may_apply
requires_user_config
source_artifacts
output_artifacts
warnings
```

## Atomic isolation
Manifest module records facts. It does not execute stages or decide routes.

## Tree dependency rule
```text
app -> manifest -> models/util
```
Never:
```text
manifest -> sources/transforms/io.writer
```

## Verification
- every major stage has a step
- skipped stages can be recorded
- partial/error statuses are representable
- model-mediated output is auditable
