from __future__ import annotations

import importlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from vctx.app.config import AsrInstanceConfig
from vctx.models.media import MediaAsset
from vctx.models.transcript import TranscriptPayload, TranscriptProvenance
from vctx.transforms.planning import RoutePlan


class AsrExecutionError(RuntimeError):
    pass


class WhisperSegment(Protocol):
    start: float
    end: float
    text: str


class FasterWhisperAsrAdapter:
    def __init__(
        self,
        *,
        instance: AsrInstanceConfig,
        model_id: str | None,
        cache_root: Path,
        offline: bool = False,
    ) -> None:
        self.instance = instance
        self.model_id = model_id or instance.model or instance.model_policy
        self.cache_root = cache_root
        self.offline = offline

    def transcribe(self, media_asset: MediaAsset) -> TranscriptPayload:
        model_id = self._model_id()
        model_kwargs = self._model_kwargs(model_id)
        module = self._load_faster_whisper()
        try:
            whisper_model = module.WhisperModel(model_id, **model_kwargs)
            segments, _info = whisper_model.transcribe(
                str(media_asset.local_path), language=media_asset.language_hint
            )
        except Exception as exc:
            raise AsrExecutionError(
                "faster-whisper ASR failed. If offline, pre-populate the model cache "
                "or point the instance model to a local model path. Original error: "
                f"{exc}"
            ) from exc
        return TranscriptPayload(
            text=_segments_to_vtt(segments),
            format="vtt",
            provenance=TranscriptProvenance(
                method="asr",
                language=media_asset.language_hint,
                format="vtt",
                provider="faster-whisper",
            ),
        )

    def _model_id(self) -> str:
        model_id = self.model_id
        if model_id == "auto":
            return "base"
        return model_id

    def _model_kwargs(self, model_id: str) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "device": "auto",
            "compute_type": "default",
        }
        if self.instance.cache == "disabled":
            if not _looks_like_local_path(model_id):
                raise AsrExecutionError(
                    "cache = disabled requires a local model path for local-faster-whisper; "
                    "use cache = \"persistent\" to allow managed model download/cache"
                )
            kwargs["local_files_only"] = True
            return kwargs
        model_cache = self.cache_root / "models" / "faster-whisper"
        model_cache.mkdir(parents=True, exist_ok=True)
        kwargs["download_root"] = str(model_cache)
        kwargs["local_files_only"] = self.offline
        return kwargs

    def _load_faster_whisper(self) -> Any:
        try:
            return importlib.import_module("faster_whisper")
        except ModuleNotFoundError as exc:
            raise AsrExecutionError(
                "Install the ASR extra to use local faster-whisper ASR: "
                "uv sync --extra asr or uv add 'vctx[asr]'"
            ) from exc


def run_asr(
    plan: RoutePlan,
    media_asset: MediaAsset,
    *,
    instance: AsrInstanceConfig,
    cache_root: Path,
    offline: bool = False,
) -> TranscriptPayload:
    if plan.selected != "local":
        raise AsrExecutionError(f"ASR plan is not executable by local adapter: {plan.selected}")
    if instance.type != "local-faster-whisper":
        raise AsrExecutionError(f"unsupported ASR instance type: {instance.type}")
    adapter = FasterWhisperAsrAdapter(
        instance=instance,
        model_id=plan.model_id,
        cache_root=cache_root,
        offline=offline,
    )
    return adapter.transcribe(media_asset)


def _looks_like_local_path(value: str) -> bool:
    path = Path(value)
    return (
        path.exists()
        or path.is_absolute()
        or any(separator in value for separator in ("/", "\\"))
    )


def _segments_to_vtt(segments: Iterable[WhisperSegment]) -> str:
    blocks = ["WEBVTT", ""]
    for segment in segments:
        start = float(segment.start)
        end = float(segment.end)
        text = segment.text.strip()
        if not text:
            continue
        blocks.append(f"{_format_vtt_timestamp(start)} --> {_format_vtt_timestamp(end)}")
        blocks.append(text)
        blocks.append("")
    return "\n".join(blocks)


def _format_vtt_timestamp(seconds: float) -> str:
    milliseconds_total = max(0, round(seconds * 1000))
    milliseconds = milliseconds_total % 1000
    seconds_total = milliseconds_total // 1000
    secs = seconds_total % 60
    minutes_total = seconds_total // 60
    mins = minutes_total % 60
    hours = minutes_total // 60
    return f"{hours:02d}:{mins:02d}:{secs:02d}.{milliseconds:03d}"
