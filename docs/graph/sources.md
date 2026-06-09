# Sources Module Graph

## Purpose
Acquire source-grounded raw material from URLs and local files.

## Dependencies
```text
sources
  -> models
  -> io.cache
  -> errors
  -> provider libraries at adapter leaves
```
Adapters:
```text
ytdlp_source -> yt-dlp
local_file_source -> pathlib
```

## API graph
```text
detect_source_adapter(input)
  -> SourceAdapter

SourceAdapter.extract_metadata(input)
  -> VideoMetadata

SourceAdapter.extract_transcript(input, language, cache)
  -> TranscriptPayload | NoTranscript

SourceAdapter.extract_media(input, cache, purpose)
  -> MediaAsset | NoMedia
```

## Auto-adaptation
Deterministic data before model fallback:
```text
metadata
  -> official subtitles
  -> automatic subtitles
  -> downloadable media only when needed by ASR/visual context
```

## Atomic isolation
Sources return normalized payloads/assets. They do not parse transcript text into segments, chunk text, render Markdown, or call model transforms.

## Tree dependency rule
```text
app -> sources -> provider library
```
Never:
```text
sources -> app/render/chunking/transcript/transforms
```

## Verification
- URL metadata can be inspected without full prepare
- missing subtitles return structured `NoTranscript`
- local `.wav`, `.mp3`, `.m4a`, `.mp4`, and `.webm` files are detected as media sources for ASR fallback
- provider payloads are converted at adapter boundary
- cache writes are explicit
