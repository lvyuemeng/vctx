from __future__ import annotations

from vctx.app.errors import InvalidTranscriptError
from vctx.models.transcript import Transcript, TranscriptPayload
from vctx.subtitles.srt_parser import parse_srt
from vctx.subtitles.webvtt_parser import parse_webvtt


def parse_transcript_payload(payload: TranscriptPayload, *, video_id: str) -> Transcript:
    if payload.format == "srt":
        return parse_srt(payload, video_id=video_id)
    if payload.format == "vtt":
        return parse_webvtt(payload, video_id=video_id)
    raise InvalidTranscriptError(f"unsupported transcript format: {payload.format}")
