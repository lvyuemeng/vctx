from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def vctx_version() -> str:
    try:
        return version("vctx")
    except PackageNotFoundError:
        return "0.0.0"
