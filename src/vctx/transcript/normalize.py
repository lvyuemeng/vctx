from __future__ import annotations

from vctx.models.transcript import Transcript, TranscriptSegment, reassign_segment_ids
from vctx.transcript.clean_text import clean_subtitle_text


def normalize_transcript(raw: Transcript) -> Transcript:
    cleaned: list[TranscriptSegment] = []
    for segment in raw.segments:
        text = clean_subtitle_text(segment.text)
        if not text:
            continue
        cleaned.append(segment.model_copy(update={"text": text}))
    cleaned.sort(key=lambda segment: segment.start)
    return raw.model_copy(update={"segments": reassign_segment_ids(cleaned)})
