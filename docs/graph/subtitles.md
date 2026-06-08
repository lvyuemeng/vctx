# Subtitle Parsing Module Graph

## Purpose
Convert subtitle payload text into normalized transcript records.

## Dependencies
```text
subtitles
  -> models
  -> webvtt-py
  -> srt
  -> errors
```

## API graph
```text
parse_transcript_payload(payload, video_id)
  -> if payload.format == vtt: parse_webvtt
  -> if payload.format == srt: parse_srt
  -> if payload.format == json: parse_transcript_json
  -> Transcript
```

## Atomic isolation
Subtitle parsers parse only. They do not fetch subtitles, choose language, normalize semantic text, chunk, render, or write files.

## Tree dependency rule
```text
app -> subtitles -> parser dependency
```
Never:
```text
subtitles -> sources/app/render
```

## Verification
- SRT and VTT tests cover multiline cues
- timestamps are preserved
- empty cues are ignored or flagged consistently
- parser errors are explicit
