"""Thin Strands/Bedrock wrappers with test-injectable hooks.

The three model-calling agents (intake, verification, pattern) go through here so
tests can substitute deterministic responses without touching AWS.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from .config import get_settings

# Test hooks: set to a callable to bypass Bedrock entirely.
_vision_hook: Callable[..., dict[str, Any]] | None = None
_text_hook: Callable[[str, str], str] | None = None


def set_vision_hook(fn: Callable[..., dict[str, Any]] | None) -> None:
    global _vision_hook
    _vision_hook = fn


def set_text_hook(fn: Callable[[str, str], str] | None) -> None:
    global _text_hook
    _text_hook = fn


def _strands_agent(model_id: str, system_prompt: str):
    from strands import Agent
    from strands.models import BedrockModel

    return Agent(
        model=BedrockModel(model_id=model_id, region_name=get_settings().aws_region),
        system_prompt=system_prompt,
    )


def vision_json(
    system_prompt: str,
    user_text: str,
    images: list[bytes],
    *,
    model_id: str | None = None,
) -> dict[str, Any]:
    """Send text + image(s), expect a JSON object back."""
    if _vision_hook is not None:
        return _vision_hook(system_prompt=system_prompt, user_text=user_text, images=images)

    from strands import Agent
    from strands.models import BedrockModel

    s = get_settings()
    agent = Agent(
        model=BedrockModel(
            model_id=model_id or s.bedrock_vision_model_id, region_name=s.aws_region
        ),
        system_prompt=system_prompt,
    )
    content: list[dict[str, Any]] = [{"text": user_text}]
    for img in images:
        # boto3/Strands expect the raw image bytes here — it base64-encodes on
        # the wire itself. Pre-encoding produces a base64 string that Bedrock
        # then rejects as "not a JPEG" (double-encoded).
        content.append({"image": {"format": "jpeg", "source": {"bytes": img}}})
    result = agent([{"role": "user", "content": content}])
    return _extract_json(str(result))


def text(system_prompt: str, user_text: str, *, model_id: str | None = None) -> str:
    if _text_hook is not None:
        return _text_hook(system_prompt, user_text)
    s = get_settings()
    agent = _strands_agent(model_id or s.bedrock_reasoning_model_id, system_prompt)
    return str(agent(user_text))


def _extract_json(raw: str) -> dict[str, Any]:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in model output: {raw!r}")
    return json.loads(raw[start : end + 1])
