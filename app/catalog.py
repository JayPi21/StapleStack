"""Catalog and persona data, plus the pricing rules the model is not trusted with.

The model chooses product ids and quantities. Everything a customer is charged -
names, pack sizes, unit prices, line totals and the bundle discount - is resolved
here from the catalog, so a hallucinated id or price can never reach the page.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from .config import settings

Product = dict[str, Any]
Persona = dict[str, Any]


@lru_cache(maxsize=1)
def _load() -> tuple[list[Product], list[Persona]]:
    catalog = json.loads((settings.data_dir / "catalog.json").read_text(encoding="utf-8"))
    personas = json.loads((settings.data_dir / "personas.json").read_text(encoding="utf-8"))
    return catalog["products"], personas["personas"]


def products() -> list[Product]:
    return _load()[0]


def personas() -> list[Persona]:
    return _load()[1]


@lru_cache(maxsize=1)
def _product_index() -> dict[str, Product]:
    return {p["id"]: p for p in products()}


@lru_cache(maxsize=1)
def _persona_index() -> dict[str, Persona]:
    return {p["id"]: p for p in personas()}


def get_product(product_id: str) -> Product | None:
    return _product_index().get(product_id)


def get_persona(persona_id: str) -> Persona:
    """Return the requested persona, falling back to the first one."""
    return _persona_index().get(persona_id) or personas()[0]


def resolve_cart(lines: list[Any]) -> list[dict[str, Any]]:
    """Turn request cart lines into catalog-backed lines, dropping unknown ids."""
    resolved = []
    for line in lines:
        product = get_product(line.id)
        if product is None:
            continue
        resolved.append({"id": product["id"], "name": product["name"], "qty": line.qty})
    return resolved


def price_line(product: Product, qty: int) -> dict[str, Any]:
    """Full price of one kit line, before and after the bundle discount."""
    qty = max(1, int(qty))
    listed = round(product["price"] * qty, 2)
    discounted = round(listed * (1 - settings.kit_discount_rate), 2)
    return {
        "qty": qty,
        "unit_price": product["price"],
        "line_total": listed,
        "line_total_discounted": discounted,
        "saving": round(listed - discounted, 2),
    }


def decorate(event: dict[str, Any]) -> dict[str, Any] | None:
    """Attach catalog truth to a model item/skip event. None means drop the event."""
    product = get_product(event.get("id", ""))
    if product is None:
        return None

    event["name"] = product["name"]
    event["short"] = product.get("short", product["name"])
    event["pack"] = product["pack"]
    event["img"] = product["img"]
    event["category"] = product["category"]
    event["price"] = product["price"]

    if event.get("type") == "item":
        event.update(price_line(product, event.get("qty", 1)))
    return event
