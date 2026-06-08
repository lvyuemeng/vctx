from __future__ import annotations

import srt

from vctx.models.transcript import Transcript, TranscriptPayload, TranscriptSegment


def parse_srt(payload: TranscriptPayload, *, video_id: str) -> Transcript:
    segments = [
        TranscriptSegment(
            id=f"seg_{index:06d}",
            start=item.start.total_seconds(),
            end=item.end.total_seconds(),
            text=item.content,
            source_id=str(item.index),
        )
        for index, item in enumerate(srt.parse(payload.text), start=1)
    ]
    return Transcript(video_id=video_id, provenance=payload.provenance, segments=segments)
