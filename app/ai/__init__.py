"""Vertex AI integration: prompt, client, streaming and offline fallback."""

from .stream import generate
from .client import status

__all__ = ["generate", "status"]
