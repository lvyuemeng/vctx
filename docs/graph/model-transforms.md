# vctx Model Transformation Stack

This document turns the abstract internal-transformation architecture into concrete technology choices.

It is intentionally opinionated: `vctx` should choose one curated default per capability instead of exposing a large provider/model menu.

## Product rule

`vctx` may use models internally to transform source material into source-grounded records.

It should not become the user-facing AI layer.

Good internal transformations:

```text
audio -> timestamped transcript
frame -> OCR text
frame -> visual description
noisy transcript -> cleaned transcript
transcript/chunks -> chapter candidates
```

Out of scope for `vctx` itself:

```text
chat
Q&A
final summary
knowledge management
cross-video memory
RAG
personal study assistant
```

External agents read `context.md`, `chunks.json`, `manifest.json`, and other artifacts to perform those user-facing reasoning tasks.

## Module role

This file is the `transforms` module graph plus concrete model stack.

```text
app
  -> transforms
      -> local model adapters
      -> free zero-config online adapters
      -> configured-online adapters
      -> models / cache / manifest evidence
```

`transforms` is atomic: it turns prepared source inputs into normalized source-grounded records plus evidence. It does not render, write final artifacts, or talk to users.

## Selection policy

For each capability, choose one curated default route. Avoid exposing provider/model menus.

Default route order:

```text
1. Deterministic source data
   - official subtitles
   - automatic platform subtitles
   - user-provided transcript

2. Best practical zero-config route
   - local when efficient and quality is good enough
   - free zero-config online when quality is better and the service is stable/safe enough

3. Default configured-online route
   - used when zero-config quality is not enough and project/user config exists
   - may require credentials
   - may upload media/text
   - must be manifest-recorded

4. External-command route
   - developer escape hatch only
   - not primary UX
```

Important correction: locality is not the main goal. For high-information-throughput visual tasks, a weak local model can be worse than a free or configured online model. The preferred route is the best practical default route with the least user configuration.

## Capability stack summary

| Capability | Default behavior | Curated local route | Free zero-config online route | Configured-online route | Why |
| --- | --- | --- | --- | --- | --- |
| URL metadata/subtitles | always deterministic first | `yt-dlp` Python package | none needed | none | No model needed if subtitles exist. |
| ASR | auto-adapt when transcript is missing and transcription is allowed by default policy | `faster-whisper` via optional `asr` extra | use if stable/no-auth/no-cost and better for the input | curated audio transcription API adapter | Solves no-transcript case. Local is often good enough, but not always fastest/best. |
| OCR | auto-adapt when visual text is likely useful | `rapidocr-onnxruntime` via optional `ocr` extra | use if stable and higher-quality than local | curated vision/OCR API adapter | Slide/code text can be important; local OCR is often acceptable. |
| Frame description | auto-adapt toward best visual route; online often wins | no default local VLM yet | preferred if stable/no-auth/no-cost and useful | curated lightweight VLM API adapter | Visual understanding is high-throughput; local small VLMs may be too weak. |
| Transcript cleanup | deterministic cleanup by default; model cleanup only when useful/safe | no default local LLM yet | acceptable for punctuation/format cleanup if stable | curated text model adapter | Cleanup must not silently rewrite meaning. |
| Chapter suggestion | deterministic/time-based candidates first; model route when useful | no default local LLM yet | acceptable for rough candidates if stable | curated text model adapter | Produces candidates, not a summary. |
| Language detection | lightweight local/default heuristic | small local heuristic/library | rarely needed | rarely needed | Should not become a general LLM call. |

## Default runtime dependencies

The default install should stay small and deterministic:

```text
typer
pydantic
yt-dlp
platformdirs
webvtt-py
srt
```

Default `vctx prepare` should use:

```text
URL/local input
  -> metadata/subtitle/transcript acquisition
  -> parsing
  -> deterministic cleanup
  -> chunking
  -> artifacts
```

No ASR, OCR, VLM, cloud SDK, or large model package should be required by the default path.

## Optional extras

### `asr` extra

Purpose:

```text
audio/media -> timestamped transcript
```

Candidate stack:

```text
faster-whisper
av or ffmpeg integration for audio handling when needed
```

Route:

```text
prepare INPUT
  -> if subtitles are missing and transcript fallback is allowed
  -> download/extract audio if needed
  -> run default ASR route:
       1. faster-whisper when installed and suitable
       2. free zero-config online ASR when stable/better and allowed by policy
       3. configured-online ASR when configured
  -> produce transcript.raw.json
  -> normalize/chunk/render
```

Recommended model policy:

```text
small/base for default CPU-friendly behavior
medium/large only through advanced config later, not normal CLI choice
```

Why:

```text
free
local
good enough for many videos
common and maintained
no provider account
```

Caveat:

```text
Local ASR may be slow or lower quality for noisy audio, multilingual speech, or poor hardware.
```

If local ASR is not good enough, the default route should adapt to the configured/free online route rather than exposing a menu of ASR providers.

### `ocr` extra

Purpose:

```text
sampled frames -> timestamped visual text records
```

Candidate stack:

```text
rapidocr-onnxruntime
pillow
opencv-python-headless, only if frame/image processing needs it
```

Route:

```text
prepare INPUT
  -> if visual context is enabled or auto-detected as useful
  -> sample frames
  -> run default visual-text route:
       1. local OCR when suitable
       2. free zero-config OCR/VLM when better and allowed by policy
       3. configured-online vision/OCR when configured
  -> visual_records.json
  -> include visual text in readable/context artifacts
```

Why:

```text
free
local
reasonable for slide text and screen recordings
lighter than many full OCR frameworks
```

Caveat:

```text
OCR quality may be poor on tiny text, stylized slides, fast motion, handwriting, dense UI screenshots, and multilingual content.
```

If local OCR quality is not good enough, the default visual route should adapt to a better free/configured online route when policy allows it.

### `online-ai` extra

Purpose:

```text
configured-online model transformations
```

Candidate stack:

```text
httpx
```

Avoid provider SDKs as default. Add a provider-specific SDK only if plain HTTP is insufficient.

Configured-online routes are selected by default routing when the project/user configuration exists and the zero-config route is not good enough for the capability.

Rules:

```text
must be explicit
must record provider/model in manifest
must record whether media/text was uploaded
must record warnings about cost/privacy when applicable
must not be required for default prepare
```

### Free zero-config online routes

A free zero-config online route is preferred over local when:

```text
- it requires no user API key or account
- it is stable enough for CLI use
- it has acceptable rate limits
- it gives materially better quality than the local route
- network/upload behavior is acceptable for the default policy
- the manifest records that online processing occurred
```

Because free public endpoints can disappear, throttle, or change behavior, they must be treated as discoverable curated routes, not hard assumptions. `--offline` or equivalent config should disable them.

## Capability API graph

### ASR graph

```text
prepare INPUT
  -> acquire metadata
  -> try subtitles
       -> if subtitles found: skip ASR
       -> if subtitles missing: continue
  -> route_default_asr(policy, environment, media)
       -> deterministic unavailable
       -> best zero-config route: local faster-whisper or free-online if better/available
       -> configured-online route when configured and needed
       -> unavailable: partial/fail with clear manifest
  -> transcript.raw.json
  -> transcript.clean.json
  -> chunks.json
  -> context.md/readable.md
  -> manifest step: transform.asr
```

### Visual context graph

```text
prepare INPUT
  -> acquire media/frame capability
  -> sample frames using deterministic policy
       -> time interval
       -> scene/keyframe later if needed
  -> route_default_visual(policy, environment, frames)
       -> skip when visual context is not useful or not supported
       -> local OCR for visual text when good enough
       -> free-online OCR/VLM when better/available
       -> configured-online vision route when configured and needed
  -> visual_records.json
  -> optional visual sections in readable.md/context.md
  -> manifest step: transform.visual_context
```

Visual model note:

```text
For frame description and dense visual understanding, online is often the better route.
Do not over-prioritize local if the local model is too weak or too slow.
```

### Cleanup graph

```text
prepare INPUT
  -> parse transcript
  -> deterministic cleanup
  -> route_default_cleanup(policy, transcript)
       -> deterministic cleanup only when model cleanup is not useful/safe
       -> free zero-config cleanup when stable and safe
       -> configured-online cleanup when configured and needed
  -> transcript.clean.json
  -> manifest step: transform.cleanup
```

Cleanup constraints:

```text
preserve timestamps
preserve segment ids when practical
avoid semantic rewriting
record model-mediated cleanup
```

### Chapter graph

```text
prepare INPUT
  -> chunks/transcript
  -> deterministic boundary candidates
  -> route_default_chapters(policy, chunks)
       -> deterministic candidates when good enough
       -> free zero-config model candidates when useful/stable
       -> configured-online candidates when configured and needed
  -> chapter_candidates.json
  -> manifest step: transform.chapters
```

Chapter output is structural metadata, not final summarization.

## Manifest transform evidence

Every model route must write evidence like:

```json
{
  "name": "transform.visual_context",
  "status": "ok",
  "provider": "configured-online",
  "provider_name": "curated-vision-provider",
  "model": "configured-vision-model",
  "mode": "online",
  "source_artifacts": ["frames/frame_001.jpg"],
  "output_artifacts": ["visual_records.json"],
  "uploaded": true,
  "cost_may_apply": true,
  "deterministic": false,
  "warnings": [
    "Visual descriptions are generated model output, not source text."
  ]
}
```

For free zero-config online:

```json
{
  "name": "transform.ocr",
  "status": "ok",
  "provider": "free-online",
  "provider_name": "curated-free-ocr-service",
  "mode": "auto",
  "uploaded": true,
  "cost_may_apply": false,
  "requires_user_config": false
}
```

For local:

```json
{
  "name": "transform.asr",
  "status": "ok",
  "provider": "local",
  "provider_name": "faster-whisper",
  "model": "small",
  "mode": "local",
  "uploaded": false,
  "cost_may_apply": false,
  "requires_user_config": false
}
```

## Implementation recommendation

Build in this order:

```text
1. URL metadata/subtitles through yt-dlp
2. no-transcript partial manifest
3. local ASR with faster-whisper optional extra
4. visual frame sampling + local OCR
5. configured-online VLM/OCR for visual high-throughput cases
6. free zero-config online registry if a stable route is identified
7. model cleanup/chapter candidates
```

Do not block URL/subtitle work on model-provider decisions.

The first model transformation to implement should be ASR because it directly solves the no-transcript failure case.
