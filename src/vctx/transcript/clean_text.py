from __future__ import annotations

import re

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def strip_subtitle_markup(text: str) -> str:
    return _TAG_RE.sub("", text)


def normalize_whitespace(text: str) -> str:
    return _SPACE_RE.sub(" ", text).strip()


def clean_subtitle_text(text: str) -> str:
    return normalize_whitespace(strip_subtitle_markup(text))
