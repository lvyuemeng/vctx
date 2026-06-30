from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from vctx.config import (
    BrowserSourceSession,
    DirectSourceNetwork,
    MediaProfile,
    PlaylistItemsSelection,
    PrepareRequest,
    ProxySourceNetwork,
    WorkflowProfile,
    resolve_config,
)


def test_config_file_supplies_defaults_and_asr_instance_config(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[runtime]
workflow = "transcript"
cache_dir = ".cache/vctx"
keep_temp = true

[output]
formats = ["json", "context"]
chunk_max_chars = 1200
chunk_max_seconds = 300

[transforms.asr]
use = "instance:openai-whisper"

[instances.asr.openai-whisper]
type = "openai-compatible-audio"
base_url = "https://api.openai.com/v1/audio/transcriptions"
api_key_env = "OPENAI_API_KEY"
model = "whisper-1"
""".strip(),
        encoding="utf-8",
    )

    resolved = resolve_config(
        PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out", config_path=config_path)
    )

    assert resolved.runtime.workflow == WorkflowProfile.TRANSCRIPT
    assert resolved.runtime.cache_dir == tmp_path / ".cache" / "vctx"
    assert resolved.runtime.keep_temp is True
    assert resolved.output.formats == {"json", "context"}
    assert resolved.output.chunk_max_chars == 1200
    assert resolved.output.chunk_max_seconds == 300
    assert resolved.transforms.asr.enabled is True
    assert resolved.transforms.asr.instance_name() == "openai-whisper"
    assert resolved.instances.asr["openai-whisper"].api_key_env == "OPENAI_API_KEY"


def test_config_file_supplies_vision_instance_config(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[transforms.visual_context]
use = "instance:test-vlm"

[instances.vision.test-vlm]
type = "openai-compatible-vision"
base_url = "https://example.invalid/v1/chat/completions"
api_key_env = "VISION_KEY"
model = "vision-test"
""".strip(),
        encoding="utf-8",
    )

    resolved = resolve_config(
        PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out", config_path=config_path)
    )

    assert resolved.transforms.visual_context.instance_name() == "test-vlm"
    assert resolved.instances.vision["test-vlm"].api_key_env == "VISION_KEY"
    assert resolved.instances.vision["test-vlm"].model == "vision-test"


def test_request_overrides_config_without_provider_menu_flags(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[runtime]
workflow = "visual"
offline = true

[transforms.asr]
""".strip(),
        encoding="utf-8",
    )

    resolved = resolve_config(
        PrepareRequest(
            input="lecture.mp4",
            out_dir=tmp_path / "out",
            config_path=config_path,
            workflow=WorkflowProfile.TRANSCRIPT,
            offline=True,
        )
    )

    assert resolved.runtime.workflow == WorkflowProfile.TRANSCRIPT
    assert resolved.runtime.offline is True
    assert resolved.transforms.visual_context.enabled is False


def test_config_resolves_minimal_ytdlp_source_options_as_sum_types(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[source.yt_dlp]
session = "browser:chrome"
network = "proxy:socks5://127.0.0.1:1080"
playlist = "items:3"
media_profile = "fast"
""".strip(),
        encoding="utf-8",
    )

    resolved = resolve_config(
        PrepareRequest(
            input="https://video.example/watch?v=abc",
            out_dir=tmp_path / "out",
            config_path=config_path,
        )
    )

    assert resolved.source.yt_dlp.session == BrowserSourceSession(browser="chrome")
    assert resolved.source.yt_dlp.network == ProxySourceNetwork(url="socks5://127.0.0.1:1080")
    assert resolved.source.yt_dlp.playlist == PlaylistItemsSelection(spec="3")
    assert resolved.source.yt_dlp.media_profile == MediaProfile.FAST


def test_config_defaults_ytdlp_source_options_to_concrete_variants(tmp_path: Path) -> None:
    resolved = resolve_config(
        PrepareRequest(input="https://video.example/watch?v=abc", out_dir=tmp_path / "out")
    )

    assert resolved.source.yt_dlp.session.kind == "none"
    assert resolved.source.yt_dlp.network == DirectSourceNetwork()
    assert resolved.source.yt_dlp.playlist.kind == "default"
    assert resolved.source.yt_dlp.media_profile == MediaProfile.BALANCED


def test_request_subtitle_languages_feed_ytdlp_source_options(tmp_path: Path) -> None:
    resolved = resolve_config(
        PrepareRequest(
            input="https://video.example/watch?v=abc",
            out_dir=tmp_path / "out",
            subtitle_languages=["ja", "zh-Hant"],
        )
    )

    assert resolved.source.yt_dlp.subtitle_languages == ["ja", "zh-Hant"]


def test_output_language_resolves_from_config(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[output]
language = "ja"
""".strip(),
        encoding="utf-8",
    )

    resolved = resolve_config(
        PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out", config_path=config_path)
    )

    assert resolved.output.language == "ja"


def test_request_output_language_overrides_config(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[output]
language = "ja"
""".strip(),
        encoding="utf-8",
    )

    resolved = resolve_config(
        PrepareRequest(
            input="lecture.mp4",
            out_dir=tmp_path / "out",
            config_path=config_path,
            output_language="zh-Hant",
        )
    )

    assert resolved.output.language == "zh-Hant"

def test_config_parse_rejects_unknown_top_level_section(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text("tranforms = {}", encoding="utf-8")

    with pytest.raises(ValidationError, match="tranforms"):
        resolve_config(
            PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out", config_path=config_path)
        )


def test_config_parse_rejects_scalar_transform_section(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[transforms]
visual_context = "yes"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="visual_context"):
        resolve_config(
            PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out", config_path=config_path)
        )


def test_config_parse_rejects_bad_use_literal(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[transforms.visual_context]
use = "cloudish"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="cloudish"):
        resolve_config(
            PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out", config_path=config_path)
        )


def test_config_parse_rejects_enabled_auto_string(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[transforms.visual_context]
enabled = "auto"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="enabled"):
        resolve_config(
            PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out", config_path=config_path)
        )


def test_config_resolve_rejects_missing_visual_instance_reference(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[transforms.visual_context]
use = "instance:openaii"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown vision instance"):
        resolve_config(
            PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out", config_path=config_path)
        )


def test_config_resolve_rejects_incomplete_selected_vision_instance(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[transforms.visual_context]
use = "instance:vlm"

[instances.vision.vlm]
type = "openai-compatible-vision"
model = "vision-test"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires base_url, api_key_env, and model"):
        resolve_config(
            PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out", config_path=config_path)
        )


def test_config_resolve_rejects_enabled_capability_with_none_use(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[transforms.visual_context]
enabled = true
use = "none"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="enabled capability cannot use none"):
        resolve_config(
            PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out", config_path=config_path)
        )


def test_config_resolve_rebases_vision_instance_path_model(tmp_path: Path) -> None:
    config_path = tmp_path / "vctx.toml"
    config_path.write_text(
        """
[transforms.visual_context]
use = "instance:local-vlm"

[instances.vision.local-vlm]
type = "openai-compatible-vision"
base_url = "https://example.invalid/v1/chat/completions"
api_key_env = "VISION_KEY"
model = "path:models/vision-model"
""".strip(),
        encoding="utf-8",
    )

    resolved = resolve_config(
        PrepareRequest(input="lecture.mp4", out_dir=tmp_path / "out", config_path=config_path)
    )

    assert resolved.instances.vision["local-vlm"].model == str(
        tmp_path / "models" / "vision-model"
    )
