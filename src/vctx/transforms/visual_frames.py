from __future__ import annotations

import subprocess
from pathlib import Path

from vctx.models.media import MediaAsset
from vctx.models.visual import FrameAsset
from vctx.transforms.visual_cases import EssentialVisualCase
from vctx.transforms.visual_planning import AcquisitionAction, Evidence


def extract_frames(
    media_asset: MediaAsset,
    sample_action: AcquisitionAction,
    frames_dir: Path,
) -> list[FrameAsset]:
    """Extract deterministic frame assets for the current visual capture slice."""

    frames_dir.mkdir(parents=True, exist_ok=True)
    strategy = str(sample_action.params.get("strategy", "cover"))
    if strategy == "essential_cases":
        cases = _sample_cases(sample_action)
        budget = int(sample_action.params.get("budget", len(cases)))
        if cases:
            return [
                _extract_case_frame(media_asset, frames_dir, case, index)
                for index, case in enumerate(cases[:budget], start=1)
            ]
    budget = int(sample_action.params.get("budget", 1))
    if strategy == "cover" or budget <= 1:
        return [_extract_cover_frame(media_asset, frames_dir)]
    return [_extract_cover_frame(media_asset, frames_dir)]


def _sample_cases(sample_action: AcquisitionAction) -> list[EssentialVisualCase]:
    raw_cases = sample_action.params.get("cases", [])
    if not isinstance(raw_cases, list):
        return []
    cases: list[EssentialVisualCase] = []
    for raw_case in raw_cases:
        if isinstance(raw_case, EssentialVisualCase):
            cases.append(raw_case)
        elif isinstance(raw_case, dict):
            cases.append(EssentialVisualCase.model_validate(raw_case))
    return cases


def _extract_case_frame(
    media_asset: MediaAsset,
    frames_dir: Path,
    case: EssentialVisualCase,
    index: int,
) -> FrameAsset:
    frame_id = f"frame-{index:04d}"
    frame_path = frames_dir / f"{frame_id}.png"
    _run_ffmpeg_frame_extract(media_asset, frame_path, case.timestamp_seconds)
    return FrameAsset(
        id=frame_id,
        timestamp_seconds=case.timestamp_seconds,
        path=frame_path,
        source="transcript_anchor",
        evidence=[
            Evidence(kind="transcript", name=case.case_type, weight=case.priority),
            Evidence(kind="transcript", name="essential-case", weight=case.priority),
        ],
    )


def _extract_cover_frame(media_asset: MediaAsset, frames_dir: Path) -> FrameAsset:
    timestamp = _cover_timestamp(media_asset.duration_seconds)
    frame_path = frames_dir / "frame-0001.png"
    _run_ffmpeg_frame_extract(media_asset, frame_path, timestamp)
    return FrameAsset(
        id="frame-0001",
        timestamp_seconds=timestamp,
        path=frame_path,
        source="cover",
        evidence=[Evidence(kind="probe", name="cover-frame", weight=1.0)],
    )


def _run_ffmpeg_frame_extract(
    media_asset: MediaAsset, frame_path: Path, timestamp: float
) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        str(media_asset.local_path),
        "-frames:v",
        "1",
        str(frame_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"failed to extract frame with ffmpeg: {exc}") from exc


def _cover_timestamp(duration_seconds: float | None) -> float:
    if duration_seconds is None or duration_seconds <= 2:
        return 0.0
    return min(max(duration_seconds / 2, 0.0), 30.0)
