from __future__ import annotations

import subprocess
from pathlib import Path

from vctx.models.media import MediaAsset
from vctx.models.visual import FrameAsset
from vctx.transforms.visual_planning import AcquisitionAction, Evidence


def extract_frames(
    media_asset: MediaAsset,
    sample_action: AcquisitionAction,
    frames_dir: Path,
) -> list[FrameAsset]:
    """Extract deterministic frame assets for the current visual capture slice."""

    frames_dir.mkdir(parents=True, exist_ok=True)
    strategy = str(sample_action.params.get("strategy", "cover"))
    budget = int(sample_action.params.get("budget", 1))
    if strategy == "cover" or budget <= 1:
        return [_extract_cover_frame(media_asset, frames_dir)]
    return [_extract_cover_frame(media_asset, frames_dir)]


def _extract_cover_frame(media_asset: MediaAsset, frames_dir: Path) -> FrameAsset:
    timestamp = _cover_timestamp(media_asset.duration_seconds)
    frame_path = frames_dir / "frame-0001.jpg"
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        str(media_asset.local_path),
        "-frames:v",
        "1",
        "-q:v",
        "3",
        str(frame_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"failed to extract cover frame with ffmpeg: {exc}") from exc
    return FrameAsset(
        id="frame-0001",
        timestamp_seconds=timestamp,
        path=frame_path,
        source="cover",
        evidence=[Evidence(kind="probe", name="cover-frame", weight=1.0)],
    )


def _cover_timestamp(duration_seconds: float | None) -> float:
    if duration_seconds is None or duration_seconds <= 2:
        return 0.0
    return min(max(duration_seconds / 2, 0.0), 30.0)
