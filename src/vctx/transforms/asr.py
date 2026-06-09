from __future__ import annotations

from vctx.app.config import AsrInstanceConfig
from vctx.models.media import MediaAsset
from vctx.models.transcript import TranscriptPayload
from vctx.transforms.planning import RoutePlan


class AsrExecutionError(RuntimeError):
    pass


class FasterWhisperAsrAdapter:
    def __init__(self, *, instance: AsrInstanceConfig, model_id: str | None) -> None:
        self.instance = instance
        self.model_id = model_id or instance.model or instance.model_policy

    def transcribe(self, media_asset: MediaAsset) -> TranscriptPayload:
        del media_asset
        raise AsrExecutionError(
            "local faster-whisper ASR execution is not installed yet; "
            "install the ASR extra before using this adapter"
        )


def run_asr(
    plan: RoutePlan,
    media_asset: MediaAsset,
    *,
    instance: AsrInstanceConfig,
) -> TranscriptPayload:
    if plan.selected != "local":
        raise AsrExecutionError(f"ASR plan is not executable by local adapter: {plan.selected}")
    if instance.type != "local-faster-whisper":
        raise AsrExecutionError(f"unsupported ASR instance type: {instance.type}")
    adapter = FasterWhisperAsrAdapter(instance=instance, model_id=plan.model_id)
    return adapter.transcribe(media_asset)
