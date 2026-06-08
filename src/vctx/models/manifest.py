from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from vctx.models.artifacts import ArtifactKind

StepStatus = Literal["ok", "skipped", "warning", "error"]
RunStatus = Literal["ok", "partial", "error"]


class ManifestStep(BaseModel):
    name: str
    status: StepStatus
    detail: str | None = None


class ArtifactRef(BaseModel):
    kind: ArtifactKind
    path: str
    media_type: str


class Manifest(BaseModel):
    schema_version: str = "0.1"
    tool: str = "vctx"
    tool_version: str
    status: RunStatus
    input: str
    created_at: str
    artifacts: list[ArtifactRef]
    steps: list[ManifestStep]
    warnings: list[str] = []


class ManifestBuilder:
    def __init__(self, input: str, tool_version: str) -> None:
        self.input = input
        self.tool_version = tool_version
        self.steps: list[ManifestStep] = []
        self.warnings: list[str] = []

    @classmethod
    def start(cls, input: str, tool_version: str) -> ManifestBuilder:
        return cls(input=input, tool_version=tool_version)

    def add_step(self, name: str, status: StepStatus, detail: str | None = None) -> None:
        self.steps.append(ManifestStep(name=name, status=status, detail=detail))

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def finish(self, status: RunStatus, artifacts: list[ArtifactRef]) -> Manifest:
        return Manifest(
            tool_version=self.tool_version,
            status=status,
            input=self.input,
            created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            artifacts=artifacts,
            steps=self.steps,
            warnings=self.warnings,
        )
