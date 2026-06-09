from __future__ import annotations

from pathlib import Path

from vctx.models.media import MediaAsset
from vctx.models.visual import FrameAsset, VisualRecord, VisualRecordSet
from vctx.transforms import visual_frames
from vctx.transforms.visual_planning import AcquisitionAction, VisualAssessment


class VisualExecutionError(RuntimeError):
    pass


def run_visual_context(
    assessment: VisualAssessment,
    media_asset: MediaAsset,
    out_dir: Path,
) -> VisualRecordSet:
    frames: list[FrameAsset] = []
    records: list[VisualRecord] = []
    frames_dir = out_dir / "visual" / "frames"

    for action in assessment.recipe:
        if action.name == "sample":
            frames = _extract_frames(media_asset, action, frames_dir)
        elif action.name == "capture":
            records.extend(_capture_records(frames, out_dir))
        elif action.name in {"ocr", "describe"}:
            # OCR/VLM operations are not added until their executable adapters exist.
            continue
    return VisualRecordSet(records=records)


def _extract_frames(
    media_asset: MediaAsset, action: AcquisitionAction, frames_dir: Path
) -> list[FrameAsset]:
    try:
        return visual_frames.extract_frames(media_asset, action, frames_dir)
    except RuntimeError as exc:
        raise VisualExecutionError(str(exc)) from exc


def _capture_records(frames: list[FrameAsset], out_dir: Path) -> list[VisualRecord]:
    records: list[VisualRecord] = []
    for index, frame in enumerate(frames, start=1):
        artifact_path = frame.path.relative_to(out_dir).as_posix()
        records.append(
            VisualRecord(
                id=f"capture-{index:04d}",
                timestamp_seconds=frame.timestamp_seconds,
                frame_id=frame.id,
                kind="capture",
                artifact_path=artifact_path,
                evidence=frame.evidence,
            )
        )
    return records
