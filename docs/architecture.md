# vctx Architecture

## Purpose

This document describes the architecture of `vctx` at the abstraction level.

It intentionally avoids concrete module names, function signatures, and implementation pseudocode. Those belong in the separated module graphs under [`docs/graph/`](graph/). This document answers a different question:

> What abstract behaviors must the system have, and how should those behaviors cooperate without becoming a monolith?

`vctx` should be understood as a context compiler for video-like sources. It acquires source-grounded material, converts it into a uniform internal representation, optionally applies bounded transformations, and emits inspectable artifacts for humans and external AI agents.

## General view

The system is a one-shot CLI pipeline:

```text
caller intent
  -> source acquisition
  -> source-grounded representation
  -> optional bounded transformations
  -> deterministic preparation
  -> artifact rendering
  -> manifest-backed verification
```

The output directory is the integration boundary. Downstream agents should not need to know which provider, subtitle format, ASR model, or cleanup route produced the artifacts. They should inspect the manifest and consume the generated Markdown/JSON.

## Architectural principles

### Context preparation, not conversation

`vctx` prepares context. It does not own the conversation with the user.

External AI agents are responsible for:

- asking the user what they want
- deciding whether to summarize, compare, teach, or ask follow-up questions
- producing final knowledge-flow explanations
- maintaining memory or cross-video knowledge systems

`vctx` is responsible for:

- acquiring metadata, transcript, audio-derived text, visual text, or other source-grounded material
- preserving provenance and timestamps where possible
- producing durable artifacts
- explaining what happened through a manifest

### Uniform internal representation

External sources differ. The architecture should hide those differences behind normalized internal concepts.

Examples of external shapes:

```text
subtitle track
manual transcript file
auto-generated captions
ASR segments
OCR text from frames
VLM frame descriptions
AI-cleaned transcript segments
```

All should converge into source-grounded internal records before deterministic preparation and rendering.

The architecture should prevent provider-specific payloads from leaking into chunking, rendering, manifest generation, or user-facing artifacts.

### Side effects at the edges

Side effects are allowed, but they must stay at architectural boundaries.

Side-effecting behaviors include:

- network extraction
- local file reads and writes
- cache creation
- media download
- audio extraction
- ASR/OCR/VLM calls
- external process execution
- online provider API calls

Core preparation behaviors should operate on data already acquired by edge behaviors.

This separation makes the tool easy to test, easier to inspect, and less likely to become spaghetti.

### Deterministic by default

The default path should be deterministic whenever practical.

Examples:

- parse known subtitle formats
- normalize obvious subtitle markup
- preserve and sort timestamps
- chunk by explicit budgets
- render known artifact formats
- write a manifest describing the run

Non-deterministic or model-mediated behavior is allowed only as a bounded transformation that is visible in the manifest.

### Explicit optional AI

The boundary is not "no AI." The boundary is:

```text
no embedded AI user interface inside vctx
```

Internal AI transformations are acceptable when they are bounded and source-preparation-oriented, for example:

- audio transcription
- OCR
- frame description
- language detection
- transcript cleanup
- speaker-label cleanup
- chapter-boundary suggestion
- provider routing

These transformations must be:

- explicit through command options or configuration
- selected by a small curated routing policy rather than a large user-facing provider menu
- local, efficient, free, and zero-configuration when local quality is good enough
- allowed to use free zero-configuration online models/services automatically when they are the best practical route and the manifest makes the upload/network behavior clear
- allowed to use configured online providers when local/free-online quality is not good enough and the user explicitly enables that route
- replaceable through adapters internally
- recorded in the manifest
- traceable back to source material when practical
- optional rather than required for the default path

`vctx` may call local models or online APIs behind transformation adapters. The user interface remains CLI commands and artifact files, not chat. Avoid exposing raw external-command wiring as the normal UX; prefer one curated default route per capability.

Technology and concrete model choices are not decided in this abstract architecture document. See [`docs/graph/model-transforms.md`](graph/model-transforms.md) for the concrete model-transformation stack and capability API graph.

## Abstract behavior map

### 1. Intent capture

The caller provides a command, input, and options.

The intent layer should answer:

- What source should be processed?
- Where should durable output be written?
- Which capabilities are allowed?
- Are optional AI transformations permitted?
- What failure mode is preferred: fail, partial output, or fallback?

This layer should not perform provider-specific work. It only turns command-line intent into a structured request.

### 2. Source acquisition

Source acquisition converts user input into source-grounded raw material.

Possible acquisition behaviors:

```text
URL -> metadata
URL -> subtitle track
URL -> audio/video asset
local transcript -> transcript payload
local media -> media asset
```

The acquisition layer owns interaction with external providers and local files. It should produce normalized metadata and raw payloads, not final Markdown.

### 3. Capability routing

Capability routing decides which preparation path is allowed and available.

Examples:

```text
subtitles available -> use subtitles
subtitles unavailable + ASR disabled -> partial manifest or clear failure
subtitles unavailable + ASR enabled -> acquire audio and transcribe
visual enrichment requested -> sample frames and run visual transformation
cleanup requested -> apply transcript cleanup transformation
```

Routing must be policy-driven, not hidden magic. If a route uses AI, expensive downloads, or online services, that route must be allowed explicitly and recorded.

### 4. Internal transformation

A transformation converts one source-grounded representation into another.

Examples:

```text
audio asset -> timestamped transcript
frame image -> timestamped visual note
raw transcript -> cleaned transcript
raw transcript -> suggested chapter boundaries
mixed source records -> ordered context records
```

Transformations can be deterministic or AI-mediated.

All transformations should preserve provenance:

- source input
- provider/tool/model, when applicable
- timestamps, when available
- numeric scores, cautions, or warning information, when meaningful
- whether content is source text, machine transcript, OCR text, or generated description

### 4.1 Visual acquisition contract

Visual acquisition is not a single class-inference step. It is a small planning workflow:

```text
observed evidence -> numeric assessment -> ordered acquisition recipe
```

The architecture should avoid global source-class enums such as `podcast`, `slides`, or `diagram` as the main decision output. Those labels can appear as evidence names, but the durable contract is a composable set of observations and actions.

The core visual planner owns only pure assessment:

```text
Evidence[] + available VisualOperation[]
  -> visual_yield: 0.0..1.0
  -> audio_sufficiency: 0.0..1.0
  -> AcquisitionAction[]
```

`VisualOperation[]` is the bridge from environment/route selection to recipe construction. It lists operations that are actually executable in this run, such as deterministic sampling/capture, local OCR, or configured/free online description. The planner must not emit an unavailable operation and then rely on the executor to skip it with a warning.

Frame probing, OCR, VLM calls, and optional LLM/VLM judging are edge behaviors. They may add more evidence, but they must not replace the core contract or leak provider payloads into rendering.

A visual acquisition recipe is an ordered operation list:

```text
sample(...)
ocr()
describe()
capture()
```

This lets visual workflows compose without boolean trigger sprawl. For example, a slide lecture can produce `sample + ocr + capture`, while a formula-heavy segment can produce `sample + ocr + describe + capture`, and an audio-sufficient podcast can produce only `sample cover + capture`.

### 5. Normalization

Normalization converts acquired/transformed material into stable internal records.

The architecture should separate normalization from semantic rewriting.

Acceptable normalization:

- strip subtitle markup
- normalize whitespace
- sort by timestamp
- remove empty segments
- assign stable ids
- merge obviously duplicated caption fragments

Semantic rewriting is a bounded transformation, not basic normalization, and must be labeled accordingly.

### 6. Chunking

Chunking prepares normalized records for context injection.

The chunking behavior should preserve traceability:

```text
chunk -> source record ids -> timestamps -> provenance
```

Default chunking should use simple deterministic budgets. Model-specific tokenization can be optional later but should not shape the core architecture.

### 7. Rendering

Rendering converts internal records into artifacts.

The renderer should support at least two audiences:

```text
human-readable Markdown
machine-readable JSON / agent context Markdown
```

Rendering should not fetch, transcribe, call AI, or write files. It should consume prepared records and produce artifact content.

### 8. Artifact writing

Artifact writing is the durable-output boundary.

The writer should:

- respect explicit output directory policy
- avoid deleting user data accidentally
- write files predictably
- write or finalize the manifest after other artifacts
- make partial outputs inspectable when a workflow cannot complete

### 9. Manifest and verification

The manifest is the audit log of a run.

It should answer:

- What input was processed?
- Which stages ran?
- Which stages were skipped?
- Which warnings occurred?
- Which artifacts exist?
- Which optional AI transformations were used?
- Which provider/tool/model produced transformed content?
- Is the result complete, partial, or failed?

The manifest is the primary verification artifact for external agents.

## Data categories

The architecture distinguishes these categories instead of treating everything as generic text.

### Source metadata

Describes the input source:

- source identity
- title
- duration
- uploader/channel, when available
- provider/extractor
- language hints

### Source payload

Raw acquired material:

- subtitle text
- transcript file text
- audio asset
- frame image
- provider metadata payload, while still inside the adapter boundary

### Source-grounded records

Normalized, timestamped units:

- transcript segment
- OCR segment
- frame description segment
- chapter boundary candidate

### Prepared context records

Records shaped for context injection:

- chunks
- readable timeline sections
- context-pack sections

### Run evidence

Artifacts proving what happened:

- manifest
- warnings
- provenance
- artifact references
- optional transformation metadata

## Handling missing transcripts

The architecture must not assume every video site provides transcripts.

When transcript-like data is unavailable, the system should support three policy outcomes:

```text
fail clearly
write partial metadata/manifest artifacts
run an explicitly enabled fallback transformation such as ASR
```

The default should not silently call cloud AI, download large media, or pretend a full context pack exists.

A no-transcript situation is not an architectural exception; it is a normal branch in the capability router.

## Internal AI transformation model

Internal AI transformations are modeled as adapters that consume and produce source-preparation data.

They are not modeled as user-facing assistants.

Abstract adapter contract:

```text
input artifact or record
  + transformation intent
  + provider configuration
  -> transformed records
  + transformation evidence
```

Examples:

```text
audio + ASR intent -> transcript segments + ASR evidence
frame + OCR intent -> visual text segments + OCR evidence
transcript + cleanup intent -> cleaned transcript + cleanup evidence
transcript + chapter intent -> chapter candidates + chapter evidence
```

The evidence should be written into the manifest and, when useful, separate JSON artifacts.

This lets an external agent decide whether to trust, cite, summarize, or rerun a step.

## Boundary with external AI agents

The intended collaboration is:

```text
external agent decides goal
external agent invokes vctx with explicit options
vctx prepares context artifacts
external agent reads manifest/context/readable artifacts
external agent performs final summarization or knowledge-flow synthesis
```

`vctx` may use AI internally to prepare better source records, but it should not become the agent.

## Evolution strategy

New capabilities should be added as new acquisition or transformation behaviors, not as cross-cutting application features.

Preferred evolution:

```text
local transcript input
URL metadata
URL subtitles
partial manifest on missing transcript
explicit ASR fallback
visual/OCR enrichment
optional cleanup/chapter transformations
```

Each capability should have a verification checklist in [`docs/workflow.md`](workflow.md) and concrete function-level details in [`docs/graph/`](graph/).

## Architectural anti-patterns

Avoid:

- provider payloads flowing through the whole app
- CLI code performing extraction/transcription/rendering directly
- renderers writing files
- chunkers calling providers
- hidden model calls
- default cloud calls
- chat prompts embedded as product behavior
- global mutable workflow state
- one giant prepare function that knows every provider detail
- treating partial output as failure when it can be useful evidence

The architecture should remain boring, inspectable, and composable.
