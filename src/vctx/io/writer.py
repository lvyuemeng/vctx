from __future__ import annotations

from pathlib import Path

from vctx.app.errors import OutputExistsError
from vctx.io.json_dump import model_to_json
from vctx.models.artifacts import Artifact, ArtifactBundle
from vctx.models.manifest import ArtifactRef, Manifest


def validate_output_policy(out_dir: Path, *, overwrite: bool) -> None:
    if out_dir.exists() and any(out_dir.iterdir()) and not overwrite:
        raise OutputExistsError(f"output directory already exists: {out_dir}")


def write_artifact_bundle(out_dir: Path, bundle: ArtifactBundle) -> list[ArtifactRef]:
    out_dir.mkdir(parents=True, exist_ok=True)
    refs: list[ArtifactRef] = []
    for artifact in bundle.artifacts:
        refs.append(write_artifact(out_dir, artifact))
    return refs


def write_artifact(out_dir: Path, artifact: Artifact) -> ArtifactRef:
    final_path = out_dir / artifact.name
    temp_path = out_dir / f".{artifact.name}.tmp"
    temp_path.write_text(artifact.content, encoding="utf-8")
    temp_path.replace(final_path)
    return ArtifactRef(kind=artifact.kind, path=artifact.name, media_type=artifact.media_type)


def write_manifest(out_dir: Path, manifest: Manifest) -> ArtifactRef:
    return write_artifact(
        out_dir,
        Artifact(
            name="manifest.json",
            kind="manifest",
            media_type="application/json",
            content=model_to_json(manifest),
        ),
    )
