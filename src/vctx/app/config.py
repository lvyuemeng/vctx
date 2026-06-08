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


class WorkflowProfile(StrEnum):
    DEFAULT = "default"
    TRANSCRIPT = "transcript"
    VISUAL = "visual"
    FULL = "full"
    METADATA = "metadata"


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
    workflow: WorkflowProfile = WorkflowProfile.DEFAULT
    offline: bool = False
    config_path: Path | None = None


class RuntimeConfig(BaseModel):
    cache_dir: Path | None
    keep_temp: bool
    offline: bool
    workflow: WorkflowProfile


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


def resolve_config(request: PrepareRequest) -> ResolvedConfig:
    """Resolve user request/config omissions into concrete default/auto policy.

    This first implementation intentionally supports built-in defaults and CLI/request
    overrides. Config-file loading can layer on top without changing downstream APIs.
    """

    del request.config_path
    asr, visual_context, cleanup, chapters = _workflow_capabilities(request.workflow)
    return ResolvedConfig(
        runtime=RuntimeConfig(
            cache_dir=request.cache_dir,
            keep_temp=request.keep_temp,
            offline=request.offline,
            workflow=request.workflow,
        ),
        source=SourceConfig(preferred_language=request.language),
        transforms=TransformConfig(
            asr=_policy(asr, offline=request.offline),
            visual_context=_policy(visual_context, offline=request.offline),
            cleanup=_policy(cleanup, offline=request.offline),
            chapters=_policy(chapters, offline=request.offline),
        ),
        output=OutputConfig(
            formats=request.formats,
            chunk_max_chars=request.chunk_max_chars,
            chunk_max_seconds=request.chunk_max_seconds,
        ),
    )
