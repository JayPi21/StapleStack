# StapleStack — Cart-to-Complete

*Add one item. Get the whole package, sized to you.*

A buyer drops a coffee machine into a Staples cart. Gemini reads the cart and the
buyer's profile, and composes the **complete kit** that finishes the job — sized to who
is actually buying, and scoped to the contracted catalog.

Three demo buyers, one product category, one screen.

---

## Run it

```bash
pip install -r requirements.txt
python main.py
```

Open <http://localhost:8080>.

### Authenticate to Vertex AI (required for live AI)

```bash
gcloud auth application-default login
gcloud config set project prj-spls-np-hackathon25-000
```

The model badge in the Cart-to-Complete panel tells you which mode you are in:

| Badge | Meaning |
|---|---|
| 🟢 `gemini-3.7-flash · 2.4s` | Live Vertex AI call |
| 🟡 `gemini-3.7-flash (offline sample)` | Vertex unreachable — deterministic local kit |

The offline mode exists so the demo never dies on stage, but it **labels itself**. If
you see amber before recording, fix the auth — the panel also prints the exact reason
on the first line of the stream.

Override the defaults with env vars if needed:

```bash
GOOGLE_CLOUD_PROJECT=...      # default prj-spls-np-hackathon25-000
VERTEX_LOCATION=...           # default global
VERTEX_MODEL=...              # default gemini-3.7-flash
VERTEX_THINKING_LEVEL=...     # default low - see below
```

### Why `thinking_level=low`

Gemini 3 thinks before it emits a single token, and that wait is dead air on
screen. Measured on this prompt:

| thinking_level | time to first token | total |
|---|---|---|
| `high` | 13.9s | 15.9s |
| `low` | 6.3s | 8.7s |

Kit quality is indistinguishable between the two, so the demo runs `low`. This
needs the current `google-genai` SDK — the older `vertexai.generative_models`
SDK exposes no thinking controls at all (and is deprecated, removal June 2026).

---

## The three buyers

Switch with the chips in the top right. Switching resets the cart, so each take starts
clean.

| | **Maya Chen** | **Dan Okafor** | **Priya Rivera** |
|---|---|---|---|
| Account | Individual | Individual | Business (Rivera & Co.) |
| Serves | 1 person | 1 person | 12 people |
| Machine | Keurig K-Elite single-serve | Keurig K-Elite single-serve | Bunn 12-cup drip brewer |
| Sweetener | regular cane sugar | **sugar-free only** | sugar packets, bulk |
| Kit shape | small packs, reusable mug | small packs, everything sugar-free | bulk cases, disposables |

**Maya and Dan buy the same machine.** Everything that differs between their kits comes
from the buyer profile, not the SKU. That is the sharpest evidence on screen that a kit
is being reasoned about rather than looked up.

Personas live in [personas.json](personas.json) — edit the `profile` block to change how
a buyer is sized. Nothing else needs to change; the profile is passed to the model
verbatim.

---

## How the AI shows itself

The model returns **JSON Lines** — one object per line — streamed to the browser over
SSE. Line-delimited JSON can't half-parse, so the stream stays robust under a live demo.

```
{"type":"thought","text":"K-Elite is single-serve — brews from pods, not grounds"}
{"type":"thought","text":"Buyer avoids sugar — every sweetener must be sugar-free"}
{"type":"kit","name":"Sugar-Free Desk Station","summary":"..."}
{"type":"item","id":"PODS-KCUP-96","qty":1,"why":"84 cups over 4 weeks"}
{"type":"skip","id":"CREAMER-JAR-16OZ","why":"original creamer contains sugar"}
{"type":"done"}
```

Four things make this legible to an audience:

1. **Reasoning arrives first, one line at a time**, with a blinking caret and a ticking
   latency counter showing real elapsed time. Note that the model does its thinking up
   front and then emits the whole answer in a ~2s burst, so the browser drains the
   event queue at a readable cadence (`PACE` in `static/app.js`) instead of flashing
   thirteen lines on screen at once. The content and the timer are the model's; only
   the spacing between lines is ours.
2. **Catalog tiles light up `IN KIT`** as the model picks them — you watch it reach into
   the same catalog that's on screen.
3. **Skips are shown, with reasons.** A pod machine takes no paper filter; a sugar-free
   buyer gets no cane sugar. Knowing what to leave out is what a recommendation widget
   cannot do.
4. **The model never sees a price.** It chooses SKU ids and quantities only; names,
   pack sizes, prices and totals are joined from `catalog.json` server-side in
   [main.py](main.py). A hallucinated id is dropped rather than rendered.

---

## Layout

```
main.py          FastAPI. /api/bootstrap, /api/kit/stream (SSE). Joins model output to catalog truth.
vertex_kit.py    Prompt, Vertex AI streaming call, JSONL parsing, offline fallback.
catalog.json     24 coffee SKUs. The whole contracted catalog.
personas.json    The three buyers.
static/          index.html, app.js, styles.css
```

The catalog is deliberately scoped to coffee and deliberately contains **traps**: cone
filters and 1000-count urn filters that a pod machine must not be given, regular and
sugar-free versions of every sweetener and creamer, and desk-sized versus case-sized
packs of the same product. A correct kit is a real choice, not the only choice.

---

## Recording the demo

Run at 1440×900 or larger, browser zoom 100%. One take per buyer, ~35 seconds each.

**Take 1 — Maya (the setup).** Land on the page. Pause on `RECOMMENDED FOR MAYA`.
Click **Add to cart**. Let the reasoning stream run without talking over it — the
latency counter is doing the work. Point at *"pod machine: paper filters would be dead
weight"*, then at the struck-through `12-Cup Filters 1000ct` under **Deliberately left
out**. Click **Add kit to cart**: one coffee maker becomes a finished coffee station.

**Take 2 — Dan (the payoff).** Switch to Dan. Same machine, same button. Then stop on
the kit: Splenda instead of Domino, sugar-free creamer instead of original, and *cane
sugar explicitly rejected* — "buyer avoids all added sugar". Nothing about the product
changed. Only the buyer did.

**Take 3 — Priya (the scale).** Switch to Priya. The recommendation badge has moved to
the Bunn brewer on its own. Add it. Now the arithmetic is visible in the stream —
*12 × 2 × 28 = 672 cups* — and the kit comes back in cases: bulk grounds, 1000-count
filters, 900 cups with matching lids, stir sticks, napkins. Drag the **Sized for**
slider from 12 to 25 and let it regenerate live for the closing shot.

If you want one continuous take instead, run the three buyers back to back without
touching anything else — the reset-on-switch behaviour keeps it clean.

Expect roughly 10 seconds per kit end to end, of which the first ~6 is the model
thinking before it says anything. That gap is the one place the demo looks idle — the
blinking caret and the ticking counter carry it, so don't cut away during it.
