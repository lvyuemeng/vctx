from __future__ import annotations

from pathlib import Path

import pytest

from vctx.app.errors import NoTranscriptError
from vctx.io.cache import Cache
from vctx.sources.detect import detect_source_adapter
from vctx.sources.ytdlp_source import YtDlpSourceAdapter


class FakeYoutubeDL:
    calls: list[dict[str, object]] = []
    info: dict[str, object] = {}

    def __init__(self, params: dict[str, object]) -> None:
        self.params = params
        self.calls.append(params)

    def __enter__(self) -> FakeYoutubeDL:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def extract_info(self, value: str, download: bool = False) -> dict[str, object]:
        assert value == "https://video.example/watch?v=abc"
        assert download is False
        return self.info


def test_detect_source_adapter_selects_ytdlp_for_url() -> None:
    adapter = detect_source_adapter("https://video.example/watch?v=abc")

    assert adapter.name == "yt-dlp"


def test_ytdlp_metadata_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    import vctx.sources.ytdlp_source as module

    FakeYoutubeDL.calls = []
    FakeYoutubeDL.info = {
        "id": "abc",
        "title": "Lecture",
        "uploader": "Teacher",
        "duration": 123.4,
        "webpage_url": "https://video.example/watch?v=abc",
        "language": "en",
        "extractor": "example",
    }
    monkeypatch.setattr(module.yt_dlp, "YoutubeDL", FakeYoutubeDL)

    metadata = YtDlpSourceAdapter().extract_metadata("https://video.example/watch?v=abc")

    assert metadata.id == "example__abc"
    assert metadata.source_type == "url"
    assert metadata.title == "Lecture"
    assert metadata.uploader == "Teacher"
    assert metadata.duration_seconds == 123.4
    assert metadata.webpage_url == "https://video.example/watch?v=abc"
    assert metadata.extractor == "example"


def test_ytdlp_extract_transcript_prefers_official_subtitles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import vctx.sources.ytdlp_source as module

    subtitle_file = tmp_path / "caption.vtt"
    subtitle_file.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello\n", encoding="utf-8")
    FakeYoutubeDL.calls = []
    FakeYoutubeDL.info = {
        "id": "abc",
        "subtitles": {"en": [{"ext": "vtt", "url": subtitle_file.as_uri()}]},
        "automatic_captions": {"en": [{"ext": "vtt", "url": "file:///should/not/use.vtt"}]},
    }
    monkeypatch.setattr(module.yt_dlp, "YoutubeDL", FakeYoutubeDL)

    payload = YtDlpSourceAdapter().extract_transcript(
        "https://video.example/watch?v=abc",
        preferred_language="en",
        cache=Cache(root=tmp_path / "cache"),
    )

    assert payload.text.startswith("WEBVTT")
    assert payload.format == "vtt"
    assert payload.provenance.method == "official_subtitles"
    assert payload.provenance.language == "en"
    assert payload.provenance.provider == "yt-dlp"


def test_ytdlp_extract_transcript_raises_when_subtitles_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import vctx.sources.ytdlp_source as module

    FakeYoutubeDL.calls = []
    FakeYoutubeDL.info = {"id": "abc", "subtitles": {}, "automatic_captions": {}}
    monkeypatch.setattr(module.yt_dlp, "YoutubeDL", FakeYoutubeDL)

    with pytest.raises(NoTranscriptError, match="no subtitles found"):
        YtDlpSourceAdapter().extract_transcript(
            "https://video.example/watch?v=abc",
            preferred_language="en",
            cache=Cache(root=tmp_path / "cache"),
        )
