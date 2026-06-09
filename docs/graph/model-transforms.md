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
Persistent cache uses runtime.cache_dir/models/faster-whisper for model ids.
Explicit local model paths are local-only automatically: no download_root and local_files_only=true.
offline=true maps to local_files_only=True so model downloads are blocked.
Managed-cache creation/download failures are wrapped as actionable AsrExecutionError messages that suggest freeing cache space, moving runtime.cache_dir, or using an explicit local model path.
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

Visual planning API currently lives in:

```text
src/vctx/transforms/visual_planning.py
```

Public types:

```python
EvidenceKind = Literal["metadata", "transcript", "frame", "probe"]
ActionName = Literal["sample", "ocr", "describe", "capture"]
OperationRoute = Literal["deterministic", "local", "free-online", "configured-online"]

class Evidence(BaseModel):
    kind: EvidenceKind
    name: str
    weight: float = 1.0        # clamped to 0.0..1.0

class VisualOperation(BaseModel):
    name: ActionName
    route: OperationRoute = "deterministic"
    provider_id: str | None = None


def baseline_visual_operations() -> list[VisualOperation]

class VisualSourceSignals(BaseModel):
    has_video: bool = False
    duration_seconds: float | None = None
    title: str | None = None
    description: str | None = None
    transcript_timestamps: bool = False
    operations: list[VisualOperation] = [
        VisualOperation(name="sample"),
        VisualOperation(name="capture"),
    ]
    evidence: list[Evidence] = []

class AcquisitionAction(BaseModel):
    name: ActionName
    params: dict[str, Any] = {}

class VisualAssessment(BaseModel):
    visual_yield: float
    audio_sufficiency: float
    recipe: list[AcquisitionAction] = []
    evidence: list[Evidence] = []
    rationale: str
    cautions: list[str] = []
```

Public call:

```python
def plan_visual_acquisition(signals: VisualSourceSignals) -> VisualAssessment
```

Concrete data flow:

```text
metadata/transcript/probe observations
  -> Evidence[]
environment/config route discovery
  -> VisualOperation[]        # only executable operations for this run
Evidence[] + VisualOperation[]
  -> VisualSourceSignals
  -> plan_visual_acquisition(...)
  -> VisualAssessment
       visual_yield
       audio_sufficiency
       recipe: AcquisitionAction[]
       evidence: Evidence[]
       rationale
       cautions
```

Recipe grammar:

```text
sample(strategy="cover", budget=1)
sample(strategy="changes", budget=N, min_gap_s=S)
sample(strategy="changes+anchors", budget=N, min_gap_s=S)
ocr(route="local", provider_id="rapidocr-onnxruntime")
describe(route="free-online" | "configured-online", provider_id="...")
capture()
```

Non-error availability rule:

```text
available operations shape the recipe before execution.
```

If no OCR operation exists, the recipe does not include `ocr()`. If no VLM/description operation exists, the recipe does not include `describe()`. The executor should not receive unavailable actions and then issue fallback warnings. It executes the recipe it was given. Lossless provenance is maintained by `capture()`, not by warning-driven skip behavior.

Route bridge examples:

```python
# deterministic baseline, always safe when video exists
[
    VisualOperation(name="sample"),
    VisualOperation(name="capture"),
]

# local OCR route available
[
    VisualOperation(name="sample"),
    VisualOperation(name="ocr", route="local", provider_id="rapidocr-onnxruntime"),
    VisualOperation(name="capture"),
]

# configured/free VLM route available
[
    VisualOperation(name="sample"),
    VisualOperation(name="describe", route="configured-online", provider_id="default-vision"),
    VisualOperation(name="capture"),
]
```

Current deterministic evidence derivation:

```text
title/description contains podcast|interview|audio only
  -> Evidence(kind="metadata", name="audio-complete", weight=0.7)

title/description contains lecture|slides|presentation|ppt
  -> dense-text + visual-reference evidence

title/description contains screen|demo|coding|walkthrough
  -> screen-content + dense-text evidence

title/description contains diagram|architecture|flowchart|graph
  -> diagram-reference evidence

title/description contains formula|equation|proof|derivation
  -> formula-reference evidence
```

Example outputs:

```python
# audio-sufficient source
VisualAssessment(
    visual_yield=0.0,
    audio_sufficiency=0.95,
    recipe=[
        AcquisitionAction(name="sample", params={"strategy": "cover", "budget": 1}),
        AcquisitionAction(name="capture"),
    ],
)

# slide/screen source
VisualAssessment(
    visual_yield=0.9,
    recipe=[
        AcquisitionAction(
            name="sample",
            params={"strategy": "changes+anchors", "budget": 40, "min_gap_s": 8},
        ),
        AcquisitionAction(name="ocr"),
        AcquisitionAction(name="capture"),
    ],
)

# formula/layout-heavy source
VisualAssessment(
    visual_yield=0.95,
    recipe=[
        AcquisitionAction(
            name="sample",
            params={"strategy": "changes+anchors", "budget": 15, "min_gap_s": 5},
        ),
        AcquisitionAction(name="ocr"),
        AcquisitionAction(name="describe"),
        AcquisitionAction(name="capture"),
    ],
    cautions=["description is model output; keep source frames"],
)
```

Visual execution APIs consume the already-shaped recipe rather than re-inferring source class or checking for missing adapters. The sample+capture+local OCR+configured VLM slice is implemented in:

```text
src/vctx/models/visual.py
src/vctx/transforms/visual_cases.py
src/vctx/transforms/visual_frames.py
src/vctx/transforms/model_resolution.py
src/vctx/transforms/visual_ocr.py
src/vctx/transforms/visual_vlm.py
src/vctx/transforms/visual_routes.py
src/vctx/transforms/visual_execute.py
```

Implemented public models/APIs:

```python
class FrameAsset(BaseModel):
    id: str
    timestamp_seconds: float | None
    path: Path
    source: Literal["cover", "scene_change", "transcript_anchor", "probe"]
    evidence: list[Evidence]

class VisualRecord(BaseModel):
    id: str
    timestamp_seconds: float | None
    frame_id: str
    kind: Literal["ocr", "description", "capture"]
    text: str | None
    artifact_path: str | None
    evidence: list[Evidence]

class VisualRecordSet(BaseModel):
    records: list[VisualRecord] = []


def discover_visual_operations(
    policy: CapabilityPolicy,
    *,
    vision_providers: dict[str, ProviderConfig] | None = None,
) -> list[VisualOperation]


def deterministic_essential_cases(transcript: Transcript) -> list[EssentialVisualCase]


def dedupe_cases_by_window(
    cases: list[EssentialVisualCase], *, min_gap_s: float, budget: int
) -> list[EssentialVisualCase]


def resolve_model_ref(
    value: str | None,
    *,
    capability: ModelCapability,
    env: Mapping[str, str],
    base_dir: Path | None = None,
    openrouter_models: list[OpenRouterModel] | None = None,
) -> ResolvedModelRoute


def choose_openrouter_free_model(
    models: list[OpenRouterModel], *, capability: ModelCapability
) -> OpenRouterModel | None


def extract_frames(
    media_asset: MediaAsset,
    sample_action: AcquisitionAction,
    frames_dir: Path,
) -> list[FrameAsset]


def run_visual_context(
    assessment: VisualAssessment,
    media_asset: MediaAsset,
    out_dir: Path,
    *,
    vision_providers: dict[str, ProviderConfig] | None = None,
    env_files: list[Path] | None = None,
) -> VisualRecordSet
```

Planned probe APIs:

```python
def make_visual_probe_plan(metadata, transcript) -> list[AcquisitionAction]
```

Concrete bridge:

```text
discover_visual_operations(...)
  -> sample + capture always when video is available
  -> add ocr only when local/free/configured OCR route is executable
  -> add describe only when free/configured VLM route is executable
  -> VisualOperation[]

plan_visual_acquisition(VisualSourceSignals(..., operations=ops))
  -> recipe contains only executable actions

run_visual_context(assessment, media_asset, out_dir)
  -> executes every action in recipe
  -> writes canonical frame artifacts as PNG for OCR/capture consistency
  -> no "describe skipped because VLM missing" branch
  -> no "ocr skipped because rapidocr missing" branch
```

Adapter absence is handled before planning by not adding the operation. If visual evidence asks for layout/formula understanding but no description route exists, `capture()` still preserves source frames; no skipped-description warning is necessary.

Optional model judge contract:

```python
class VisualJudgeAdapter(Protocol):
    def judge(self, bundle: VisualDiagnosisBundle) -> list[Evidence]: ...
```

The judge may add `Evidence`; it must not return provider-specific plans. This keeps free/configured LLM/VLM calls optional, inspectable, and replaceable.

Sampling goal: maximize source information while minimizing relative entropy against the transcript-grounded state. Do not frame this as direct visual informativeness detection: judging that from the video stream alone is a recursive circuit. Prefer transcript-anchored hypotheses when timestamps exist, then use frame extraction/OCR/VLM as evidence generation across different aspects. Deterministic transcript cues now produce typed `EssentialVisualCase` anchors with simple time-window dedup before frame extraction. Scene/keyframe signals are weak evidence for candidate anchors, not ground truth; bounded sampling should still enforce minimum intervals and near-duplicate removal.

Concrete default stack:

```text
local OCR adapter: rapidocr-onnxruntime
frame extraction: ffmpeg canonical PNG output; pillow utilities later; opencv-python-headless only when needed
model reference resolver: implemented for auto, none, openrouter:<model-id>, local:<path-or-id>, hf:<repo-id>, alias:<name>
local VLM adapter: none by default
free remote VLM: OpenRouter registry currently exposes free text+image->text models; explicit `openrouter:<model-id>` visual routes are wired into planner/executor; runtime registry fetch/cache for `auto` is not integrated yet
configured-online VLM/OCR: OpenAI-compatible vision adapter when configured through current provider-alias path
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
  "source_artifacts": ["visual/frames/frame-0001.png"],
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
