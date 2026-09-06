"""The two models: the real one, and a scripted one for tests.

The scripted one is not a mock of the API — it is a way to say "the model asks
for this tool call, then that one", so a test can assert what the *tools* do.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

#: Sonnet is the default because a job runner is a batch worker, not a
#: conversation; pass --model to reach for something larger on hard work.
DEFAULT_MODEL = "claude-sonnet-5"
MAX_TOKENS = 4096


class AnthropicModel:
    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - environment, not logic
            raise SystemExit("the anthropic package is not installed: pip install anthropic") from exc
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise SystemExit("ANTHROPIC_API_KEY is not set (and no --api-key given)")
        self.model = model
        self.client = anthropic.Anthropic(api_key=key)

    def respond(self, messages: list[dict], tools: list[dict], system: str) -> Any:
        return self.client.messages.create(
            model=self.model, max_tokens=MAX_TOKENS, system=system,
            tools=tools, messages=messages)


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    name: str
    input: dict
    id: str = "call"
    type: str = "tool_use"


@dataclass
class ScriptedResponse:
    content: list
    stop_reason: str = "tool_use"


class ScriptedModel:
    """Replays a fixed list of turns. Records what it was told, so a test can
    assert that a refusal actually reached the model."""

    def __init__(self, turns: list[list]) -> None:
        self.turns = list(turns)
        self.seen: list[dict] = []

    def respond(self, messages: list[dict], tools: list[dict], system: str) -> Any:
        self.seen = messages
        if not self.turns:
            return ScriptedResponse([TextBlock("done")], stop_reason="end_turn")
        blocks = self.turns.pop(0)
        for index, block in enumerate(blocks):
            if isinstance(block, ToolUseBlock):
                block.id = f"call-{len(self.seen)}-{index}"
        return ScriptedResponse(blocks,
                                stop_reason="tool_use" if any(
                                    isinstance(b, ToolUseBlock) for b in blocks)
                                else "end_turn")

    @property
    def tool_results(self) -> list[dict]:
        """Every tool result the loop handed back, flattened."""
        out = []
        for message in self.seen:
            content = message.get("content")
            if isinstance(content, list):
                out += [b for b in content if isinstance(b, dict)
                        and b.get("type") == "tool_result"]
        return out
