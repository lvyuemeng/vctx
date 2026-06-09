from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal, cast
from urllib.parse import urlparse
from urllib.request import urlopen

import yt_dlp

from vctx.app.errors import NoTranscriptError
from vctx.io.cache import Cache
from vctx.models.common import SourceRef
from vctx.models.media import MediaAsset
from vctx.models.metadata import VideoMetadata
from vctx.models.transcript import TranscriptPayload, TranscriptProvenance

SubtitleKind = Literal["official_subtitles", "automatic_subtitles"]
_SUPPORTED_SUBTITLE_EXTS = {"vtt", "srt", "json", "plain"}


@dataclass(frozen=True)
class SubtitleCandidate:
    kind: SubtitleKind
    language: str
    ext: Literal["vtt", "srt", "json", "plain", "unknown"]
    url: str


class YtDlpSourceAdapter:
    name = "yt-dlp"

    def can_handle(self, value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def extract_metadata(self, value: str) -> VideoMetadata:
        info = _extract_info(value)
        extractor = _as_optional_str(info.get("extractor"))
        video_id = _as_optional_str(info.get("id")) or "unknown"
        normalized_id = f"{extractor}__{video_id}" if extractor else f"url__{video_id}"
        return VideoMetadata(
            id=normalized_id,
            source_type="url",
            source=SourceRef(kind="url", value=value),
            title=_as_optional_str(info.get("title")),
            uploader=_as_optional_str(info.get("uploader")),
            duration_seconds=_as_optional_float(info.get("duration")),
            webpage_url=_as_optional_str(info.get("webpage_url")) or value,
            language=_as_optional_str(info.get("language")),
            extractor=extractor,
            raw_provider="yt-dlp",
        )

    def extract_transcript(
        self, value: str, *, preferred_language: str | None, cache: Cache
    ) -> TranscriptPayload:
        del cache
        info = _extract_info(value)
        candidate = _select_subtitle_candidate(info, preferred_language=preferred_language)
        if candidate is None:
            raise NoTranscriptError(f"no subtitles found for input: {value}")
        return TranscriptPayload(
            text=_read_subtitle_text(candidate.url),
            format=candidate.ext,
            provenance=TranscriptProvenance(
                method=candidate.kind,
                language=candidate.language,
                format=candidate.ext,
                provider="yt-dlp",
            ),
        )

    def extract_media(
        self, value: str, *, preferred_language: str | None, cache: Cache
    ) -> MediaAsset:
        del preferred_language, cache
        raise NoTranscriptError(f"media extraction not implemented for URL input: {value}")


def _extract_info(value: str) -> dict[str, Any]:
    params: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(params) as ydl:
        info = ydl.extract_info(value, download=False)
    if not isinstance(info, dict):
        raise NoTranscriptError(f"yt-dlp returned no metadata for input: {value}")
    return info


def _select_subtitle_candidate(
    info: dict[str, Any], *, preferred_language: str | None
) -> SubtitleCandidate | None:
    language_order = _language_order(info, preferred_language=preferred_language)
    subtitle_maps: list[tuple[SubtitleKind, object]] = [
        ("official_subtitles", info.get("subtitles")),
        ("automatic_subtitles", info.get("automatic_captions")),
    ]
    for kind, subtitle_map in subtitle_maps:
        if not isinstance(subtitle_map, dict):
            continue
        subtitle_entries = cast(dict[str, object], subtitle_map)
        for language in language_order:
            entries = subtitle_entries.get(language)
            candidate = _candidate_from_entries(kind, language, entries)
            if candidate is not None:
                return candidate
        for language, entries in subtitle_entries.items():
            if not isinstance(language, str):
                continue
            candidate = _candidate_from_entries(kind, language, entries)
            if candidate is not None:
                return candidate
    return None


def _language_order(info: dict[str, Any], *, preferred_language: str | None) -> list[str]:
    values: list[str] = []
    if preferred_language:
        values.append(preferred_language)
    info_language = _as_optional_str(info.get("language"))
    if info_language:
        values.append(info_language)
    values.extend(["en", "zh", "zh-Hans", "zh-CN"])
    return list(dict.fromkeys(values))


def _candidate_from_entries(
    kind: SubtitleKind, language: str, entries: object
) -> SubtitleCandidate | None:
    if not isinstance(entries, Iterable) or isinstance(entries, str | bytes):
        return None
    fallback: SubtitleCandidate | None = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        subtitle = cast(dict[str, object], entry)
        url = _as_optional_str(subtitle.get("url"))
        if not url:
            continue
        ext = _normalize_subtitle_ext(subtitle.get("ext"))
        candidate = SubtitleCandidate(kind=kind, language=language, ext=ext, url=url)
        if ext in {"vtt", "srt"}:
            return candidate
        if fallback is None:
            fallback = candidate
    return fallback


def _normalize_subtitle_ext(value: object) -> Literal["vtt", "srt", "json", "plain", "unknown"]:
    normalized = value.lower() if isinstance(value, str) else ""
    if normalized == "vtt":
        return "vtt"
    if normalized == "srt":
        return "srt"
    if normalized == "json":
        return "json"
    if normalized == "plain":
        return "plain"
    return "unknown"


def _read_subtitle_text(url: str) -> str:
    with urlopen(url, timeout=30) as response:  # noqa: S310 - URLs come from source adapter.
        payload = response.read()
    return payload.decode("utf-8-sig")


def _as_optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _as_optional_float(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None
