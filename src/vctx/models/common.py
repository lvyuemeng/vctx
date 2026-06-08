from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TimeRange(BaseModel):
    start: float
    end: float | None = None


class SourceRef(BaseModel):
    kind: Literal["url", "file"]
    value: str
