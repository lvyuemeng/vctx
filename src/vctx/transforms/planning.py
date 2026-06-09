from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from vctx.app.config import CapabilityEnabled, CapabilityPolicy

SelectedRoute = Literal[
    "skipped",
    "deterministic",
    "local",
    "free-online",
    "configured-online",
    "unavailable",
]
CapabilityName = Literal["asr", "visual_context", "cleanup", "chapters"]
VisualNeed = Literal["none", "ocr", "description"]
ProviderCostMode = Literal["free", "paid", "local", "unknown"]


class TransformEvidence(BaseModel):
    capability: CapabilityName
    selected_route: SelectedRoute
    provider_id: str | None = None
    model_id: str | None = None
    requires_user_config: bool = False
    uploaded: bool = False
    cost_may_apply: bool = False
    deterministic: bool = False
    source_artifacts: list[str] = []
    output_artifacts: list[str] = []
    reason: str
    warnings: list[str] = []


class RoutePlan(BaseModel):
    capability: CapabilityName
    selected: SelectedRoute
    provider_id: str | None = None
    model_id: str | None = None
    reason: str
    requirements: list[str] = []
    warnings: list[str] = []
    evidence_seed: TransformEvidence


class SourceState(BaseModel):
    has_transcript: bool = False
    has_media: bool = False
    visual_need: VisualNeed = "none"


class TransformEnvironment(BaseModel):
    installed_asr: bool = False
    installed_ocr: bool = False
    installed_online_ai: bool = False
    network_available: bool = True
    offline: bool = False
    configured_asr: bool = False
    configured_asr_provider_id: str | None = None
    configured_asr_model_id: str | None = None
    configured_asr_cost_mode: ProviderCostMode = "unknown"
    configured_ocr: bool = False
    configured_vision: bool = False
    configured_text: bool = False
    free_online_asr: bool = False
    free_online_ocr: bool = False
    free_online_vision: bool = False
    free_online_text: bool = False


def _plan(
    *,
    capability: CapabilityName,
    selected: SelectedRoute,
    reason: str,
    provider_id: str | None = None,
    model_id: str | None = None,
    requirements: list[str] | None = None,
    warnings: list[str] | None = None,
    requires_user_config: bool = False,
    uploaded: bool = False,
    cost_may_apply: bool = False,
    deterministic: bool = False,
) -> RoutePlan:
    warnings = warnings or []
    return RoutePlan(
        capability=capability,
        selected=selected,
        provider_id=provider_id,
        model_id=model_id,
        reason=reason,
        requirements=requirements or [],
        warnings=warnings,
        evidence_seed=TransformEvidence(
            capability=capability,
            selected_route=selected,
            provider_id=provider_id,
            model_id=model_id,
            requires_user_config=requires_user_config,
            uploaded=uploaded,
            cost_may_apply=cost_may_apply,
            deterministic=deterministic,
            reason=reason,
            warnings=warnings,
        ),
    )


def _disabled(policy: CapabilityPolicy) -> bool:
    return policy.enabled == CapabilityEnabled.FALSE or policy.route == "disabled"


def _online_allowed(policy: CapabilityPolicy, environment: TransformEnvironment) -> bool:
    return policy.allow_network and environment.network_available and not environment.offline


def plan_asr(
    policy: CapabilityPolicy,
    environment: TransformEnvironment,
    source_state: SourceState,
) -> RoutePlan:
    if source_state.has_transcript:
        return _plan(
            capability="asr",
            selected="skipped",
            reason="transcript already available",
            deterministic=True,
        )
    if _disabled(policy):
        return _plan(capability="asr", selected="skipped", reason="ASR disabled by policy")
    if not source_state.has_media:
        return _plan(
            capability="asr",
            selected="unavailable",
            reason="No transcript found and no media asset is available for ASR.",
            requirements=["media asset"],
        )
    if environment.installed_asr:
        return _plan(
            capability="asr",
            selected="local",
            provider_id="faster-whisper",
            model_id="small/base",
            reason="default local ASR route available",
        )
    if _online_allowed(policy, environment) and environment.free_online_asr:
        return _plan(
            capability="asr",
            selected="free-online",
            provider_id="free-online-asr",
            reason="free zero-config online ASR route available",
            uploaded=True,
        )
    if _online_allowed(policy, environment) and policy.allow_upload and environment.configured_asr:
        explicit_instance = policy.instance is not None
        if environment.configured_asr_cost_mode == "paid" and not (
            policy.allow_paid or explicit_instance
        ):
            return _plan(
                capability="asr",
                selected="unavailable",
                reason="configured paid ASR provider requires allow_paid=true",
                requirements=["set allow_paid=true or choose a free/local route"],
                requires_user_config=True,
            )
        provider_id = (
            environment.configured_asr_provider_id
            or policy.instance
            or policy.preferred_provider
            or "default-asr"
        )
        model_id = policy.model or environment.configured_asr_model_id
        return _plan(
            capability="asr",
            selected="configured-online",
            provider_id=provider_id,
            model_id=model_id,
            reason="configured online ASR route available",
            requires_user_config=True,
            uploaded=True,
            cost_may_apply=environment.configured_asr_cost_mode == "paid" or policy.allow_paid,
        )
    return _plan(
        capability="asr",
        selected="unavailable",
        reason=(
            "No transcript found, ASR extra not installed, no free-online ASR route registered, "
            "and no configured ASR provider."
        ),
        requirements=["install ASR extra", "configure ASR provider", "provide transcript file"],
    )


def plan_visual_context(
    policy: CapabilityPolicy,
    environment: TransformEnvironment,
    source_state: SourceState,
) -> RoutePlan:
    if _disabled(policy) or source_state.visual_need == "none":
        return _plan(
            capability="visual_context",
            selected="skipped",
            reason="visual context not requested or not useful",
        )
    if not source_state.has_media:
        return _plan(
            capability="visual_context",
            selected="unavailable",
            reason="visual context needs media or frame assets",
            requirements=["media/frame assets"],
        )

    if source_state.visual_need == "description":
        if _online_allowed(policy, environment) and environment.free_online_vision:
            return _plan(
                capability="visual_context",
                selected="free-online",
                provider_id="free-online-vision",
                reason="free zero-config online visual description route is preferred",
                uploaded=True,
                warnings=["Visual descriptions are generated model output, not source text."],
            )
        if (
            _online_allowed(policy, environment)
            and policy.allow_upload
            and environment.configured_vision
        ):
            return _plan(
                capability="visual_context",
                selected="configured-online",
                provider_id="default-vision",
                reason="configured online visual description route available",
                requires_user_config=True,
                uploaded=True,
                cost_may_apply=policy.allow_paid,
                warnings=["Visual descriptions are generated model output, not source text."],
            )

    if environment.installed_ocr:
        return _plan(
            capability="visual_context",
            selected="local",
            provider_id="rapidocr-onnxruntime",
            reason="default local OCR route available",
        )
    if _online_allowed(policy, environment) and environment.free_online_ocr:
        return _plan(
            capability="visual_context",
            selected="free-online",
            provider_id="free-online-ocr",
            reason="free zero-config online OCR route available",
            uploaded=True,
        )
    if _online_allowed(policy, environment) and policy.allow_upload and environment.configured_ocr:
        return _plan(
            capability="visual_context",
            selected="configured-online",
            provider_id="default-ocr",
            reason="configured online OCR route available",
            requires_user_config=True,
            uploaded=True,
            cost_may_apply=policy.allow_paid,
        )
    return _plan(
        capability="visual_context",
        selected="unavailable",
        reason="No suitable visual-context route is available.",
    )


def plan_cleanup(policy: CapabilityPolicy, environment: TransformEnvironment) -> RoutePlan:
    if _disabled(policy):
        return _plan(capability="cleanup", selected="skipped", reason="model cleanup disabled")
    if _online_allowed(policy, environment) and environment.free_online_text:
        return _plan(
            capability="cleanup",
            selected="free-online",
            provider_id="free-online-text",
            reason="safe free zero-config cleanup route available",
            uploaded=True,
        )
    if _online_allowed(policy, environment) and environment.configured_text:
        return _plan(
            capability="cleanup",
            selected="configured-online",
            provider_id="default-text",
            reason="configured cleanup route available",
            requires_user_config=True,
            uploaded=True,
            cost_may_apply=policy.allow_paid,
        )
    return _plan(
        capability="cleanup",
        selected="skipped",
        reason="deterministic cleanup only; no safe model cleanup route available",
        deterministic=True,
    )


def plan_chapters(policy: CapabilityPolicy, environment: TransformEnvironment) -> RoutePlan:
    if _disabled(policy):
        return _plan(capability="chapters", selected="skipped", reason="chapters disabled")
    if _online_allowed(policy, environment) and environment.free_online_text:
        return _plan(
            capability="chapters",
            selected="free-online",
            provider_id="free-online-text",
            reason="free zero-config chapter candidate route available",
            uploaded=True,
        )
    if _online_allowed(policy, environment) and environment.configured_text:
        return _plan(
            capability="chapters",
            selected="configured-online",
            provider_id="default-text",
            reason="configured chapter candidate route available",
            requires_user_config=True,
            uploaded=True,
            cost_may_apply=policy.allow_paid,
        )
    return _plan(
        capability="chapters",
        selected="skipped",
        reason="deterministic chapter candidates only; no model route available",
        deterministic=True,
    )
