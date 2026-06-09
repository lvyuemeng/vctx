from __future__ import annotations

import importlib.util

from vctx.app.config import CapabilityPolicy
from vctx.transforms.visual_planning import VisualOperation, baseline_visual_operations

RAPIDOCR_PROVIDER_ID = "rapidocr-onnxruntime"


def discover_visual_operations(policy: CapabilityPolicy) -> list[VisualOperation]:
    operations = baseline_visual_operations()
    if policy.enabled == "false":
        return operations
    if policy.route in {"auto", "default", "local"} and rapidocr_available():
        operations.append(
            VisualOperation(
                name="ocr",
                route="local",
                provider_id=RAPIDOCR_PROVIDER_ID,
            )
        )
    return operations


def rapidocr_available() -> bool:
    return importlib.util.find_spec("rapidocr_onnxruntime") is not None
