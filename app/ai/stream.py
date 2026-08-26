"""Streaming kit generation: call the model, parse JSON Lines, yield events."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

from ..config import settings
from . import client, fallback, prompt

log = logging.getLogger(__name__)

VALID_TYPES = {"thought", "kit", "item", "skip", "done"}


def parse_line(line: str) -> dict[str, Any] | None:
    """Parse one JSONL line, tolerating stray fences and trailing commas."""
    line = line.strip()
    if not line or line.startswith("```"):
        return None
    if line.endswith(","):
        line = line[:-1]
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict) or obj.get("type") not in VALID_TYPES:
        return None
    return obj


def generate(
    persona: dict[str, Any],
    cart_lines: list[dict[str, Any]],
    products: list[dict[str, Any]],
    scale: int | None,
    history: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield kit events, falling back to a local sample if Vertex is unavailable."""
    genai_client = client.get_client()
    if genai_client is None:
        yield _offline(client.status()["error"] or "AI unavailable")
        yield from fallback.events(persona, cart_lines, scale)
        return

    yield {"type": "source", "live": True}

    text_prompt = prompt.build(persona, cart_lines, products, scale, history)
    buffer = ""
    emitted = 0

    try:
        stream = genai_client.models.generate_content_stream(
            model=settings.model,
            contents=text_prompt,
            config=client.generation_config(),
        )
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if not text:
                continue
            buffer += text
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                event = parse_line(line)
                if event:
                    emitted += 1
                    yield event
        event = parse_line(buffer)
        if event:
            emitted += 1
            yield event
    except Exception as exc:  # noqa: BLE001
        log.exception("kit generation failed")
        yield {
            "type": "error",
            "text": client.friendly_error(exc),
            "detail": f"{type(exc).__name__}: {exc}",
        }
        if emitted == 0:
            yield _offline("live call failed")
            yield from fallback.events(persona, cart_lines, scale)
        return

    if emitted == 0:
        yield _offline("empty response")
        yield from fallback.events(persona, cart_lines, scale)


def _offline(note: str) -> dict[str, Any]:
    return {"type": "source", "live": False, "note": note}
