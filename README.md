# StapleStack — Cart-to-Complete

*Add one item. Get the whole package, sized to you.*

A buyer drops a coffee machine into a Staples cart. The assistant reads the cart and
the buyer's profile and composes the **complete set of supplies** that finishes the
job — sized to who is actually buying, and scoped to the contracted catalog.

Three demo buyers, one product category, one screen. Every product, price and photo is
real staples.com data.

---

## Run it

```bash
pip install -r requirements.txt
python -m app
```

Open <http://localhost:8080>.

With Docker:

```bash
docker build -t staplestack . && docker run -p 8080:8080 staplestack
```

Tests:

```bash
pip install -r requirements-dev.txt
pytest -q
```

### Sign in to Vertex AI

```bash
gcloud auth application-default login
gcloud config set project prj-spls-np-hackathon31-000
```

Credentials expire — corporate policies re-prompt periodically — so **re-run the first
command on the day you record**. When the assistant is unreachable the app falls back
to a built-in kit and says so in plain language on screen; the technical cause goes to
the browser console and the server log, never to the shopper.

Settings, all overridable by environment variable, live in [app/config.py](app/config.py):

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | `prj-spls-np-hackathon31-000` | Vertex project |
| `VERTEX_MODEL` | `gemini-3.7-flash` | Model id |
| `VERTEX_THINKING_LEVEL` | `low` | See below |
| `KIT_DISCOUNT_RATE` | `0.12` | Kit-exclusive bundle saving |
| `PORT` | `8080` | HTTP port |

---

## How the demo runs

**1. The cart is just a machine.** Nothing else on screen. No kit, no panel.

**2. An offer appears.** Once there is equipment to complete, a highlighted card slides
in: *New — Finish this setup automatically*, naming the machine and the bundle saving.
It pulses until clicked. Nothing about the kit is computed or shown until the buyer
opts in — the assistant is offered, never imposed.

**3. It reasons out loud, in plain English.** Ticks appear one at a time: *"This machine
brews from pods, so it needs K-Cups rather than ground coffee."* No field names, no
arithmetic notation, no model name, no stopwatch.

**4. Two kits, not one.** *Essentials* — the shortest list that genuinely makes the
machine work — against *Complete Station*, fully stocked. Each card shows its price,
its saving and a strip of product thumbnails. The buyer chooses; the assistant does not
decide for them. **Complete is always a superset of Essentials**, enforced by a test.

**5. The catalog narrows to the kit.** Choosing a kit filters the whole product grid
down to just those items, with a banner and a *Show all products* escape hatch. The
screen stops being a catalog and becomes a shopping list.

**6. Every line is editable.** Plus and minus on each row. Quantities and prices update
live, dropping a line to zero marks it *Removed* and takes it out of the filtered
catalog too. Rows patch in place rather than re-rendering, so the button never moves
out from under the cursor mid-click.

**7. The saving is kit-exclusive.** 12% comes off every line, shown struck-through per
row and totalled as a *Kit only* saving. Add the kit and that saving carries into the
cart summary — it exists only because the whole kit was taken together.

---

## The three buyers

| | **Hari** | **Ravi** | **Umesh** |
|---|---|---|---|
| Account | Individual | Individual | Business (Nair & Co.) |
| Serves | 1 person | 1 person | 12 people |
| Machine | Keurig K-Express | Keurig K-Express | Bunn VPR 12-Cup |
| Sweetener | Domino sugar | **Splenda — sugar-free** | Domino sugar, bulk |
| Creamer | Coffee mate regular | **Coffee mate Zero Sugar** | Coffee mate 180ct |
| Drinkware | skipped — own mug | skipped — own mug | 1000 cups + lids |

**Hari and Ravi buy the same machine.** Everything that differs between their kits comes
from the buyer profile, not the product. That is the sharpest evidence on screen that a
kit is reasoned about rather than looked up.

Buyers live in [data/personas.json](data/personas.json). Edit the `profile` block to
change how one is sized — it is passed to the model verbatim, nothing else to change.

---

## Architecture

```
app/
  config.py        Typed settings, one source of truth, env-overridable
  catalog.py       Catalog + persona data, pricing, discount, event decoration
  schemas.py       Validated request models
  main.py          App factory, routes, SSE framing
  ai/
    prompt.py      The prompt: two kits, plain-English reasoning
    client.py      Vertex client, generation config, error shaping
    stream.py      Streaming call + JSON Lines parsing
    fallback.py    Deterministic offline kits
data/              catalog.json, personas.json
static/
  css/             tokens, base, components
  js/
    store.js       Observable state; views subscribe, nothing mutates directly
    api.js         fetch + SSE reader
    ui/            personas, catalog, cart, kit
    main.js        Controller: lifecycle, event wiring, pacing
tests/             17 tests, no network
```

**The model never sees a price and never sets one.** It returns product ids and
quantities; names, packs, prices, line totals and the discount are all resolved from
`catalog.json` in `catalog.py`. An unknown id is dropped and logged rather than
rendered — there is a test asserting a model-supplied price is ignored.

### Why thinking_level is low

Gemini 3 thinks before emitting a token, and that wait is dead air. Measured on this
prompt: `high` gave 13.9s to first token and 15.9s total; `low` gave 6.3s and 8.7s,
with no observable difference in kit quality.

### Why the browser paces the stream

The model thinks first, then emits its whole answer in a roughly 2-second burst.
Rendered raw, every line flashes on screen at once. The browser drains the event queue
at a readable cadence (`PACE` in `static/js/main.js`). **The content is the model's;
only the spacing between lines is ours.**

---

## The catalog is real

Every product is a real staples.com item — name, SKU, price and photograph, captured
2026-08-26. Images are bundled locally rather than hotlinked, so a recording never
depends on the network.

It is scoped to coffee and deliberately contains **traps**:

- **Wrong brew type.** Bunn basket filters and Pike Place *ground* portion packs sit
  next to the pods. A kit for the pod machine must refuse all of them.
- **Sugar vs sugar-free.** Domino and Coffee mate French Vanilla against Splenda and
  Coffee mate *Zero Sugar*. Only the buyer profile separates them.
- **Desk vs bulk.** 24 vs 72 pods, 100 vs 400 Splenda, 50 vs 180 creamer, 50 vs 500
  cups, 250 vs 1000 filters. The wrong one is never *wrong*, just wasteful.

A correct kit is a real choice, not the only choice.

---

## Recording the demo

Run at 1512x1000 or larger, browser zoom 100%. One take per buyer, about 40 seconds each.

**Take 1 — Hari (the setup).** Land on the page. Add the recommended machine. Stop and
let the *New* card pulse before clicking it — that beat sells the opt-in. Let the ticks
land without talking over them. Point at the two kits, pick *Complete*, and watch the
catalog collapse to just those products. Nudge a quantity up and down. Add the kit.

**Take 2 — Ravi (the payoff).** Same machine, same button. Then stop on the kit:
Splenda where Hari got Domino, Zero Sugar creamer where Hari got regular, and Domino
sugar explicitly under *What we left out*. Nothing about the product changed. Only the
buyer did. This is the strongest ten seconds in the demo.

**Take 3 — Umesh (the scale).** The recommendation has already moved to the Bunn.
The reasoning now says *"Twelve people works out at about 672 cups, or 56 pots"*, and
the kit comes back in cases. Open *What we left out* to show the pods rejected outright.

Expect roughly 10 seconds per kit, of which the first 6 or so is the assistant thinking.
The spinner and the ticks carry that gap — don't cut away during it.
