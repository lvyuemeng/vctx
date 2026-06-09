from __future__ import annotations

import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, cast

from platformdirs import user_cache_path
from pydantic import BaseModel, Field

from vctx.render.bundle import DEFAULT_FORMATS, OutputFormat


class CapabilityEnabled(StrEnum):
    AUTO = "auto"
    TRUE = "true"
    FALSE = "false"


class WorkflowProfile(StrEnum):
    DEFAULT = "default"
    TRANSCRIPT = "transcript"
    VISUAL = "visual"
    FULL = "full"
    METADATA = "metadata"


CapabilityRoute = Literal[
    "auto",
    "default",
    "local",
    "free-online",
    "configured-online",
    "disabled",
    "explicit",
]
ProviderCostMode = Literal["free", "paid", "local", "unknown"]
ProviderGroup = Literal["asr", "ocr", "vision", "text"]
AsrInstanceType = Literal["local-faster-whisper", "openai-compatible-audio"]
InstanceCachePolicy = Literal["persistent", "disabled"]
InstanceUploadPolicy = Literal["none", "required"]


class PrepareRequest(BaseModel):
    input: str
    out_dir: Path
    language: str | None = None
    overwrite: bool = False
    chunk_max_chars: int = 6000
    chunk_max_seconds: int | None = None
    cache_dir: Path | None = None
    keep_temp: bool = False
    formats: set[OutputFormat] = DEFAULT_FORMATS
    workflow: WorkflowProfile = WorkflowProfile.DEFAULT
    offline: bool = False
    config_path: Path | None = None


class RuntimeConfig(BaseModel):
    cache_dir: Path
    keep_temp: bool
    offline: bool
    workflow: WorkflowProfile
    env_files: list[Path] = Field(default_factory=list)


class SourceConfig(BaseModel):
    preferred_language: str | None
    subtitle_fallback_order: list[str] = Field(
        default_factory=lambda: ["manual", "automatic", "fallback"]
    )
    media_download_policy: Literal["auto", "never"] = "auto"


class CapabilityPolicy(BaseModel):
    enabled: CapabilityEnabled
    route: CapabilityRoute = "auto"
    instance: str | None = None
    allow_network: bool = True
    allow_upload: bool = True
    allow_paid: bool = False
    preferred_provider: str | None = None
    model: str | None = None


class TransformConfig(BaseModel):
    asr: CapabilityPolicy
    visual_context: CapabilityPolicy
    cleanup: CapabilityPolicy
    chapters: CapabilityPolicy


class OutputConfig(BaseModel):
    formats: set[OutputFormat]
    chunk_max_chars: int
    chunk_max_seconds: int | None


class ProviderConfig(BaseModel):
    type: str
    base_url: str | None = None
    api_key_env: str | None = None
    model: str | None = None
    cost_mode: ProviderCostMode = "unknown"


class ProviderRegistry(BaseModel):
    asr: dict[str, ProviderConfig] = Field(default_factory=dict)
    ocr: dict[str, ProviderConfig] = Field(default_factory=dict)
    vision: dict[str, ProviderConfig] = Field(default_factory=dict)
    text: dict[str, ProviderConfig] = Field(default_factory=dict)


class AsrInstanceConfig(BaseModel):
    type: AsrInstanceType
    model: str | None = None
    model_policy: Literal["auto", "tiny", "base", "small", "medium", "large"] = "auto"
    cache: InstanceCachePolicy = "persistent"
    base_url: str | None = None
    api_key_env: str | None = None
    cost: ProviderCostMode = "unknown"
    upload: InstanceUploadPolicy = "none"


class InstanceRegistry(BaseModel):
    asr: dict[str, AsrInstanceConfig] = Field(default_factory=dict)


class ResolvedConfig(BaseModel):
    runtime: RuntimeConfig
    source: SourceConfig
    transforms: TransformConfig
    output: OutputConfig
    providers: ProviderRegistry = Field(default_factory=ProviderRegistry)
    instances: InstanceRegistry = Field(default_factory=InstanceRegistry)


def _policy(
    enabled: CapabilityEnabled, *, offline: bool, allow_upload: bool = True
) -> CapabilityPolicy:
    network_allowed = not offline
    return CapabilityPolicy(
        enabled=enabled,
        route="auto" if enabled != CapabilityEnabled.FALSE else "disabled",
        allow_network=network_allowed,
        allow_upload=network_allowed and allow_upload,
        allow_paid=False,
    )


def _workflow_capabilities(
    workflow: WorkflowProfile,
) -> tuple[CapabilityEnabled, CapabilityEnabled, CapabilityEnabled, CapabilityEnabled]:
    if workflow == WorkflowProfile.METADATA:
        return (
            CapabilityEnabled.FALSE,
            CapabilityEnabled.FALSE,
            CapabilityEnabled.FALSE,
            CapabilityEnabled.FALSE,
        )
    if workflow == WorkflowProfile.TRANSCRIPT:
        return (
            CapabilityEnabled.AUTO,
            CapabilityEnabled.FALSE,
            CapabilityEnabled.FALSE,
            CapabilityEnabled.FALSE,
        )
    if workflow == WorkflowProfile.VISUAL:
        return (
            CapabilityEnabled.AUTO,
            CapabilityEnabled.TRUE,
            CapabilityEnabled.AUTO,
            CapabilityEnabled.AUTO,
        )
    if workflow == WorkflowProfile.FULL:
        return (
            CapabilityEnabled.AUTO,
            CapabilityEnabled.TRUE,
            CapabilityEnabled.TRUE,
            CapabilityEnabled.TRUE,
        )
    return (
        CapabilityEnabled.AUTO,
        CapabilityEnabled.AUTO,
        CapabilityEnabled.AUTO,
        CapabilityEnabled.AUTO,
    )


def _read_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    return data if isinstance(data, dict) else {}


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name, {})
    return value if isinstance(value, dict) else {}


def _capability_config(config: dict[str, Any], capability: str) -> dict[str, Any]:
    transforms = _section(config, "transforms")
    value = transforms.get(capability, {})
    return value if isinstance(value, dict) else {}


def _config_value(section: dict[str, Any], name: str, default: Any) -> Any:
    value = section.get(name, default)
    return default if value == "auto" else value


def _resolve_provider_registry(config: dict[str, Any]) -> ProviderRegistry:
    providers = _section(config, "providers")
    registry: dict[str, dict[str, ProviderConfig]] = {}
    for group in ("asr", "ocr", "vision", "text"):
        group_table = providers.get(group, {})
        if not isinstance(group_table, dict):
            registry[group] = {}
            continue
        registry[group] = {
            name: ProviderConfig.model_validate(raw_provider)
            for name, raw_provider in group_table.items()
            if isinstance(raw_provider, dict)
        }
    return ProviderRegistry.model_validate(registry)


def _resolve_instance_registry(config: dict[str, Any]) -> InstanceRegistry:
    instances = _section(config, "instances")
    asr_table = instances.get("asr", {})
    if not isinstance(asr_table, dict):
        return InstanceRegistry()
    return InstanceRegistry(
        asr={
            name: AsrInstanceConfig.model_validate(raw_instance)
            for name, raw_instance in asr_table.items()
            if isinstance(raw_instance, dict)
        }
    )


def _default_cache_dir() -> Path:
    return user_cache_path("vctx", appauthor=False)


def _paths(values: Any) -> list[Path]:
    if values is None:
        return []
    if isinstance(values, str):
        return [Path(values)]
    if isinstance(values, list):
        return [Path(value) for value in values]
    return []


def _resolve_policy(
    capability: str,
    enabled: CapabilityEnabled,
    *,
    offline: bool,
    config: dict[str, Any],
    allow_upload: bool = True,
) -> CapabilityPolicy:
    values = _capability_config(config, capability)
    policy = _policy(enabled, offline=offline, allow_upload=allow_upload)
    if values:
        policy = policy.model_copy(update=values)
    if offline:
        policy = policy.model_copy(update={"allow_network": False, "allow_upload": False})
    return policy


def resolve_config(request: PrepareRequest) -> ResolvedConfig:
    """Resolve user request/config omissions into concrete default/auto policy."""

    config = _read_config(request.config_path)
    runtime = _section(config, "runtime")
    source = _section(config, "source")
    output = _section(config, "output")

    configured_workflow = _config_value(runtime, "workflow", WorkflowProfile.DEFAULT)
    workflow = request.workflow
    if workflow == WorkflowProfile.DEFAULT and configured_workflow != WorkflowProfile.DEFAULT:
        workflow = WorkflowProfile(configured_workflow)

    configured_offline = bool(_config_value(runtime, "offline", False))
    offline = request.offline or configured_offline
    asr, visual_context, cleanup, chapters = _workflow_capabilities(workflow)

    cache_dir = request.cache_dir
    if cache_dir is None:
        configured_cache = _config_value(runtime, "cache_dir", None)
        cache_dir = Path(configured_cache) if configured_cache is not None else _default_cache_dir()

    preferred_language = request.language
    if preferred_language is None:
        preferred_language = _config_value(source, "preferred_language", None)

    formats = request.formats
    if formats == DEFAULT_FORMATS and "formats" in output:
        formats = {cast(OutputFormat, value) for value in output["formats"]}

    return ResolvedConfig(
        runtime=RuntimeConfig(
            cache_dir=cache_dir,
            keep_temp=request.keep_temp or bool(_config_value(runtime, "keep_temp", False)),
            offline=offline,
            workflow=workflow,
            env_files=_paths(_config_value(runtime, "env_files", [])),
        ),
        source=SourceConfig(
            preferred_language=preferred_language,
            subtitle_fallback_order=_config_value(
                source, "subtitle_fallback_order", ["manual", "automatic", "fallback"]
            ),
            media_download_policy=_config_value(source, "media_download_policy", "auto"),
        ),
        transforms=TransformConfig(
            asr=_resolve_policy("asr", asr, offline=offline, config=config),
            visual_context=_resolve_policy(
                "visual_context", visual_context, offline=offline, config=config
            ),
            cleanup=_resolve_policy("cleanup", cleanup, offline=offline, config=config),
            chapters=_resolve_policy("chapters", chapters, offline=offline, config=config),
        ),
        output=OutputConfig(
            formats=formats,
            chunk_max_chars=int(_config_value(output, "chunk_max_chars", request.chunk_max_chars)),
            chunk_max_seconds=_config_value(output, "chunk_max_seconds", request.chunk_max_seconds),
        ),
        providers=_resolve_provider_registry(config),
        instances=_resolve_instance_registry(config),
    )
