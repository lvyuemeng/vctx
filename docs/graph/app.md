# Application Module Graph

## Purpose
Orchestrate one `vctx` workflow from request/config resolution to artifacts.

Application code owns workflow order and policy dispatch. It does not parse subtitle formats, call model/provider SDKs, render Markdown, or write provider-specific payloads inline.

## Dependencies

```text
app
  -> models
  -> config resolution helpers
  -> sources
  -> subtitles
  -> transcript
  -> transforms
  -> chunking
  -> render
  -> io
  -> manifest
  -> errors
```

Tree direction:

```text
cli -> app -> module APIs -> adapter leaves
```

Lower modules must not import `app`.

## Configuration design

Normal users should not configure providers or modes. The application resolves a small request plus optional config into a complete `ResolvedConfig` before any workflow step runs.

### Configuration layers

```text
BuiltInDefaults
  -> project config file, if present
  -> user config file, if present
  -> environment variables, only for secrets/credentials and coarse flags
  -> CLI/request overrides
  -> ResolvedConfig
```

Later layers override earlier layers only for fields they explicitly set. Missing fields are not errors; they become `default` or `auto` values.

### Missing-field rule

Every optional config field must have one of these meanings:

```text
missing / null
  -> use built-in default

default
  -> use the curated project default for this capability

auto
  -> inspect source, environment, installed extras, network policy, and configured providers
  -> choose the best route

false / disabled
  -> do not run this optional capability

explicit value
  -> use the value only if it is supported; otherwise fail clearly
```

The caller should not need to specify `local`, `online`, provider names, or model names in normal use.

### Request/config shapes

```text
PrepareRequest
  input: str
  out: Path
  language: str | Auto = Auto
  overwrite: bool = false
  cache_dir: Path | Default = Default
  formats: list[Format] | Default = Default
  workflow: default | transcript | visual | full | metadata = default
  offline: bool = false
  config_path: Path | None = None
```

```text
ResolvedConfig
  runtime:
    cache_dir
    keep_temp
    offline
    workflow
  source:
    preferred_language
    subtitle_fallback_order
    media_download_policy
  transforms:
    asr: CapabilityPolicy
    visual_context: CapabilityPolicy
    cleanup: CapabilityPolicy
    chapters: CapabilityPolicy
  output:
    formats
    chunk_max_chars
    chunk_max_seconds
```

```text
CapabilityPolicy
  enabled: auto | true | false
  route: default | auto | disabled | explicit
  allow_network: bool
  allow_upload: bool
  allow_paid: bool
  preferred_provider: optional advanced/debug value
  model: optional advanced/debug value
```

Default capability behavior:

| Capability | Missing field resolves to | Normal default behavior |
| --- | --- | --- |
| source metadata/subtitles | default | always try deterministic metadata/subtitles first |
| transcript fallback / ASR | auto | run only if no transcript exists and a default route is available |
| visual context | auto | run only when visual records are likely useful and a safe route exists |
| cleanup | auto | deterministic cleanup always; model cleanup only if safe/useful |
| chapters | auto | deterministic candidates when useful; model route only if safe/useful |

Workflow instances are decisive presets, not vague trigger flags:

| Workflow | ASR | visual context | cleanup | chapters |
| --- | --- | --- | --- | --- |
| `default` | auto | auto | auto | auto |
| `transcript` | auto | false | false | false |
| `visual` | auto | true | auto | auto |
| `full` | auto | true | true | true |
| `metadata` | false | false | false | false |

### Config file sketch

Config should be small and optional:

```toml
[runtime]
offline = false
workflow = "default"

[source]
preferred_language = "auto"

[workflow.default]
# Optional. Missing capability fields resolve to default/auto.
visual_context = "auto"
cleanup = "auto"
chapters = "auto"

[providers.default_online]
# Optional. Missing means configured-online routes are unavailable.
base_url = "https://..."
api_key_env = "VCTX_API_KEY"
```

If `[providers.default_online]` is missing, dispatch does not fail during config load. It simply marks configured-online routes as unavailable.

## API graph

```text
PrepareRequest
  -> prepare_context_pack(request)
      -> resolve_config(request)
      -> validate output policy
      -> create run context and cache/session context
      -> detect source
      -> acquire metadata
      -> acquire transcript payload if deterministic source exists
      -> if transcript payload missing:
           -> transforms.route_transcript_fallback(config.transforms.asr, source_state)
      -> parse transcript payload
      -> normalize transcript
      -> transforms.run_cleanup_if_needed(config.transforms.cleanup, transcript)
      -> transforms.run_visual_if_needed(config.transforms.visual_context, source_state)
      -> chunk records
      -> transforms.run_chapters_if_needed(config.transforms.chapters, chunks)
      -> render bundle
      -> write artifacts
      -> write manifest
      -> PrepareResult
```

## Model workflow dispatch

The app asks transform module APIs for a route. It does not choose provider/model details itself.

```text
CapabilityPolicy + EnvironmentState + SourceState
  -> transforms.plan_<capability>()
      -> RoutePlan
          selected: deterministic | local | free-online | configured-online | unavailable | skipped
          provider_id
          model_id
          reason
          requirements
          warnings
```

Then:

```text
RoutePlan
  -> if skipped: record skipped step
  -> if unavailable and required: fail with actionable error
  -> if unavailable and optional: record partial/skipped manifest step
  -> if available: transforms.run_<capability>(plan, inputs)
  -> normalized records + TransformEvidence
```

Dispatch table:

| Input state | Policy | Result |
| --- | --- | --- |
| transcript exists | any ASR policy | skip ASR; record deterministic transcript source |
| transcript missing, ASR missing/auto | auto=true | plan best default ASR route |
| transcript missing, ASR disabled | false/disabled | partial/fail depending output requirement |
| visual context missing/auto | auto=true | run only if source/media and useful route exist |
| configured-online missing | any | mark configured-online unavailable, try lower/default route |
| free-online unavailable/offline | any | skip free-online, try local/configured if allowed |
| all routes unavailable | required capability | actionable failure |
| all routes unavailable | optional capability | skipped/partial manifest step |

## Auto-adaptation

```text
if transcript exists:
  use transcript
elif config.transforms.asr.enabled is auto/true:
  transforms.plan_asr(config.transforms.asr, environment, source)
else:
  fail clearly or write partial manifest
```

Visual/model-heavy capabilities should not over-prioritize local models. The transform module may select a free zero-config online or configured-online route when that is the best practical default and policy allows network/upload behavior.

## Atomic isolation

Application owns:

```text
config resolution
workflow order
required vs optional behavior
partial/failure policy
manifest step assembly
```

Application does not own:

```text
VTT/SRT parsing
model/provider API calls
OCR/ASR/VLM implementation
chunking algorithms
Markdown rendering
artifact byte writing
```

## Tree dependency rule

```text
cli -> app
app -> config/models/sources/subtitles/transcript/transforms/chunking/render/io/manifest
module APIs -> adapter leaves
```

Never:

```text
transforms -> app
sources -> app
render -> app
io -> app
app -> provider SDK directly
```

## Verification

- config resolution tests cover missing/null/default/auto/disabled/explicit fields
- missing provider config makes configured-online unavailable, not a config-load crash
- `--offline` disables online/free-online routes
- app tests cover happy, partial, skipped, and failure paths
- manifest records every routed/skipped stage and the reason
- provider payloads never leak beyond transform/source adapters
- output directory policy is enforced before side-effecting writes
