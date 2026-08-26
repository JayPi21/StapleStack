"""Application settings, resolved once at import from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    """Everything the app can be tuned with, in one place."""

    project_id: str = os.environ.get("GOOGLE_CLOUD_PROJECT", "prj-spls-np-hackathon31-000")
    location: str = os.environ.get("VERTEX_LOCATION", "global")
    model: str = os.environ.get("VERTEX_MODEL", "gemini-3.7-flash")

    # Gemini 3 thinks before emitting a token, and that wait is dead air on screen.
    # "low" cuts time-to-first-token roughly in half with no loss of kit quality.
    thinking_level: str = os.environ.get("VERTEX_THINKING_LEVEL", "low")
    temperature: float = _float("VERTEX_TEMPERATURE", 0.3)

    # Bundle saving applied only when a whole kit is added at once.
    kit_discount_rate: float = _float("KIT_DISCOUNT_RATE", 0.12)

    host: str = os.environ.get("HOST", "0.0.0.0")
    port: int = int(os.environ.get("PORT", 8080))
    log_level: str = os.environ.get("LOG_LEVEL", "info")

    data_dir: Path = BASE_DIR / "data"
    static_dir: Path = BASE_DIR / "static"

    @property
    def discount_label(self) -> str:
        return f"{round(self.kit_discount_rate * 100)}%"


settings = Settings()
