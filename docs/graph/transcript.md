# Transcript Module Graph

## Purpose
Normalize transcript records deterministically.

## Dependencies
```text
transcript -> models -> util
```

## API graph
```text
normalize_transcript(raw)
  -> sort segments
  -> clean text deterministically
  -> drop/flag empty segments
  -> assign stable ids
  -> Transcript
```

Deterministic cleanup:
```text
strip subtitle markup
normalize whitespace
merge obvious duplicate fragments
preserve timestamps
```

Model-mediated cleanup belongs to `transforms`, not this module.

## Atomic isolation
Transcript module is pure. It accepts models and returns models.

## Tree dependency rule
```text
app -> transcript -> models/util
```
Never:
```text
transcript -> sources/transforms/render/io
```

## Verification
- normalization is deterministic
- segment ids are stable
- timestamps/provenance survive
- semantic rewriting does not happen here
