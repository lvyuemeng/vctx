from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ModelProvider = Literal["none", "openrouter", "local", "hf", "alias"]
ModelCost = Literal["free", "paid", "local", "unknown"]
ModelUpload = Literal["none", "required"]

OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"


class ModelCapability(StrEnum):
    ESSENTIAL_CASES = "essential_cases"
    VISION_DESCRIPTION = "vision_description"
    ASR = "asr"
    OCR = "ocr"
    CLEANUP = "cleanup"
    CHAPTERS = "chapters"


class ModelRef(BaseModel):
    prefix: Literal["auto", "none", "openrouter", "local", "hf", "alias"]
    value: str | None = None


class ResolvedModelRoute(BaseModel):
    ref: ModelRef
    provider: ModelProvider
    model: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    cost: ModelCost = "unknown"
    upload: ModelUpload = "none"
    available: bool = False
    reason: str = ""


class OpenRouterModelArchitecture(BaseModel):
    input_modalities: list[str] = Field(default_factory=list)
    output_modalities: list[str] = Field(default_factory=list)


class OpenRouterModelPricing(BaseModel):
    prompt: str = ""
    completion: str = ""


class OpenRouterModel(BaseModel):
    id: str
    architecture: OpenRouterModelArchitecture = Field(
        default_factory=OpenRouterModelArchitecture
    )
    pricing: OpenRouterModelPricing = Field(default_factory=OpenRouterModelPricing)
    context_length: int | None = None


def parse_model_ref(value: str | None) -> ModelRef:
    if value is None or value == "auto":
        return ModelRef(prefix="auto")
    if value == "none":
        return ModelRef(prefix="none")
    prefix, separator, rest = value.partition(":")
    if separator:
        if prefix == "openrouter":
            return ModelRef(prefix="openrouter", value=rest)
        if prefix == "local":
            return ModelRef(prefix="local", value=rest)
        if prefix == "hf":
            return ModelRef(prefix="hf", value=rest)
        if prefix == "alias":
            return ModelRef(prefix="alias", value=rest)
    if _looks_like_path_value(value):
        return ModelRef(prefix="local", value=value)
    return ModelRef(prefix="alias", value=value)


def resolve_model_ref(
    value: str | None,
    *,
    capability: ModelCapability,
    env: Mapping[str, str],
    base_dir: Path | None = None,
    openrouter_models: list[OpenRouterModel] | None = None,
) -> ResolvedModelRoute:
    ref = parse_model_ref(value)
    if ref.prefix == "none":
        return ResolvedModelRoute(
            ref=ref,
            provider="none",
            available=False,
            reason="model-mediated transform disabled",
        )
    if ref.prefix == "auto":
        return _resolve_auto(
            capability=capability,
            env=env,
            openrouter_models=openrouter_models or [],
        )
    if ref.prefix == "openrouter":
        return _resolve_openrouter(ref, capability=capability, env=env)
    if ref.prefix == "local":
        return _resolve_local(ref, base_dir=base_dir)
    if ref.prefix == "hf":
        return ResolvedModelRoute(
            ref=ref,
            provider="hf",
            model=ref.value,
            cost="local",
            upload="none",
            available=True,
            reason="Hugging Face model id uses managed local cache when runtime exists",
        )
    return ResolvedModelRoute(
        ref=ref,
        provider="alias",
        model=ref.value,
        available=False,
        reason="model alias resolution is not implemented",
    )


def choose_openrouter_free_model(
    models: list[OpenRouterModel], *, capability: ModelCapability
) -> OpenRouterModel | None:
    for model in models:
        if _is_free(model) and _supports_capability(model, capability):
            return model
    return None


def _resolve_auto(
    *,
    capability: ModelCapability,
    env: Mapping[str, str],
    openrouter_models: list[OpenRouterModel],
) -> ResolvedModelRoute:
    if OPENROUTER_API_KEY_ENV not in env:
        return ResolvedModelRoute(
            ref=ModelRef(prefix="auto"),
            provider="none",
            available=False,
            reason=(
                f"{OPENROUTER_API_KEY_ENV} is not set; "
                "using deterministic fallback when available"
            ),
        )
    selected = choose_openrouter_free_model(openrouter_models, capability=capability)
    if selected is None:
        return ResolvedModelRoute(
            ref=ModelRef(prefix="auto"),
            provider="none",
            available=False,
            reason="no free OpenRouter model supports the requested capability",
        )
    return _openrouter_route(ModelRef(prefix="openrouter", value=selected.id), selected.id)


def _resolve_openrouter(
    ref: ModelRef, *, capability: ModelCapability, env: Mapping[str, str]
) -> ResolvedModelRoute:
    if ref.value is None or ref.value == "":
        return ResolvedModelRoute(
            ref=ref,
            provider="openrouter",
            available=False,
            reason="openrouter model reference is missing a model id",
        )
    if OPENROUTER_API_KEY_ENV not in env:
        return ResolvedModelRoute(
            ref=ref,
            provider="openrouter",
            model=ref.value,
            base_url=OPENROUTER_CHAT_COMPLETIONS_URL,
            api_key_env=OPENROUTER_API_KEY_ENV,
            cost=_openrouter_cost_from_id(ref.value),
            upload=_upload_for_capability(capability),
            available=False,
            reason=f"{OPENROUTER_API_KEY_ENV} is not set",
        )
    return _openrouter_route(ref, ref.value, upload=_upload_for_capability(capability))


def _openrouter_route(
    ref: ModelRef, model: str, *, upload: ModelUpload = "required"
) -> ResolvedModelRoute:
    return ResolvedModelRoute(
        ref=ref,
        provider="openrouter",
        model=model,
        base_url=OPENROUTER_CHAT_COMPLETIONS_URL,
        api_key_env=OPENROUTER_API_KEY_ENV,
        cost=_openrouter_cost_from_id(model),
        upload=upload,
        available=True,
        reason="resolved from OpenRouter model reference",
    )


def _resolve_local(ref: ModelRef, *, base_dir: Path | None) -> ResolvedModelRoute:
    model = ref.value or ""
    path = Path(model)
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    normalized = str(path) if model else model
    return ResolvedModelRoute(
        ref=ModelRef(prefix="local", value=normalized),
        provider="local",
        model=normalized,
        cost="local",
        upload="none",
        available=True,
        reason="resolved from local model reference",
    )


def _is_free(model: OpenRouterModel) -> bool:
    return model.id.endswith(":free") or (
        _is_zero_price(model.pricing.prompt) and _is_zero_price(model.pricing.completion)
    )


def _is_zero_price(value: str) -> bool:
    try:
        return float(value) == 0.0
    except ValueError:
        return False


def _supports_capability(model: OpenRouterModel, capability: ModelCapability) -> bool:
    inputs = set(model.architecture.input_modalities)
    outputs = set(model.architecture.output_modalities)
    if "text" not in outputs:
        return False
    if capability == ModelCapability.VISION_DESCRIPTION:
        return {"text", "image"}.issubset(inputs)
    if capability in {
        ModelCapability.ESSENTIAL_CASES,
        ModelCapability.CLEANUP,
        ModelCapability.CHAPTERS,
    }:
        return "text" in inputs
    return False


def _upload_for_capability(capability: ModelCapability) -> ModelUpload:
    if capability in {ModelCapability.VISION_DESCRIPTION, ModelCapability.ASR}:
        return "required"
    if capability in {
        ModelCapability.ESSENTIAL_CASES,
        ModelCapability.CLEANUP,
        ModelCapability.CHAPTERS,
    }:
        return "required"
    return "none"


def _openrouter_cost_from_id(model: str) -> ModelCost:
    return "free" if model.endswith(":free") else "unknown"


def _looks_like_path_value(value: str) -> bool:
    path = Path(value)
    return path.is_absolute() or value.startswith(".") or any(
        separator in value for separator in ("/", "\\")
    )
