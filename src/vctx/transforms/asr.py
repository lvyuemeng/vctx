from __future__ import annotations

import importlib
import json
import mimetypes
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.request import Request, urlopen

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
        if _looks_like_local_path(model_id):
            kwargs["local_files_only"] = True
            return kwargs
        if self.instance.cache == "disabled":
            raise AsrExecutionError(
                "cache = disabled requires a local model path for local-faster-whisper; "
                "set model to an explicit local path or omit cache for managed persistent cache"
            )
        model_cache = self.cache_root / "models" / "faster-whisper"
        try:
            model_cache.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise AsrExecutionError(
                "ASR model cache is not writable. Free disk space, choose another "
                "runtime.cache_dir, or set model to an explicit local model path. "
                f"Cache path: {model_cache}. Original error: {exc}"
            ) from exc
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


class OpenAiCompatibleAsrAdapter:
    def __init__(
        self,
        *,
        instance: AsrInstanceConfig,
        api_key: str,
        provider_id: str,
    ) -> None:
        self.instance = instance
        self.api_key = api_key
        self.provider_id = provider_id

    def transcribe(self, media_asset: MediaAsset) -> TranscriptPayload:
        if not self.instance.base_url:
            raise AsrExecutionError("openai-compatible ASR instance is missing base_url")
        model = self.instance.model or "whisper-1"
        data, content_type = _multipart_audio_payload(media_asset.local_path, model=model)
        request = Request(
            self.instance.base_url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": content_type,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:  # noqa: S310 - configured endpoint.
                raw_payload = response.read()
        except Exception as exc:
            raise AsrExecutionError(f"online ASR request failed: {exc}") from exc
        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AsrExecutionError("online ASR returned invalid JSON") from exc
        return TranscriptPayload(
            text=_openai_response_to_vtt(payload),
            format="vtt",
            provenance=TranscriptProvenance(
                method="asr",
                language=media_asset.language_hint,
                format="vtt",
                provider=self.provider_id,
            ),
        )


def run_asr(
    plan: RoutePlan,
    media_asset: MediaAsset,
    *,
    instance: AsrInstanceConfig,
    cache_root: Path,
    offline: bool = False,
    api_key: str | None = None,
) -> TranscriptPayload:
    if plan.selected == "local":
        if instance.type != "local-faster-whisper":
            raise AsrExecutionError(f"unsupported local ASR instance type: {instance.type}")
        adapter = FasterWhisperAsrAdapter(
            instance=instance,
            model_id=plan.model_id,
            cache_root=cache_root,
            offline=offline,
        )
        return adapter.transcribe(media_asset)
    if plan.selected == "configured-online":
        if instance.type != "openai-compatible-audio":
            raise AsrExecutionError(f"unsupported online ASR instance type: {instance.type}")
        if not api_key:
            raise AsrExecutionError("online ASR credential is missing")
        adapter = OpenAiCompatibleAsrAdapter(
            instance=instance,
            api_key=api_key,
            provider_id=plan.provider_id or "configured-asr",
        )
        return adapter.transcribe(media_asset)
    raise AsrExecutionError(f"ASR plan is not executable: {plan.selected}")


def _openai_response_to_vtt(payload: object) -> str:
    if not isinstance(payload, dict):
        raise AsrExecutionError("online ASR returned a non-object JSON payload")
    response = cast(dict[str, object], payload)
    segments = response.get("segments")
    if isinstance(segments, list) and segments:
        return _segments_to_vtt(_json_segments(cast(list[object], segments)))
    text = response.get("text")
    if isinstance(text, str) and text.strip():
        return "WEBVTT\n\n00:00:00.000 --> 00:00:00.001\n" + text.strip() + "\n"
    raise AsrExecutionError("online ASR returned no transcript text")


def _json_segments(values: list[object]) -> Iterable[WhisperSegment]:
    class JsonSegment:
        def __init__(self, start: float, end: float, text: str) -> None:
            self.start = start
            self.end = end
            self.text = text

    for value in values:
        if not isinstance(value, dict):
            continue
        segment = cast(dict[str, object], value)
        start = segment.get("start")
        end = segment.get("end")
        text = segment.get("text")
        valid_segment = (
            isinstance(start, int | float)
            and isinstance(end, int | float)
            and isinstance(text, str)
        )
        if valid_segment:
            yield JsonSegment(float(start), float(end), text)


def _multipart_audio_payload(path: Path, *, model: str) -> tuple[bytes, str]:
    boundary = f"----vctx-{uuid.uuid4().hex}"
    content_type = f"multipart/form-data; boundary={boundary}"
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = bytearray()
    _append_form_field(body, boundary, "model", model)
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        (
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            f"Content-Type: {media_type}\r\n\r\n"
        ).encode()
    )
    body.extend(path.read_bytes())
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), content_type


def _append_form_field(body: bytearray, boundary: str, name: str, value: str) -> None:
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
    body.extend(value.encode())
    body.extend(b"\r\n")


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
