"""
StapleStack - Cart-to-Complete demo server.

    pip install -r requirements.txt
    python main.py     ->  http://localhost:8080
"""

import json
import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import vertex_kit

ROOT = Path(__file__).parent
CATALOG = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))["products"]
PERSONAS = json.loads((ROOT / "personas.json").read_text(encoding="utf-8"))["personas"]

BY_ID = {p["id"]: p for p in CATALOG}
PERSONA_BY_ID = {p["id"]: p for p in PERSONAS}

app = FastAPI(title="Cart-to-Complete")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/bootstrap")
def bootstrap():
    return {
        "personas": PERSONAS,
        "catalog": CATALOG,
        "model": vertex_kit.model_status(),
    }


class CartLine(BaseModel):
    id: str
    qty: int = 1


class KitRequest(BaseModel):
    persona_id: str
    cart: list[CartLine] = []
    scale: int | None = None


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@app.post("/api/kit/stream")
def kit_stream(req: KitRequest):
    persona = PERSONA_BY_ID.get(req.persona_id) or PERSONAS[0]
    cart_lines = [
        {"id": c.id, "name": BY_ID[c.id]["name"], "qty": c.qty}
        for c in req.cart
        if c.id in BY_ID
    ]

    def gen():
        started = time.time()
        seen = set()
        yield _sse({"type": "start", "persona": persona["label"], "t": 0})
        try:
            for evt in vertex_kit.stream_events(persona, cart_lines, CATALOG, req.scale):
                evt["t"] = round(time.time() - started, 2)

                # Enrich model output with catalog truth. The model picks ids and
                # quantities; names and prices always come from the catalog.
                if evt.get("type") in ("item", "skip"):
                    product = BY_ID.get(evt.get("id"))
                    if product is None:
                        continue  # model hallucinated an id - drop the line
                    if evt["id"] in seen:
                        continue
                    seen.add(evt["id"])
                    evt["name"] = product["name"]
                    evt["short"] = product.get("short", product["name"])
                    evt["pack"] = product["pack"]
                    evt["category"] = product["category"]
                    evt["price"] = product["price"]
                    if evt["type"] == "item":
                        qty = max(1, int(evt.get("qty", 1) or 1))
                        evt["qty"] = qty
                        evt["line_total"] = round(product["price"] * qty, 2)

                yield _sse(evt)
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "text": f"{type(exc).__name__}: {exc}"})
        yield _sse({"type": "end", "t": round(time.time() - started, 2)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), log_level="info")
