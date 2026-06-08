from __future__ import annotations

import io

import webvtt

from vctx.models.transcript import Transcript, TranscriptPayload, TranscriptSegment


def _timestamp_to_seconds(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return hours * 3600 + minutes * 60 + seconds


def parse_webvtt(payload: TranscriptPayload, *, video_id: str) -> Transcript:
    captions = webvtt.from_buffer(io.StringIO(payload.text)).captions
    segments = [
        TranscriptSegment(
            id=f"seg_{index:06d}",
            start=_timestamp_to_seconds(caption.start),
            end=_timestamp_to_seconds(caption.end),
            text=caption.text,
            source_id=str(index),
        )
        for index, caption in enumerate(captions, start=1)
    ]
    return Transcript(video_id=video_id, provenance=payload.provenance, segments=segments)
