"""Catalog integrity and pricing rules."""

import pytest

from app import catalog
from app.config import settings


def test_every_product_is_complete():
    for product in catalog.products():
        for field in ("id", "name", "short", "sku", "img", "category", "pack", "price", "desc"):
            assert field in product, f"{product.get('id')} missing {field}"
        assert product["price"] > 0


def test_product_ids_are_unique():
    ids = [p["id"] for p in catalog.products()]
    assert len(ids) == len(set(ids))


def test_every_persona_recommends_a_real_machine():
    for persona in catalog.personas():
        machine = catalog.get_product(persona["recommended_machine"])
        assert machine is not None, persona["id"]
        assert machine["category"] == "machine"


def test_fallback_only_references_real_products():
    from app.ai.fallback import SAMPLES

    known = {p["id"] for p in catalog.products()}
    for persona_id, sample in SAMPLES.items():
        for _, _, items in sample["kits"]:
            for product_id, _, _ in items:
                assert product_id in known, f"{persona_id}: unknown {product_id}"
        for product_id, _ in sample["skips"]:
            assert product_id in known, f"{persona_id}: unknown skip {product_id}"


def test_fallback_covers_every_persona():
    from app.ai.fallback import SAMPLES

    assert {p["id"] for p in catalog.personas()} == set(SAMPLES)


def test_complete_kit_is_a_superset_of_essentials():
    from app.ai.fallback import SAMPLES

    for persona_id, sample in SAMPLES.items():
        essentials = {i[0] for i in sample["kits"][0][2]}
        complete = {i[0] for i in sample["kits"][1][2]}
        assert essentials <= complete, persona_id
        assert len(complete) > len(essentials), persona_id


@pytest.mark.parametrize("qty", [1, 3, 7])
def test_discount_applied_to_line(qty):
    product = catalog.products()[0]
    line = catalog.price_line(product, qty)
    assert line["line_total"] == pytest.approx(product["price"] * qty, abs=0.01)
    expected = line["line_total"] * (1 - settings.kit_discount_rate)
    assert line["line_total_discounted"] == pytest.approx(expected, abs=0.01)
    assert line["saving"] > 0


def test_decorate_drops_unknown_ids():
    assert catalog.decorate({"type": "item", "id": "NOT-A-REAL-SKU", "qty": 1}) is None


def test_decorate_never_trusts_model_price():
    product = catalog.products()[0]
    event = catalog.decorate({"type": "item", "id": product["id"], "qty": 2, "price": 0.01})
    assert event["price"] == product["price"]
    assert event["line_total"] == pytest.approx(product["price"] * 2, abs=0.01)
