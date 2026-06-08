from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from vctx.render.bundle import DEFAULT_FORMATS, OutputFormat


class CapabilityEnabled(StrEnum):
    AUTO = "auto"
    TRUE = "true"
    FALSE = "false"


CapabilityRoute = Literal["auto", "default", "disabled", "explicit"]


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
    auto: bool = True
    offline: bool = False
    visual_context: CapabilityEnabled | None = None
    cleanup: CapabilityEnabled | None = None
    chapters: CapabilityEnabled | None = None
    config_path: Path | None = None


class RuntimeConfig(BaseModel):
    cache_dir: Path | None
    keep_temp: bool
    offline: bool
    auto: bool


class SourceConfig(BaseModel):
    preferred_language: str | None
    subtitle_fallback_order: list[str] = ["manual", "automatic", "fallback"]
    media_download_policy: Literal["auto", "never"] = "auto"


class CapabilityPolicy(BaseModel):
    enabled: CapabilityEnabled
    route: CapabilityRoute = "auto"
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


class ResolvedConfig(BaseModel):
    runtime: RuntimeConfig
    source: SourceConfig
    transforms: TransformConfig
    output: OutputConfig


def _auto_enabled(enabled: CapabilityEnabled | None, *, global_auto: bool) -> CapabilityEnabled:
    if enabled is not None:
        return enabled
    if global_auto:
        return CapabilityEnabled.AUTO
    return CapabilityEnabled.FALSE


def _policy(
    enabled: CapabilityEnabled | None,
    *,
    global_auto: bool,
    offline: bool,
    allow_upload: bool = True,
) -> CapabilityPolicy:
    resolved_enabled = _auto_enabled(enabled, global_auto=global_auto)
    network_allowed = not offline
    return CapabilityPolicy(
        enabled=resolved_enabled,
        route="auto" if resolved_enabled != CapabilityEnabled.FALSE else "disabled",
        allow_network=network_allowed,
        allow_upload=network_allowed and allow_upload,
        allow_paid=False,
    )


def resolve_config(request: PrepareRequest) -> ResolvedConfig:
    """Resolve user request/config omissions into concrete default/auto policy.

    This first implementation intentionally supports built-in defaults and CLI/request
    overrides. Config-file loading can layer on top without changing downstream APIs.
    """

    del request.config_path
    return ResolvedConfig(
        runtime=RuntimeConfig(
            cache_dir=request.cache_dir,
            keep_temp=request.keep_temp,
            offline=request.offline,
            auto=request.auto,
        ),
        source=SourceConfig(preferred_language=request.language),
        transforms=TransformConfig(
            asr=_policy(None, global_auto=request.auto, offline=request.offline),
            visual_context=_policy(
                request.visual_context, global_auto=request.auto, offline=request.offline
            ),
            cleanup=_policy(request.cleanup, global_auto=request.auto, offline=request.offline),
            chapters=_policy(request.chapters, global_auto=request.auto, offline=request.offline),
        ),
        output=OutputConfig(
            formats=request.formats,
            chunk_max_chars=request.chunk_max_chars,
            chunk_max_seconds=request.chunk_max_seconds,
        ),
    )
