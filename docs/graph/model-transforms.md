# Model Transforms Module Graph

## Purpose
Run bounded model-mediated transformations behind the context-preparation workflow.

This module converts prepared source inputs into normalized records plus route/evidence metadata. It is not a chat layer, summarizer, RAG layer, or knowledge manager.

Good transformations:

```text
audio/media -> timestamped transcript
frames -> OCR text records
frames -> visual description records
transcript -> safe cleanup records
chunks -> chapter candidates
```

## Dependencies

### Module dependency tree

```text
app
  -> transforms
      -> models
      -> errors
      -> io.cache/read-only-temp-assets
      -> transform adapters
          -> local_asr
          -> local_ocr
          -> free_online_asr/ocr/vlm/text
          -> configured_online_asr/ocr/vlm/text
```

`transforms` returns records and evidence. It does not render Markdown, write final artifacts, mutate app config, or import `app`.

### Default install dependencies

No heavy model dependency is required for default install.

```text
pydantic        # shared models
httpx           # only in online extra / adapter layer
faster-whisper  # optional asr extra
rapidocr-onnxruntime # optional ocr extra
pillow          # optional visual/frame utility
opencv-python-headless # optional only if frame processing needs it
```

Provider-specific SDKs are not default dependencies. Use plain HTTP adapters unless an SDK is truly required.

## Config input contract

Transform APIs receive resolved policy from `app`. They do not read user config files directly.

```text
CapabilityPolicy
  enabled: auto | true | false      # legacy/internal during refactor
  route: default | auto | disabled | explicit  # legacy/internal during refactor
  instance: str | None              # preferred public selector
```

Preferred local/online separation is by named instance, not booleans:

```text
AsrInstanceConfig
  name: local-default
  type: local-faster-whisper
  model_policy: auto | tiny | base | small | medium | large
  cache: persistent | disabled

AsrInstanceConfig
  name: openai-whisper
  type: openai-compatible-audio
  api_key_env: OPENAI_API_KEY
  model: whisper-1
  cost: paid
  upload: required
```

Missing fields are already resolved by `app` before this module is called:

```text
missing -> default/auto
missing configured provider -> configured-online unavailable
missing local extra -> local route unavailable
missing free-online registry entry -> free-online unavailable
```

## Environment input contract

```text
TransformEnvironment
  installed_extras:
    asr: bool
    ocr: bool
    online_ai: bool
  network_available: bool
  offline: bool
  model_cache_root: Path
  configured_instances:
    asr: dict[str, AsrInstanceConfig]
  free_online_registry:
    asr: RouteDescriptor | None
    ocr: RouteDescriptor | None
    vision: RouteDescriptor | None
    text: RouteDescriptor | None
```

Credential-bearing instances store `api_key_env`, never the secret value. `.env` support belongs in the app/runtime layer; transform execution receives already resolved availability/evidence and reads credentials only for the selected instance.

## Public module API set

### Planning APIs

Planning is pure: no model call, no network call, no media upload.

```text
plan_asr(policy, environment, source_state) -> RoutePlan
plan_visual_context(policy, environment, source_state) -> RoutePlan
plan_cleanup(policy, environment, transcript) -> RoutePlan
plan_chapters(policy, environment, chunks) -> RoutePlan
```

```text
RoutePlan
  capability: asr | visual_context | cleanup | chapters
  selected: skipped | deterministic | local | free-online | configured-online | unavailable
  provider_id: str | None
  model_id: str | None
  reason: str
  requirements: list[str]
  warnings: list[str]
  evidence_seed: TransformEvidence
```

### Execution APIs

Execution APIs perform the bounded transformation selected by a plan.

```text
run_asr(plan, media_asset, instance) -> TranscriptPayload
run_visual_context(plan, frame_assets, cache) -> TransformResult[list[VisualRecord]]
run_cleanup(plan, transcript, cache) -> TransformResult[Transcript]
run_chapters(plan, chunks) -> TransformResult[list[ChapterCandidate]]
```

Current ASR execution status:

```text
run_asr exists for local-faster-whisper instance dispatch.
FasterWhisperAsrAdapter loads faster_whisper.WhisperModel when the optional ASR extra is installed.
Persistent cache uses runtime.cache_dir/models/faster-whisper.
offline=true maps to local_files_only=True so model downloads are blocked.
cache="disabled" requires model to be a local path, avoiding hidden global model downloads.
```

```text
TransformResult[T]
  value: T
  evidence: TransformEvidence
  warnings: list[str]
  artifacts: list[ArtifactRef]
```

### Adapter APIs

Adapters are leaf implementations.

```text
AsrAdapter.transcribe(media_asset, options) -> TranscriptPayload
VisualAdapter.describe_or_ocr(frame_assets, options) -> list[VisualRecord]
CleanupAdapter.clean(transcript, options) -> Transcript
ChapterAdapter.suggest(chunks, options) -> list[ChapterCandidate]
```

All adapters must convert provider-specific payloads to internal models before returning.

## Route-selection algorithm

```text
route_capability(policy, environment, inputs):
  if policy.enabled is false or policy.route is disabled:
    return skipped

  if capability already has deterministic source data:
    return deterministic/skipped

  candidates = []

  if local extra installed and local route is suitable for input:
    candidates.append(local)

  if not environment.offline
     and policy.allow_network
     and free-online route exists
     and route is stable/safe for this input:
    candidates.append(free-online)

  if policy.allow_network
     and policy.allow_upload
     and configured provider exists
     and provider is suitable:
    candidates.append(configured-online)

  return best candidate by capability-specific ranking
  or unavailable with actionable reason
```

Capability-specific ranking may prefer online for high-throughput visual cases:

```text
ASR: deterministic subtitle > local faster-whisper if good enough > free-online if better/stable > configured-online
OCR text: local OCR if clear text > free-online/configured vision when local OCR likely weak
Frame description/VLM: free-online/configured-online often before local; no weak local VLM default
Cleanup: deterministic cleanup > safe free-online/configured cleanup only if it preserves meaning
Chapters: deterministic candidates > safe model candidates when useful
```

## Capability API graphs

### ASR

```text
plan_asr(policy, environment, source_state)
  -> if transcript exists: skipped(reason="transcript already available")
  -> if media unavailable: unavailable(requirement="media asset")
  -> candidate local_asr if faster-whisper installed
  -> candidate free_online_asr if registry route exists and not offline
  -> candidate configured_online_asr if provider config exists
  -> RoutePlan

run_asr(plan, media_asset, cache)
  -> selected adapter transcribes audio/media
  -> adapter returns TranscriptPayload
  -> evidence records provider/model/upload/cost
```

Concrete default stack:

```text
local adapter: faster-whisper
local default model: small/base, selected by project default and hardware policy
configured-online adapter: plain HTTP audio transcription adapter
free-online adapter: only if project registry contains stable no-auth/no-cost route
```

### Visual context

```text
plan_visual_context(policy, environment, source_state)
  -> if visual disabled: skipped
  -> if frames/media unavailable: unavailable or skipped optional
  -> detect whether OCR-only or frame-description is useful
  -> candidate local_ocr if rapidocr installed and likely good enough
  -> candidate free_online_vision if registry route exists and better for input
  -> candidate configured_online_vision if provider config exists
  -> RoutePlan

run_visual_context(plan, frame_assets, cache)
  -> selected adapter performs OCR and/or visual description
  -> returns VisualRecord[]
  -> evidence labels generated descriptions vs source text
```

Concrete default stack:

```text
local OCR adapter: rapidocr-onnxruntime
frame utilities: pillow; opencv-python-headless only when needed
local VLM adapter: none by default
free-online VLM/OCR: preferred when stable and materially better
configured-online VLM/OCR: plain HTTP adapter when configured
```

### Cleanup

```text
plan_cleanup(policy, environment, transcript)
  -> deterministic cleanup already handled by transcript module
  -> if model cleanup unsafe/not useful: skipped
  -> candidate free_online_text if stable and safe
  -> candidate configured_online_text if configured
  -> RoutePlan

run_cleanup(plan, transcript, cache)
  -> selected adapter improves punctuation/format only
  -> preserves timestamps/segment ids when practical
  -> returns Transcript
```

No default local LLM route yet. Do not silently rewrite meaning.

### Chapters

```text
plan_chapters(policy, environment, chunks)
  -> deterministic boundary candidates first
  -> if model candidates useful: choose free-online/configured text route when available
  -> RoutePlan

run_chapters(plan, chunks, cache)
  -> selected adapter returns ChapterCandidate[]
  -> candidates include evidence chunk/segment ids
```

Chapter output is structure, not final summary.

## Transform evidence

Every executed or skipped route returns evidence for the manifest.

```text
TransformEvidence
  capability
  selected_route: skipped | deterministic | local | free-online | configured-online | unavailable
  provider_id
  model_id
  requires_user_config
  uploaded
  cost_may_apply
  deterministic
  source_artifacts
  output_artifacts
  reason
  warnings
```

Example configured-online visual evidence:

```json
{
  "capability": "visual_context",
  "selected_route": "configured-online",
  "provider_id": "default-vision",
  "model_id": "configured-vision-model",
  "requires_user_config": true,
  "uploaded": true,
  "cost_may_apply": true,
  "deterministic": false,
  "source_artifacts": ["frames/frame_001.jpg"],
  "output_artifacts": ["visual_records.json"],
  "warnings": ["Visual descriptions are generated model output, not source text."]
}
```

Example missing provider evidence:

```json
{
  "capability": "asr",
  "selected_route": "unavailable",
  "reason": "No transcript found, ASR extra not installed, no free-online ASR route registered, and no configured ASR provider.",
  "requires_user_config": false,
  "uploaded": false,
  "cost_may_apply": false
}
```

## Atomic isolation

Transforms own:

```text
route planning per capability
adapter invocation
provider payload normalization
model-route evidence
```

Transforms do not own:

```text
reading config files
workflow orchestration
source acquisition
subtitle parsing
chunk rendering
final artifact writing
user-facing summarization
```

## Tree dependency rule

Allowed:

```text
app -> transforms -> adapters -> provider libraries / HTTP
transforms -> models/errors/cache abstractions
```

Forbidden:

```text
transforms -> app
transforms -> render
transforms -> final artifact writer
transforms -> CLI
transforms -> source acquisition orchestration
```

## Verification

- planning tests cover missing config, missing extras, offline mode, missing provider, and optional skip
- execution tests use fake adapters where possible
- provider payloads are normalized before leaving adapters
- every execution result includes `TransformEvidence`
- visual descriptions are labeled as generated model output
- no provider/model menu is required for the normal CLI path
