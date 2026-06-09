from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from vctx.models.common import SourceRef


class MediaAsset(BaseModel):
    id: str
    source: SourceRef
    local_path: Path
    media_type: Literal["audio", "video", "unknown"] = "unknown"
    container: str | None = None
    duration_seconds: float | None = None
    language_hint: str | None = None
    provider: str | None = None
