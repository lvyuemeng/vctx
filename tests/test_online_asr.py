from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from vctx.app.config import AsrInstanceConfig
from vctx.app.credentials import CredentialError, resolve_env_credential
from vctx.cli import app
from vctx.models.common import SourceRef
from vctx.models.media import MediaAsset
from vctx.models.transcript import TranscriptPayload, TranscriptProvenance
from vctx.transforms.asr import AsrExecutionError, OpenAiCompatibleAsrAdapter

runner = CliRunner()


def test_resolve_env_credential_reads_selected_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("IGNORED=value\nOPENAI_API_KEY=from-dotenv\n", encoding="utf-8")

    assert resolve_env_credential("OPENAI_API_KEY", env_files=[env_file]) == "from-dotenv"


def test_resolve_env_credential_prefers_shell_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "from-shell")
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=from-dotenv\n", encoding="utf-8")

    assert resolve_env_credential("OPENAI_API_KEY", env_files=[env_file]) == "from-shell"


def test_resolve_env_credential_reports_missing_without_secret(tmp_path: Path) -> None:
    with pytest.raises(CredentialError, match="OPENAI_API_KEY"):
        resolve_env_credential("OPENAI_API_KEY", env_files=[tmp_path / "missing.env"])


def test_openai_compatible_asr_posts_audio_and_redacts_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "text": "hello online asr",
                    "segments": [
                        {"start": 0.0, "end": 1.2, "text": "hello online asr"},
                    ],
                }
            ).encode("utf-8")

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        calls["timeout"] = timeout
        calls["url"] = request.full_url
        calls["headers"] = dict(request.header_items())
        calls["data"] = request.data
        return FakeResponse()

    monkeypatch.setattr("vctx.transforms.asr.urlopen", fake_urlopen)
    media = _media_asset(tmp_path / "lecture.wav")
    media.local_path.write_bytes(b"fake audio")
    adapter = OpenAiCompatibleAsrAdapter(
        instance=AsrInstanceConfig(
            type="openai-compatible-audio",
            base_url="https://api.example.test/v1/audio/transcriptions",
            model="whisper-test",
            api_key_env="OPENAI_API_KEY",
        ),
        api_key="secret-token",
        provider_id="example-asr",
    )

    payload = adapter.transcribe(media)

    assert calls["url"] == "https://api.example.test/v1/audio/transcriptions"
    assert calls["headers"]["Authorization"] == "Bearer secret-token"
    assert b'name="model"' in calls["data"]
    assert b"whisper-test" in calls["data"]
    assert b'name="file"' in calls["data"]
    assert payload.format == "vtt"
    assert payload.provenance.provider == "example-asr"
    assert "hello online asr" in payload.text


def test_openai_compatible_asr_errors_do_not_include_api_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_urlopen(request: Any, timeout: int) -> object:
        del request, timeout
        raise OSError("network down")

    monkeypatch.setattr("vctx.transforms.asr.urlopen", fake_urlopen)
    media = _media_asset(tmp_path / "lecture.wav")
    media.local_path.write_bytes(b"fake audio")
    adapter = OpenAiCompatibleAsrAdapter(
        instance=AsrInstanceConfig(
            type="openai-compatible-audio",
            base_url="https://api.example.test/v1/audio/transcriptions",
            model="whisper-test",
            api_key_env="OPENAI_API_KEY",
        ),
        api_key="secret-token",
        provider_id="example-asr",
    )

    with pytest.raises(AsrExecutionError) as exc_info:
        adapter.transcribe(media)

    assert "network down" in str(exc_info.value)
    assert "secret-token" not in str(exc_info.value)


def test_prepare_local_media_can_use_configured_online_asr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import vctx.transforms.asr as asr_module

    calls: dict[str, Any] = {}

    class FakeOnlineAdapter:
        def __init__(self, **kwargs: object) -> None:
            calls["kwargs"] = kwargs

        def transcribe(self, media_asset: MediaAsset) -> TranscriptPayload:
            calls["media"] = media_asset.local_path
            return TranscriptPayload(
                text="WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nOnline CLI ASR.\n",
                format="vtt",
                provenance=TranscriptProvenance(
                    method="asr", language=None, format="vtt", provider="online-test"
                ),
            )

    monkeypatch.setattr(asr_module, "OpenAiCompatibleAsrAdapter", FakeOnlineAdapter)
    media = tmp_path / "lecture.wav"
    media.write_bytes(b"fake audio")
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=from-dotenv\n", encoding="utf-8")
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        f'''
[runtime]
env_files = ["{env_file.as_posix()}"]

[transforms.asr]
instance = "online-test"

[instances.asr.online-test]
type = "openai-compatible-audio"
base_url = "https://api.example.test/v1/audio/transcriptions"
api_key_env = "OPENAI_API_KEY"
model = "whisper-test"
cost = "paid"
upload = "required"
'''.strip(),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        ["prepare", str(media), "--out", str(out_dir), "--config", str(config_path)],
    )

    assert result.exit_code == 0, result.output
    assert calls["media"] == media
    assert calls["kwargs"]["api_key"] == "from-dotenv"
    assert calls["kwargs"]["provider_id"] == "online-test"
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "ok"
    assert manifest["transform_evidence"][0]["selected_route"] == "configured-online"
    assert manifest["transform_evidence"][0]["uploaded"] is True
    assert manifest["transform_evidence"][0]["cost_may_apply"] is True
    assert "from-dotenv" not in json.dumps(manifest)


def _media_asset(path: Path) -> MediaAsset:
    return MediaAsset(
        id="local__lecture",
        source=SourceRef(kind="file", value=str(path)),
        local_path=path,
        media_type="audio",
        container="wav",
        provider="local-file",
    )
