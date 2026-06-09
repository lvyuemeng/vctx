from __future__ import annotations

from pathlib import Path

from platformdirs import user_cache_path
from pydantic import BaseModel


class Cache(BaseModel):
    root: Path

    def path_for(self, key: str) -> Path:
        return self.root / key


def build_cache(cache_dir: Path | None) -> Cache:
    root = cache_dir or user_cache_path("vctx", appauthor=False)
    root.mkdir(parents=True, exist_ok=True)
    return Cache(root=root)
