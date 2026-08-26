"""Deterministic kits used when Vertex AI is unreachable.

This exists so a live demo degrades visibly rather than dying. Every event it
produces is labelled as an offline sample upstream, so it is never mistaken for
real model output.
"""

from __future__ import annotations

import time
from typing import Any, Iterator

# thoughts, then (kit name, summary, [(id, qty, why)]) for Essentials and Complete,
# then the shared skips.
SAMPLES: dict[str, dict[str, Any]] = {
    "hari": {
        "thoughts": [
            "This machine brews from pods, so it needs K-Cups rather than ground coffee.",
            "Pods carry their own filter, so there are no paper filters to buy.",
            "That is about 56 cups over the next month for one person.",
            "You take regular sugar, so this uses cane sugar rather than sweetener.",
        ],
        "kits": [
            (
                "Desk Essentials",
                "Just enough to get the machine brewing for a month at one desk.",
                [
                    ("PODS-PIKE-24", 3, "covers about 56 cups"),
                    ("SUGAR-DOMINO-100", 1, "regular sugar, desk pack"),
                ],
            ),
            (
                "Complete Desk Station",
                "A fully stocked desk setup for the month, with creamer to hand.",
                [
                    ("PODS-PIKE-24", 3, "covers about 56 cups"),
                    ("SUGAR-DOMINO-100", 1, "regular sugar, desk pack"),
                    ("CREAMER-FV-50", 2, "keeps without a fridge"),
                ],
            ),
        ],
        "skips": [
            ("GROUND-PIKE-18", "ground coffee will not fit this machine"),
            ("FILTERS-BUNN-250", "pods already have their own filter"),
            ("CUPS-DIXIE-50", "you use your own mug at the desk"),
        ],
    },
    "ravi": {
        "thoughts": [
            "This machine brews from pods, so it needs K-Cups rather than ground coffee.",
            "Pods carry their own filter, so there are no paper filters to buy.",
            "You avoid sugar, so everything chosen here is sugar-free.",
            "That is about 84 cups over the next month, so four boxes covers it.",
        ],
        "kits": [
            (
                "Sugar-Free Essentials",
                "The shortest sugar-free list that gets the machine brewing.",
                [
                    ("PODS-PIKE-24", 4, "covers about 84 cups"),
                    ("SPLENDA-100", 1, "sweetener with no sugar"),
                ],
            ),
            (
                "Complete Sugar-Free Station",
                "A full month at your desk with nothing containing added sugar.",
                [
                    ("PODS-PIKE-24", 4, "covers about 84 cups"),
                    ("SPLENDA-100", 1, "sweetener with no sugar"),
                    ("CREAMER-SF-50", 2, "sugar-free, keeps without a fridge"),
                ],
            ),
        ],
        "skips": [
            ("SUGAR-DOMINO-100", "contains sugar, which you avoid"),
            ("CREAMER-FV-50", "this creamer has added sugar"),
            ("FILTERS-BUNN-250", "pods already have their own filter"),
        ],
    },
    "umesh": {
        "thoughts": [
            "This is a drip brewer, so it needs ground coffee and basket filters.",
            "Pods would not fit this machine at all.",
            "Twelve people works out at about 672 cups, or 56 pots, this month.",
            "Each portion pack makes exactly one pot, so four boxes covers it.",
            "Nobody brings a mug to a shared breakroom, so cups and lids are needed.",
        ],
        "kits": [
            (
                "Breakroom Essentials",
                "The coffee and filters the brewer needs to run for a month.",
                [
                    ("GROUND-PIKE-18", 4, "one pack makes one pot"),
                    ("FILTERS-BUNN-1000", 1, "one filter per pot"),
                    ("CUPS-DIXIE-500", 2, "enough cups for the team"),
                ],
            ),
            (
                "Complete Breakroom Station",
                "Everything a 12-person breakroom needs, fully stocked for the month.",
                [
                    ("GROUND-PIKE-18", 4, "one pack makes one pot"),
                    ("FILTERS-BUNN-1000", 1, "one filter per pot"),
                    ("CUPS-DIXIE-500", 2, "enough cups for the team"),
                    ("LIDS-DIXIE-500", 2, "fits the cups above"),
                    ("SUGAR-DOMINO-100", 7, "sugar for the whole team"),
                    ("CREAMER-FV-180", 4, "keeps without fridge space"),
                    ("STIRRERS-PERK-1000", 1, "one for every cup"),
                ],
            ),
        ],
        "skips": [
            ("PODS-PIKE-72", "pods do not fit a drip brewer"),
            ("SPLENDA-400", "the team asked for regular sugar"),
            ("CUPS-DIXIE-50", "far too few cups for twelve people"),
        ],
    },
}

# Used instead of a persona sample whenever the cart holds the printer, not a
# coffee machine - the persona samples above are coffee-only and would ship
# K-Cups to a buyer who never asked for coffee.
PRINTER_SAMPLE: dict[str, Any] = {
    "thoughts": [
        "This is an inkjet printer, so it needs ink cartridges and paper, not coffee.",
        "Black and tri-color cover normal office printing.",
        "One ream is enough to get started without over-buying.",
    ],
    "kits": [
        (
            "Printer Essentials",
            "Ink and paper to get the printer working right away.",
            [
                ("INK-HP67-BLACK", 1, "black ink for everyday documents"),
                ("INK-HP67-TRICOLOR", 1, "color ink for everyday documents"),
                ("PAPER-HP-1REAM", 1, "one ream to start printing"),
            ],
        ),
        (
            "Complete Printer Station",
            "Everything in Essentials plus backup high-yield ink, bulk paper, and shipping labels.",
            [
                ("INK-HP67-BLACK", 1, "black ink for everyday documents"),
                ("INK-HP67-TRICOLOR", 1, "color ink for everyday documents"),
                ("PAPER-HP-1REAM", 1, "one ream to start printing"),
                ("INK-HP67XL-BLACK", 1, "high-yield backup black ink"),
                ("INK-HP67XL-TRICOLOR", 1, "high-yield backup color ink"),
                ("PAPER-STAPLES-8REAM-CASE", 1, "bulk paper so you don't run out"),
                ("LABELS-STAPLES-SHIP-1000", 1, "labels for outgoing mail"),
            ],
        ),
    ],
    "skips": [
        ("PAPER-PHOTO-HP-GLOSSY-50", "glossy stock, not needed for everyday documents"),
    ],
}


def events(persona: dict[str, Any], cart_lines: list[dict[str, Any]], scale: int | None) -> Iterator[dict]:
    owned = {line["id"] for line in cart_lines}
    if "MACHINE-PRINTER-AIO" in owned:
        yield from _run(PRINTER_SAMPLE, cart_lines, factor=1.0)
        return

    sample = SAMPLES.get(persona["id"]) or next(iter(SAMPLES.values()))
    base = persona["profile"]["people_served"] or 1
    factor = max(1.0, (scale or base) / base)
    yield from _run(sample, cart_lines, factor)


def _run(sample: dict[str, Any], cart_lines: list[dict[str, Any]], factor: float) -> Iterator[dict]:
    owned = {line["id"] for line in cart_lines}

    for text in sample["thoughts"]:
        time.sleep(0.35)
        yield {"type": "thought", "text": text}

    for index, (name, summary, items) in enumerate(sample["kits"]):
        time.sleep(0.25)
        yield {"type": "kit", "index": index, "name": name, "summary": summary}
        for product_id, qty, why in items:
            if product_id in owned:
                continue
            time.sleep(0.12)
            scaled = qty if factor == 1.0 else max(1, round(qty * factor))
            yield {"type": "item", "kit": index, "id": product_id, "qty": scaled, "why": why}

    for product_id, why in sample["skips"]:
        time.sleep(0.12)
        yield {"type": "skip", "id": product_id, "why": why}

    yield {"type": "done"}
