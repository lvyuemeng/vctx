from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from vctx.cli import app

runner = CliRunner()


def test_prepare_local_srt_writes_context_pack(tmp_path: Path) -> None:
    source = tmp_path / "lecture.srt"
    source.write_text(
        """1
00:00:00,000 --> 00:00:02,000
Hello <b>world</b>.

2
00:00:02,000 --> 00:00:05,000
This is a second caption.
""",
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    result = runner.invoke(app, ["prepare", str(source), "--out", str(out_dir)])

    assert result.exit_code == 0, result.output
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "metadata.json").exists()
    assert (out_dir / "transcript.raw.json").exists()
    assert (out_dir / "transcript.clean.json").exists()
    assert (out_dir / "chunks.json").exists()
    assert (out_dir / "context.md").exists()
    assert (out_dir / "readable.md").exists()
    assert (out_dir / "transcript.md").exists()

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "ok"
    assert manifest["input"] == str(source)
    assert {artifact["path"] for artifact in manifest["artifacts"]} >= {
        "metadata.json",
        "context.md",
        "readable.md",
    }

    clean = json.loads((out_dir / "transcript.clean.json").read_text(encoding="utf-8"))
    assert clean["segments"][0]["text"] == "Hello world."

    context = (out_dir / "context.md").read_text(encoding="utf-8")
    assert "# Agent Context Pack" in context
    assert '<chunk id="chunk_0001" start="00:00:00" end="00:00:05">' in context
    assert "Hello world." in context


def test_prepare_refuses_existing_output_without_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "lecture.srt"
    source.write_text(
        """1
00:00:00,000 --> 00:00:01,000
hello
""",
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "existing.txt").write_text("keep", encoding="utf-8")

    result = runner.invoke(app, ["prepare", str(source), "--out", str(out_dir)])

    assert result.exit_code == 5
    assert "output directory already exists" in result.output
    assert (out_dir / "existing.txt").read_text(encoding="utf-8") == "keep"
