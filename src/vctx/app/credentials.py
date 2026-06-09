from __future__ import annotations

import os
from pathlib import Path


class CredentialError(RuntimeError):
    pass


def resolve_env_credential(name: str | None, *, env_files: list[Path]) -> str:
    if not name:
        raise CredentialError("ASR instance is missing api_key_env")
    value = os.environ.get(name)
    if value:
        return value
    for env_file in env_files:
        dotenv_value = _read_dotenv_value(env_file, name)
        if dotenv_value:
            return dotenv_value
    searched = ", ".join(str(path) for path in env_files) or "no env files"
    raise CredentialError(f"missing credential {name}; searched shell environment and {searched}")


def _read_dotenv_value(path: Path, name: str) -> str | None:
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != name:
            continue
        return _strip_dotenv_quotes(value.strip())
    return None


def _strip_dotenv_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
