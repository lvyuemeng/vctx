# Models Module Graph

## Purpose
Define stable internal data shapes and artifact schemas.

## Dependencies
```text
models -> pydantic -> stdlib types
```
Models are leaves.

## API graph
```text
VideoMetadata
SourceRef
Transcript
TranscriptSegment
TranscriptProvenance
Chunk
VisualRecord
ChapterCandidate
ArtifactRef
Manifest
ManifestStep
TransformEvidence
```

## Atomic isolation
Models validate and serialize data only. They contain no side effects and no provider calls.

## Tree dependency rule
Any module may import models. Models import no project module except primitive shared type aliases if needed.

## Verification
- JSON serialization is stable enough for artifacts
- provider-specific raw payloads are not normal fields
- timestamps and provenance survive transformations
