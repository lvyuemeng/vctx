from __future__ import annotations

import importlib
from typing import Any

from vctx.models.visual import FrameAsset


class OcrExecutionError(RuntimeError):
    pass


class RapidOcrAdapter:
    provider_id = "rapidocr-onnxruntime"

    def __init__(self) -> None:
        self._engine: Any | None = None

    def extract_text(self, frame: FrameAsset) -> str:
        try:
            result = self._rapidocr()(str(frame.path))
        except Exception as exc:  # pragma: no cover - adapter boundary
            raise OcrExecutionError(f"rapidocr failed for {frame.path}: {exc}") from exc
        return _rapidocr_text(result)

    def _rapidocr(self) -> Any:
        if self._engine is None:
            try:
                module = importlib.import_module("rapidocr_onnxruntime")
                rapid_ocr = module.RapidOCR
            except ImportError as exc:
                raise OcrExecutionError(
                    "rapidocr-onnxruntime is not installed; install vctx[visual]"
                ) from exc
            self._engine = rapid_ocr()
        return self._engine


def _rapidocr_text(result: Any) -> str:
    blocks = _rapidocr_blocks(result)
    texts: list[str] = []
    for block in blocks:
        text = _block_text(block)
        if text:
            texts.append(text)
    return "\n".join(texts).strip()


def _rapidocr_blocks(result: Any) -> list[Any]:
    if result is None:
        return []
    if isinstance(result, tuple) and result:
        first = result[0]
        return first if isinstance(first, list) else []
    if isinstance(result, list):
        return result
    return []


def _block_text(block: Any) -> str | None:
    if isinstance(block, dict):
        value = block.get("text")
        return value if isinstance(value, str) else None
    if isinstance(block, (list, tuple)):
        for item in block:
            if isinstance(item, str):
                return item
    text = getattr(block, "text", None)
    return text if isinstance(text, str) else None
