from __future__ import annotations

from pathlib import Path

from vctx.app.config import CapabilityEnabled, PrepareRequest, WorkflowProfile, resolve_config


def test_config_file_supplies_defaults_and_provider_config(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[runtime]
workflow = "transcript"
cache_dir = ".cache/vctx"
keep_temp = true

[source]
preferred_language = "en"
subtitle_fallback_order = ["manual", "automatic"]
media_download_policy = "never"

[output]
formats = ["json", "context"]
chunk_max_chars = 1200
chunk_max_seconds = 300

[transforms.asr]
enabled = "true"
route = "configured-online"
allow_network = true
allow_upload = true
allow_paid = true
preferred_provider = "openai-whisper"
model = "whisper-1"

[providers.asr.openai-whisper]
type = "openai-compatible-audio"
base_url = "https://api.openai.com/v1/audio/transcriptions"
api_key_env = "OPENAI_API_KEY"
model = "whisper-1"
cost_mode = "paid"
""".strip(),
        encoding="utf-8",
    )

    resolved = resolve_config(
        PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out", config_path=config_path)
    )

    assert resolved.runtime.workflow == WorkflowProfile.TRANSCRIPT
    assert resolved.runtime.cache_dir == tmp_path / ".cache" / "vctx"
    assert resolved.runtime.keep_temp is True
    assert resolved.source.preferred_language == "en"
    assert resolved.source.subtitle_fallback_order == ["manual", "automatic"]
    assert resolved.source.media_download_policy == "never"
    assert resolved.output.formats == {"json", "context"}
    assert resolved.output.chunk_max_chars == 1200
    assert resolved.output.chunk_max_seconds == 300
    assert resolved.transforms.asr.enabled == CapabilityEnabled.TRUE
    assert resolved.transforms.asr.route == "configured-online"
    assert resolved.transforms.asr.allow_upload is True
    assert resolved.transforms.asr.allow_paid is True
    assert resolved.transforms.asr.preferred_provider == "openai-whisper"
    assert resolved.transforms.asr.model == "whisper-1"
    assert resolved.providers.asr["openai-whisper"].api_key_env == "OPENAI_API_KEY"
    assert resolved.providers.asr["openai-whisper"].cost_mode == "paid"


def test_request_overrides_config_without_provider_menu_flags(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[runtime]
workflow = "visual"
offline = true

[source]
preferred_language = "en"

[transforms.asr]
allow_network = true
allow_upload = true
""".strip(),
        encoding="utf-8",
    )

    resolved = resolve_config(
        PrepareRequest(
            input="lecture.mp4",
            out_dir=tmp_path / "out",
            config_path=config_path,
            language="zh",
            workflow=WorkflowProfile.TRANSCRIPT,
            offline=True,
        )
    )

    assert resolved.runtime.workflow == WorkflowProfile.TRANSCRIPT
    assert resolved.runtime.offline is True
    assert resolved.source.preferred_language == "zh"
    assert resolved.transforms.asr.allow_network is False
    assert resolved.transforms.asr.allow_upload is False
    assert resolved.transforms.visual_context.enabled == CapabilityEnabled.FALSE
