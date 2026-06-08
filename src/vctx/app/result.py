from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from vctx.models.artifacts import ArtifactKind
from vctx.models.manifest import ArtifactRef, Manifest


class PrepareResult(BaseModel):
    out_dir: Path
    manifest: Manifest
    artifacts: list[ArtifactRef]

    def artifact_path(self, kind: ArtifactKind) -> Path | None:
        for artifact in self.artifacts:
            if artifact.kind == kind:
                return self.out_dir / artifact.path
        return None
