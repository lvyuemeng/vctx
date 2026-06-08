from __future__ import annotations


def approximate_token_count(text: str) -> int:
    return max(1, len(text) // 4)
