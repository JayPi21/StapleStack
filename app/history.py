"""Purchase history: the dummy "buy" flow's one lasting effect.

Every completed checkout is appended to a flat JSON file, keyed by persona. It
is the entire "database" - a demo has no business standing up real storage.
The only reason it exists is so the next kit for the same buyer can be built
against what they actually bought, not just their static profile.
"""

from __future__ import annotations

import json
import time
from threading import Lock
from typing import Any

from . import catalog
from .config import settings

_LOCK = Lock()


def _path():
    return settings.data_dir / "order_history.json"


def _load() -> dict[str, list[dict[str, Any]]]:
    path = _path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def record_order(persona_id: str, lines: list[dict[str, Any]]) -> dict[str, Any]:
    """Append a completed order for this buyer and return it."""
    order = {
        "ts": time.time(),
        "items": [{"id": l["id"], "name": l["name"], "qty": l["qty"]} for l in lines],
    }
    with _LOCK:
        data = _load()
        data.setdefault(persona_id, []).append(order)
        _path().write_text(json.dumps(data, indent=2), encoding="utf-8")
    return order


def summarize(persona_id: str) -> str | None:
    """A short natural-language note on what this buyer has actually bought
    before, for the model to weigh alongside their stated profile. None if
    they have never checked out."""
    orders = _load().get(persona_id, [])
    if not orders:
        return None

    sweetener_counts: dict[str, int] = {}
    creamer_counts: dict[str, int] = {}
    name_counts: dict[str, int] = {}

    for order in orders:
        for line in order["items"]:
            name_counts[line["name"]] = name_counts.get(line["name"], 0) + line["qty"]
            product = catalog.get_product(line["id"])
            if not product:
                continue
            if product.get("sweetener_type"):
                key = product["sweetener_type"]
                sweetener_counts[key] = sweetener_counts.get(key, 0) + line["qty"]
            if product.get("creamer_type"):
                key = product["creamer_type"]
                creamer_counts[key] = creamer_counts.get(key, 0) + line["qty"]

    bits = [f"This buyer has checked out {len(orders)} time(s) before."]
    if sweetener_counts:
        top = max(sweetener_counts, key=sweetener_counts.get)
        bits.append(f"Every sweetener they have ever bought has been {top}.")
    if creamer_counts:
        top = max(creamer_counts, key=creamer_counts.get)
        bits.append(f"Every creamer they have ever bought has been {top}.")

    top_items = sorted(name_counts.items(), key=lambda kv: -kv[1])[:3]
    if top_items:
        listed = ", ".join(f"{qty}x {name}" for name, qty in top_items)
        bits.append(f"Most repurchased items: {listed}.")

    return " ".join(bits)
