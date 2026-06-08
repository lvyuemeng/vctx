from __future__ import annotations

from vctx.app.errors import UnsupportedSourceError
from vctx.sources.base import SourceAdapter
from vctx.sources.local_file_source import LocalFileSourceAdapter


def detect_source_adapter(value: str) -> SourceAdapter:
    adapters: list[SourceAdapter] = [LocalFileSourceAdapter()]
    for adapter in adapters:
        if adapter.can_handle(value):
            return adapter
    raise UnsupportedSourceError(f"unsupported source: {value}")
