from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from vctx.cli import app
from vctx.models.transcript import TranscriptPayload, TranscriptProvenance

runner = CliRunner()


def test_prepare_visual_workflow_writes_capture_records_and_frame_refs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import vctx.transforms.asr as asr_module
    import vctx.transforms.visual_frames as visual_frames_module
    from vctx.models.visual import FrameAsset
    from vctx.transforms.visual_planning import Evidence

    media = tmp_path / "lecture.mp4"
    media.write_bytes(b"fake mp4 bytes")
    config = tmp_path / "vctx.toml"
    config.write_text(
        """
[transforms.asr]
instance = "local-default"

[instances.asr.local-default]
type = "local-faster-whisper"
model = "tiny"
cache = "persistent"
""".strip(),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    def fake_transcribe(self: object, media_asset: object) -> TranscriptPayload:
        del self, media_asset
        return TranscriptPayload(
            text="WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nA lecture with slides.\n",
            format="vtt",
            provenance=TranscriptProvenance(
                method="asr",
                language="en",
                format="vtt",
                provider="faster-whisper",
            ),
        )

    def fake_extract_frames(
        media_asset: object,
        sample_action: object,
        frames_dir: Path,
    ) -> list[FrameAsset]:
        del media_asset, sample_action
        frames_dir.mkdir(parents=True, exist_ok=True)
        frame_path = frames_dir / "frame-0001.jpg"
        frame_path.write_bytes(b"fake jpg bytes")
        return [
            FrameAsset(
                id="frame-0001",
                timestamp_seconds=1.0,
                path=frame_path,
                source="cover",
                evidence=[Evidence(kind="probe", name="test-frame", weight=1.0)],
            )
        ]

    monkeypatch.setattr(asr_module.FasterWhisperAsrAdapter, "transcribe", fake_transcribe)
    monkeypatch.setattr(visual_frames_module, "extract_frames", fake_extract_frames)

    result = runner.invoke(
        app,
        [
            "prepare",
            str(media),
            "--out",
            str(out_dir),
            "--config",
            str(config),
            "--workflow",
            "visual",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (out_dir / "visual_records.json").exists()
    assert (out_dir / "visual" / "frames" / "frame-0001.jpg").exists()

    visual_records = json.loads(
        (out_dir / "visual_records.json").read_text(encoding="utf-8")
    )
    assert visual_records["records"][0]["kind"] == "capture"
    assert visual_records["records"][0]["artifact_path"] == "visual/frames/frame-0001.jpg"

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "ok"
    assert _step_status(manifest, "transform.visual_plan") == "ok"
    assert _step_status(manifest, "transform.visual_capture") == "ok"
    assert {artifact["path"] for artifact in manifest["artifacts"]} >= {
        "visual_records.json",
        "visual/frames/frame-0001.jpg",
    }

    context = (out_dir / "context.md").read_text(encoding="utf-8")
    assert "## Visual records" in context
    assert "visual/frames/frame-0001.jpg" in context


def _step_status(manifest: dict[str, Any], name: str) -> str:
    steps = manifest["steps"]
    assert isinstance(steps, list)
    for raw_step in steps:
        assert isinstance(raw_step, dict)
        step = cast(dict[str, Any], raw_step)
        if step["name"] == name:
            status = step["status"]
            assert isinstance(status, str)
            return status
    raise AssertionError(f"missing manifest step: {name}")
