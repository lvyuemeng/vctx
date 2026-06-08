from __future__ import annotations

from pydantic import BaseModel


def model_to_json(model: BaseModel) -> str:
    return model.model_dump_json(indent=2) + "\n"
