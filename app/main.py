"""FastAPI application: bootstrap data and the streaming kit endpoint."""

from __future__ import annotations

import json
import logging
import time
from typing import Iterator

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import ai, catalog
from .config import settings
from .schemas import KitRequest

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("staplestack")


def create_app() -> FastAPI:
    app = FastAPI(title="StapleStack Cart-to-Complete", version="1.0.0")
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(settings.static_dir / "index.html")

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict:
        return {"status": "ok", "ai": ai.status()["live"]}

    @app.get("/api/bootstrap")
    def bootstrap() -> dict:
        """Everything the page needs on load."""
        return {
            "personas": catalog.personas(),
            "catalog": catalog.products(),
            "discount": {
                "rate": settings.kit_discount_rate,
                "label": settings.discount_label,
            },
        }

    @app.post("/api/kit/stream")
    def kit_stream(request: KitRequest) -> StreamingResponse:
        persona = catalog.get_persona(request.persona_id)
        cart_lines = catalog.resolve_cart(request.cart)

        return StreamingResponse(
            _events(persona, cart_lines, request.scale),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _events(persona: dict, cart_lines: list[dict], scale: int | None) -> Iterator[str]:
    """Decorate model events with catalog truth and frame them as SSE."""
    started = time.monotonic()
    seen_by_kit: dict[int, set[str]] = {}
    seen_skips: set[str] = set()

    yield _sse({"type": "start"})
    try:
        for event in ai.generate(persona, cart_lines, catalog.products(), scale):
            kind = event.get("type")

            if kind in ("item", "skip"):
                # De-duplicate per kit; the same product may legitimately appear in
                # both the Essentials and Complete kits.
                if kind == "item":
                    kit_index = int(event.get("kit", 0))
                    seen = seen_by_kit.setdefault(kit_index, set())
                else:
                    seen = seen_skips
                if event.get("id") in seen:
                    continue

                decorated = catalog.decorate(event)
                if decorated is None:
                    log.warning("dropping unknown product id: %s", event.get("id"))
                    continue
                seen.add(decorated["id"])
                event = decorated

            yield _sse(event)
    except Exception:  # noqa: BLE001
        log.exception("stream failed")
        yield _sse({"type": "error", "text": "Something went wrong building the kit."})

    log.info("kit stream finished in %.2fs", time.monotonic() - started)
    yield _sse({"type": "end"})


app = create_app()
