"""
Cart-to-Complete kit generation.

The model is given the buyer's profile, the current cart, and the full contracted
catalog, and streams back JSON Lines - one object per line - so the UI can render
its reasoning as it arrives instead of waiting for a finished blob.

The model chooses SKUs and quantities only. Prices and totals are computed from
catalog.json in main.py, so the model can never invent a price.
"""

import json
import os
import time

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "prj-spls-np-hackathon25-000")
LOCATION = os.environ.get("VERTEX_LOCATION", "global")
MODEL_NAME = os.environ.get("VERTEX_MODEL", "gemini-3.7-flash")

# Gemini 3 thinks before it emits anything, and the wait is dead air on screen.
# "low" cuts time-to-first-token from ~14s to ~6s with no loss of kit quality.
THINKING_LEVEL = os.environ.get("VERTEX_THINKING_LEVEL", "low")

_client = None
_init_error = None


def _get_client():
    """Lazily build the Vertex AI client. Returns None if unavailable."""
    global _client, _init_error
    if _client is not None or _init_error is not None:
        return _client
    try:
        from google import genai

        _client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    except Exception as exc:  # noqa: BLE001 - any failure means fall back
        _init_error = f"{type(exc).__name__}: {exc}"
        _client = None
    return _client


def _config():
    from google.genai import types

    return types.GenerateContentConfig(
        temperature=0.3,
        thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
        # No tools are used; disabling AFC keeps the SDK from warning about it.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def model_status():
    _get_client()
    if _client is not None:
        return {"live": True, "model": MODEL_NAME, "project": PROJECT_ID, "error": None}
    return {"live": False, "model": MODEL_NAME, "project": PROJECT_ID, "error": _init_error}


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------

SYSTEM_RULES = """You are Cart-to-Complete, the kit builder inside a Staples business
storefront.

A buyer has put a piece of coffee equipment in their cart. Equipment alone does not
brew coffee. Your job is to compose the COMPLETE kit that finishes the job, sized to
this specific buyer, choosing only from the contracted catalog you are given.

Hard rules:
1. Only use product ids that appear in the catalog. Never invent an id or a price.
2. Match the consumables to the machine's brew_type. A single-serve pod machine takes
   pods and needs NO paper filters. A drip carafe machine takes ground coffee and DOES
   need paper filters. Getting this wrong ships a machine that cannot brew.
3. Respect the buyer's stated sweetener and creamer preference exactly. If the buyer
   avoids sugar, every sweetener and creamer you pick must be sugar-free.
4. Size quantities from the buyer's profile: people_served x cups_per_person_per_day x
   7 x restock_window_weeks gives total cups for the period. Convert to whole packs
   using units_per_pack, rounding up. Never ship a bulk case to a desk of one, and
   never ship a desk-sized jar to a 12-person breakroom.
5. Do not re-add anything already in the cart.
6. Explicitly SKIP the catalog items a careless buyer would wrongly add - especially
   consumables for the wrong brew type, or the wrong sweetener for this buyer. The skip
   and its reason is as valuable as the pick.

Output format - JSON Lines. Emit ONE compact JSON object per line, nothing else. No
markdown, no code fences, no blank lines, no commentary.

Emit in this order:
{"type":"thought","text":"<one short observation, max 12 words>"}   x4 to 6
{"type":"kit","name":"<short kit name>","summary":"<one sentence>"}
{"type":"item","id":"<catalog id>","qty":<int>,"why":"<max 10 words>"}   one per item
{"type":"skip","id":"<catalog id>","why":"<max 10 words>"}              1 to 3 of these
{"type":"done"}

Thoughts must be concrete deductions about THIS buyer and THIS machine - the brew type
you detected, the preference you are honouring, the arithmetic you used. Never generic
filler like "analysing cart".
"""


def build_prompt(persona, cart_lines, catalog, scale):
    catalog_view = []
    for p in catalog:
        entry = {
            "id": p["id"],
            "name": p["name"],
            "category": p["category"],
            "pack": p["pack"],
            "price": p["price"],
            "desc": p["desc"],
        }
        for k in ("brew_type", "for_brew_type", "sweetener_type", "creamer_type", "units_per_pack", "serves"):
            if k in p:
                entry[k] = p[k]
        catalog_view.append(entry)

    profile = dict(persona["profile"])
    if scale and scale != profile.get("people_served"):
        profile["people_served"] = scale
        profile["notes"] = profile.get("notes", "") + f" The buyer has adjusted headcount to {scale} people; resize every line accordingly."

    return (
        SYSTEM_RULES
        + "\n\nBUYER\n"
        + json.dumps(
            {
                "name": persona["label"],
                "account_type": persona["account_type"],
                "profile": profile,
            },
            indent=2,
        )
        + "\n\nCART (already owned, do not re-add)\n"
        + json.dumps(cart_lines, indent=2)
        + "\n\nCONTRACTED CATALOG\n"
        + json.dumps(catalog_view, indent=2)
        + "\n\nNow emit the JSON Lines."
    )


# --------------------------------------------------------------------------
# Streaming
# --------------------------------------------------------------------------


def stream_events(persona, cart_lines, catalog, scale):
    """Yield dict events. Falls back to a local generator if Vertex is unavailable."""
    client = _get_client()
    if client is None:
        yield {"type": "source", "live": False, "model": MODEL_NAME, "note": _init_error or "Vertex AI unavailable"}
        yield from _fallback_events(persona, cart_lines, catalog, scale)
        return

    yield {"type": "source", "live": True, "model": MODEL_NAME, "note": f"{PROJECT_ID} · {LOCATION}"}

    prompt = build_prompt(persona, cart_lines, catalog, scale)
    buffer = ""
    emitted = 0
    try:
        stream = client.models.generate_content_stream(
            model=MODEL_NAME, contents=prompt, config=_config()
        )
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if not text:
                continue
            buffer += text
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                evt = _parse_line(line)
                if evt:
                    emitted += 1
                    yield evt
        evt = _parse_line(buffer)
        if evt:
            emitted += 1
            yield evt
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "text": _short_error(exc), "detail": f"{type(exc).__name__}: {exc}"}
        if emitted == 0:
            yield {"type": "source", "live": False, "model": MODEL_NAME, "note": "live call failed, showing offline sample"}
            yield from _fallback_events(persona, cart_lines, catalog, scale)
            return

    if emitted == 0:
        yield {"type": "source", "live": False, "model": MODEL_NAME, "note": "empty response, showing offline sample"}
        yield from _fallback_events(persona, cart_lines, catalog, scale)


def _short_error(exc):
    """One line the presenter can read at a glance. Full text goes in `detail`."""
    name = type(exc).__name__
    if "DefaultCredentials" in name:
        return "Not authenticated - run: gcloud auth application-default login"
    if "PermissionDenied" in name or "Forbidden" in name:
        return f"No access to {MODEL_NAME} on {PROJECT_ID}"
    if "NotFound" in name:
        return f"Model {MODEL_NAME} not found in {LOCATION}"
    first = str(exc).split(". ")[0]
    return f"{name}: {first[:110]}"


def _parse_line(line):
    line = line.strip()
    if not line or line.startswith("```"):
        return None
    if line.endswith(","):
        line = line[:-1]
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) and "type" in obj else None


# --------------------------------------------------------------------------
# Offline fallback - deterministic, clearly labelled as not the live model
# --------------------------------------------------------------------------

_FALLBACK = {
    "maya": {
        "thoughts": [
            "K-Elite is single-serve - brews from pods, not grounds",
            "Pod machine: paper filters would be dead weight",
            "Buyer takes regular cane sugar, not sweetener",
            "1 person x 2 cups x 28 days = 56 pods",
            "56 pods needs 3 boxes of 24, not the 96 case",
        ],
        "kit": ("Desk Coffee Station", "A one-month single-serve setup for one desk, no bulk packs."),
        "items": [
            ("PODS-KCUP-24", 3, "56 cups over 4 weeks"),
            ("SUGAR-CAN-20OZ", 1, "regular sugar, desk-sized canister"),
            ("CREAMER-JAR-16OZ", 1, "45 servings, fits the fridge"),
            ("MUG-CERAMIC-14OZ", 1, "reusable, no disposables at a desk"),
            ("DESCALER-KEURIG", 1, "keeps the K-Elite brewing"),
            ("WATERFILTER-KEURIG-6", 1, "swap every 2 months"),
        ],
        "skips": [
            ("FILTERS-COMM-1000", "pod machine takes no paper filter"),
            ("CUPS-INSUL-300", "one desk, reusable mug instead"),
            ("SWEET-SF-CAN", "buyer takes regular sugar"),
        ],
    },
    "dan": {
        "thoughts": [
            "K-Elite is single-serve - brews from pods, not grounds",
            "Pod machine: paper filters would be dead weight",
            "Buyer avoids sugar - every sweetener must be sugar-free",
            "Original creamer contains sugar, so it is out",
            "1 person x 3 cups x 28 days = 84 pods",
        ],
        "kit": ("Sugar-Free Desk Station", "A one-month single-serve setup with no added sugar anywhere in the kit."),
        "items": [
            ("PODS-KCUP-96", 1, "84 cups over 4 weeks"),
            ("SWEET-SF-CAN", 1, "zero calorie, no sugar"),
            ("CREAMER-SF-JAR-32OZ", 1, "sugar free, 90 servings"),
            ("MUG-CERAMIC-14OZ", 1, "reusable, no disposables at a desk"),
            ("DESCALER-KEURIG", 1, "keeps the K-Elite brewing"),
            ("WATERFILTER-KEURIG-6", 1, "swap every 2 months"),
        ],
        "skips": [
            ("SUGAR-CAN-20OZ", "buyer avoids all added sugar"),
            ("CREAMER-JAR-16OZ", "original creamer contains sugar"),
            ("FILTERS-COMM-1000", "pod machine takes no paper filter"),
        ],
    },
    "priya": {
        "thoughts": [
            "Bunn 12-cup is a drip brewer - needs grounds and filters",
            "Pods would not fit this machine at all",
            "12 people x 2 cups x 28 days = 672 cups",
            "672 cups = 56 pots, so 3 bulk bags of grounds",
            "Shared breakroom - staff bring no mugs, so cups and lids",
        ],
        "kit": ("Breakroom Coffee Station", "A one-month drip station for a 12-person breakroom, in bulk pack sizes."),
        "items": [
            ("COFFEE-BULK-2LB", 3, "56 pots over 4 weeks"),
            ("FILTERS-COMM-1000", 1, "one filter per pot"),
            ("CUPS-INSUL-300", 3, "672 cups, disposable"),
            ("LIDS-DOME-300", 3, "matches the 12 oz cups"),
            ("SUGAR-PKT-500", 2, "single-serve for a shared station"),
            ("CREAMER-PKT-180", 4, "shelf-stable, no fridge space"),
            ("STIR-STICKS-1000", 1, "one per cup"),
            ("NAPKINS-BEV-500", 2, "shared station"),
        ],
        "skips": [
            ("PODS-KCUP-96", "wrong brew type for a drip carafe"),
            ("MUG-CERAMIC-14OZ", "staff do not bring mugs"),
            ("CREAMER-JAR-16OZ", "fridge bottle will not serve 12"),
        ],
    },
}


def _fallback_events(persona, cart_lines, catalog, scale):
    spec = _FALLBACK.get(persona["id"]) or _FALLBACK["maya"]
    base = persona["profile"]["people_served"]
    factor = max(1.0, (scale or base) / base) if base else 1.0

    for t in spec["thoughts"]:
        time.sleep(0.45)
        yield {"type": "thought", "text": t}
    name, summary = spec["kit"]
    time.sleep(0.3)
    yield {"type": "kit", "name": name, "summary": summary}
    owned = {c["id"] for c in cart_lines}
    for pid, qty, why in spec["items"]:
        if pid in owned:
            continue
        time.sleep(0.22)
        scaled = qty if factor == 1.0 else max(1, round(qty * factor))
        yield {"type": "item", "id": pid, "qty": scaled, "why": why}
    for pid, why in spec["skips"]:
        time.sleep(0.18)
        yield {"type": "skip", "id": pid, "why": why}
    yield {"type": "done"}
