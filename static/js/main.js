// Application controller: boots data, owns the kit lifecycle, wires events.

import * as api from "./api.js";
import { money } from "./format.js";
import { activeKit, commit, liveLines, kitTotals, persona, state, subscribe } from "./store.js";
import { markKitTiles, renderCatalog } from "./ui/catalog.js";
import { renderCart } from "./ui/cart.js";
import { renderKit } from "./ui/kit.js";
import { markSelectedPersona, renderPersonas } from "./ui/personas.js";

// The model thinks first and then emits its whole answer in a burst. Draining the
// queue at a readable cadence keeps the reasoning legible. Only the spacing is ours.
const PACE = { thought: 460, kit: 300, item: 130, skip: 130 };

let stream = null;
const queue = [];
let draining = false;
let streamEnded = false;

// ---------------------------------------------------------------- boot

async function boot() {
  const data = await api.bootstrap();

  commit((s) => {
    s.personas = data.personas;
    s.catalog = data.catalog;
    s.byId = Object.fromEntries(data.catalog.map((p) => [p.id, p]));
    s.discount = data.discount;
  });

  renderPersonas(selectPersona);
  subscribe(render);
  wireEvents();
  selectPersona(state.personas[0].id);
}

function render() {
  renderCatalog();
  renderCart();
  renderKit();
  markSelectedPersona();
}

// ---------------------------------------------------------------- lifecycle

function selectPersona(id) {
  cancelStream();
  commit((s) => {
    s.personaId = id;
    s.cart = [];
    resetKit(s);
  });
}

function resetKit(s) {
  s.phase = "idle";
  s.thoughts = [];
  s.kits = [];
  s.skips = [];
  s.selectedKit = null;
  s.aiLive = true;
}

function cancelStream() {
  if (stream) stream.abort();
  stream = null;
  queue.length = 0;
  draining = false;
  streamEnded = false;
}

function addToCart(id, qty, savedTotal = 0) {
  commit((s) => {
    const existing = s.cart.find((line) => line.id === id);
    if (existing) {
      existing.qty += qty;
      existing.savedTotal = (existing.savedTotal || 0) + savedTotal;
      existing.isNew = true;
    } else {
      s.cart.push({ id, qty, isNew: true, savedTotal });
    }
  });
}

// ---------------------------------------------------------------- kit stream

function buildKit() {
  cancelStream();
  commit((s) => {
    resetKit(s);
    s.phase = "thinking";
  });

  const who = persona();
  stream = api.streamKit(
    {
      personaId: who.id,
      cart: state.cart.map((line) => ({ id: line.id, qty: line.qty })),
      scale: who.headcount,
    },
    enqueue
  );

  stream.promise
    .catch((err) => {
      if (err.name !== "AbortError") {
        enqueue({ type: "error", text: "We couldn't reach the assistant. Please try again." });
      }
    })
    .finally(() => {
      streamEnded = true;
      if (!draining) finish();
    });
}

function enqueue(event) {
  queue.push(event);
  if (!draining) drain();
}

function drain() {
  const event = queue.shift();
  if (!event) {
    draining = false;
    if (streamEnded) finish();
    return;
  }
  draining = true;
  apply(event);
  setTimeout(drain, PACE[event.type] ?? 0);
}

function apply(event) {
  commit((s) => {
    switch (event.type) {
      case "source":
        s.aiLive = event.live !== false;
        break;

      case "thought":
        s.thoughts.push({ text: event.text });
        break;

      case "error":
        // Operators need the real cause; shoppers need plain language.
        console.warn("[cart-to-complete]", event.text, event.detail || "");
        s.thoughts.push({
          text: "We had trouble reaching the assistant, so this is a standard kit.",
          error: true,
        });
        break;

      case "kit":
        s.kits[event.index ?? s.kits.length] = {
          name: event.name,
          summary: event.summary || "",
          items: [],
        };
        break;

      case "item": {
        const kit = s.kits[event.kit ?? 0];
        if (kit) kit.items.push({ ...event, qty: event.qty });
        break;
      }

      case "skip":
        s.skips.push(event);
        break;

      default:
        break;
    }
  });
}

function finish() {
  commit((s) => {
    // Drop any kit the model announced but never populated.
    s.kits = s.kits.filter((kit) => kit && kit.items.length > 0);
    if (s.kits.length === 0) {
      s.phase = "idle";
      s.thoughts.push({ text: "We couldn't build a kit for this cart.", error: true });
      s.phase = "thinking";
      return;
    }
    // One kit needs no comparison step.
    if (s.kits.length === 1) {
      s.selectedKit = 0;
      s.phase = "selected";
    } else {
      s.phase = "choosing";
    }
  });
}

// ---------------------------------------------------------------- events

function wireEvents() {
  // Add a machine to the cart.
  document.addEventListener("click", (event) => {
    const add = event.target.closest("[data-add]");
    if (!add) return;
    addToCart(add.dataset.add, 1);
  });

  // Choose one of the two kits.
  document.addEventListener("click", (event) => {
    const choice = event.target.closest("[data-choose]");
    if (!choice) return;
    commit((s) => {
      s.selectedKit = Number(choice.dataset.choose);
      s.phase = "selected";
    });
  });

  // Per-line quantity steppers.
  document.addEventListener("click", (event) => {
    const step = event.target.closest("[data-step]");
    if (!step) return;
    const delta = Number(step.dataset.step);
    const id = step.dataset.id;
    commit((s) => {
      const kit = s.kits[s.selectedKit];
      const line = kit?.items.find((i) => i.id === id);
      if (line) line.qty = Math.max(0, Math.min(99, line.qty + delta));
    });
    markKitTiles();
  });

  document.getElementById("ctaBtn").addEventListener("click", buildKit);

  document.getElementById("switchKitBtn").addEventListener("click", () => {
    commit((s) => {
      s.phase = "choosing";
      s.selectedKit = null;
    });
  });

  document.getElementById("restartBtn").addEventListener("click", () => {
    cancelStream();
    commit(resetKit);
  });

  document.getElementById("showAllBtn").addEventListener("click", () => {
    commit((s) => {
      s.selectedKit = null;
      s.phase = s.kits.length > 1 ? "choosing" : "idle";
    });
  });

  document.getElementById("addKitBtn").addEventListener("click", () => {
    const kit = activeKit();
    if (!kit) return;
    const rate = state.discount.rate;
    for (const line of liveLines(kit)) {
      addToCart(line.id, line.qty, line.unit_price * line.qty * rate);
    }
    const { total } = kitTotals(kit, rate);
    const button = document.getElementById("addKitBtn");
    button.textContent = `Added — ${money(total)}`;
    button.disabled = true;
    setTimeout(() => commit(resetKit), 1400);
  });
}

boot().catch((err) => {
  document.body.insertAdjacentHTML(
    "afterbegin",
    `<p style="padding:20px;color:#a30000">Failed to start: ${err.message}</p>`
  );
});
