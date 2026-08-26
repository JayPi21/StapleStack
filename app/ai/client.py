"""Vertex AI client construction and error shaping."""

from __future__ import annotations

import logging
import threading
from typing import Any

from ..config import settings

log = logging.getLogger(__name__)

_client: Any | None = None
_init_error: str | None = None
_lock = threading.Lock()


def get_client() -> Any | None:
    """Build the Vertex AI client once. Returns None when unavailable."""
    global _client, _init_error
    if _client is not None or _init_error is not None:
        return _client

    with _lock:
        if _client is not None or _init_error is not None:
            return _client
        try:
            from google import genai

            _client = genai.Client(
                vertexai=True, project=settings.project_id, location=settings.location
            )
            log.info("Vertex AI ready: %s on %s", settings.model, settings.project_id)
        except Exception as exc:  # noqa: BLE001 - any failure means fall back
            _init_error = f"{type(exc).__name__}: {exc}"
            _client = None
            log.warning("Vertex AI unavailable: %s", _init_error)
    return _client


def generation_config() -> Any:
    from google.genai import types

    return types.GenerateContentConfig(
        temperature=settings.temperature,
        thinking_config=types.ThinkingConfig(thinking_level=settings.thinking_level),
        # No tools are used; disabling AFC stops the SDK warning about it.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def status() -> dict[str, Any]:
    get_client()
    return {"live": _client is not None, "error": _init_error}


def friendly_error(exc: Exception) -> str:
    """One line a presenter can read at a glance. Full text goes in `detail`."""
    name = type(exc).__name__
    if "DefaultCredentials" in name:
        return "Not signed in - run: gcloud auth application-default login"
    if "Refresh" in name or "Reauthentication" in str(exc):
        # Enterprise policies expire ADC periodically; the fix is the same command.
        return "Sign-in expired - run: gcloud auth application-default login"
    if "PermissionDenied" in name or "Forbidden" in name:
        return f"No access to {settings.model} on {settings.project_id}"
    if "NotFound" in name:
        return f"Model {settings.model} not found in {settings.location}"
    return f"{name}: {str(exc).split('. ')[0][:110]}"
