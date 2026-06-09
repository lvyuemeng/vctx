from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

from vctx.app.config import ProviderConfig
from vctx.app.credentials import CredentialError, resolve_env_credential
from vctx.models.visual import FrameAsset


class VisionExecutionError(RuntimeError):
    pass


class OpenAiVisionMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str | None = None


class OpenAiVisionChoice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: OpenAiVisionMessage


class OpenAiVisionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    choices: list[OpenAiVisionChoice] = Field(default_factory=list)


class OpenAiCompatibleVisionAdapter:
    def __init__(
        self,
        *,
        provider: ProviderConfig,
        provider_id: str,
        env_files: list[Path],
    ) -> None:
        self.provider = provider
        self.provider_id = provider_id
        self.env_files = env_files

    def describe(self, frame: FrameAsset) -> str:
        if not self.provider.base_url:
            raise VisionExecutionError("vision provider is missing base_url")
        if not self.provider.model:
            raise VisionExecutionError("vision provider is missing model")
        try:
            api_key = resolve_env_credential(
                self.provider.api_key_env,
                env_files=self.env_files,
            )
        except CredentialError as exc:
            raise VisionExecutionError(str(exc)) from exc
        payload = _vision_payload(frame.path, model=self.provider.model)
        request = Request(
            self.provider.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:  # noqa: S310 - configured endpoint.
                raw_payload = response.read()
        except Exception as exc:
            raise VisionExecutionError(f"vision request failed: {exc}") from exc
        try:
            response_payload = OpenAiVisionResponse.model_validate_json(raw_payload)
        except ValueError as exc:
            raise VisionExecutionError("vision provider returned invalid JSON") from exc
        return _description_text(response_payload)


def _vision_payload(frame_path: Path, *, model: str) -> dict[str, object]:
    media_type = mimetypes.guess_type(frame_path.name)[0] or "image/png"
    image_b64 = base64.b64encode(frame_path.read_bytes()).decode("ascii")
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Describe the visual source content in the frame. "
                            "Focus on diagrams, layout, labels, equations, and information "
                            "that is not recoverable from transcript text. Be concise and factual."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_b64}",
                        },
                    },
                ],
            }
        ],
        "temperature": 0,
    }


def _description_text(payload: OpenAiVisionResponse) -> str:
    if not payload.choices:
        raise VisionExecutionError("vision provider returned no choices")
    text = payload.choices[0].message.content
    if text is None or not text.strip():
        raise VisionExecutionError("vision provider returned empty description")
    return text.strip()
