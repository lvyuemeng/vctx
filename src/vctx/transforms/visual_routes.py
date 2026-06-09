from __future__ import annotations

import importlib.util
import os
from collections.abc import Mapping

from vctx.app.config import CapabilityEnabled, CapabilityPolicy, ProviderConfig
from vctx.transforms.model_resolution import (
    ModelCapability,
    OpenRouterModel,
    ResolvedModelRoute,
    resolve_model_ref,
)
from vctx.transforms.visual_planning import VisualOperation, baseline_visual_operations

RAPIDOCR_PROVIDER_ID = "rapidocr-onnxruntime"


def discover_visual_operations(
    policy: CapabilityPolicy,
    *,
    vision_providers: dict[str, ProviderConfig] | None = None,
    env: Mapping[str, str] | None = None,
    openrouter_models: list[OpenRouterModel] | None = None,
) -> list[VisualOperation]:
    operations = baseline_visual_operations()
    if policy.enabled == CapabilityEnabled.FALSE:
        return operations
    if policy.route in {"auto", "default", "local"} and rapidocr_available():
        operations.append(
            VisualOperation(
                name="ocr",
                route="local",
                provider_id=RAPIDOCR_PROVIDER_ID,
            )
        )
    vision_provider = _configured_vision_provider(policy, vision_providers or {})
    if vision_provider is not None:
        provider_id, _provider = vision_provider
        route = "free-online" if policy.route == "free-online" else "configured-online"
        operations.append(
            VisualOperation(
                name="describe",
                route=route,
                provider_id=provider_id,
            )
        )
        return operations

    resolved = _resolved_visual_model(policy, env=env, openrouter_models=openrouter_models)
    if resolved is not None:
        operations.append(_resolved_describe_operation(resolved))
    return operations


def _configured_vision_provider(
    policy: CapabilityPolicy,
    providers: dict[str, ProviderConfig],
) -> tuple[str, ProviderConfig] | None:
    if not policy.allow_network or not policy.allow_upload:
        return None
    if policy.route not in {"auto", "default", "free-online", "configured-online"}:
        return None
    if policy.preferred_provider is not None:
        provider = providers.get(policy.preferred_provider)
        if provider is not None and _vision_provider_allowed(policy, provider):
            return policy.preferred_provider, provider
        return None
    for provider_id, provider in providers.items():
        if _vision_provider_allowed(policy, provider):
            return provider_id, provider
    return None


def _vision_provider_allowed(policy: CapabilityPolicy, provider: ProviderConfig) -> bool:
    if provider.type != "openai-compatible-vision":
        return False
    if provider.cost_mode == "paid" and not policy.allow_paid:
        return False
    if policy.route == "free-online" and provider.cost_mode != "free":
        return False
    return provider.base_url is not None and provider.model is not None


def _resolved_visual_model(
    policy: CapabilityPolicy,
    *,
    env: Mapping[str, str] | None,
    openrouter_models: list[OpenRouterModel] | None,
) -> ResolvedModelRoute | None:
    if not policy.allow_network or not policy.allow_upload:
        return None
    if policy.route not in {"auto", "default", "free-online", "configured-online"}:
        return None
    if policy.model is None and openrouter_models is None:
        return None
    resolved = resolve_model_ref(
        policy.model,
        capability=ModelCapability.VISION_DESCRIPTION,
        env=env or os.environ,
        openrouter_models=openrouter_models,
    )
    if not resolved.available:
        return None
    if resolved.provider != "openrouter":
        return None
    if resolved.cost == "paid" and not policy.allow_paid:
        return None
    if policy.route == "free-online" and resolved.cost != "free":
        return None
    if resolved.upload != "required":
        return None
    return resolved


def _resolved_describe_operation(resolved: ResolvedModelRoute) -> VisualOperation:
    provider_id = f"{resolved.provider}:{resolved.model}"
    route = "free-online" if resolved.cost == "free" else "configured-online"
    return VisualOperation(
        name="describe",
        route=route,
        provider_id=provider_id,
        params={
            "provider_type": "openai-compatible-vision",
            "base_url": resolved.base_url,
            "api_key_env": resolved.api_key_env,
            "model": resolved.model,
            "cost": resolved.cost,
        },
    )


def rapidocr_available() -> bool:
    return importlib.util.find_spec("rapidocr_onnxruntime") is not None
