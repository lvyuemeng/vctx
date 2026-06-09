from __future__ import annotations

import importlib.util

from vctx.app.config import CapabilityEnabled, CapabilityPolicy, ProviderConfig
from vctx.transforms.visual_planning import VisualOperation, baseline_visual_operations

RAPIDOCR_PROVIDER_ID = "rapidocr-onnxruntime"


def discover_visual_operations(
    policy: CapabilityPolicy,
    *,
    vision_providers: dict[str, ProviderConfig] | None = None,
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


def rapidocr_available() -> bool:
    return importlib.util.find_spec("rapidocr_onnxruntime") is not None
