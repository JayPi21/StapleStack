// StapleStack - Cart-to-Complete demo front end.

const $ = (id) => document.getElementById(id);
const money = (n) => "$" + n.toFixed(2);

const ART = {
  "MACHINE-KEURIG-KELITE": "☕",
  "MACHINE-BUNN-12CUP": "\u{1F375}",
};

const state = {
  personas: [],
  catalog: [],
  byId: {},
  personaId: null,
  cart: [],          // [{id, qty}]
  kit: [],           // [{id, qty, ...}]
  scale: 1,
  streaming: false,
  abort: null,
  timerId: null,
};

// ---------------------------------------------------------------- boot

async function boot() {
  const data = await (await fetch("/api/bootstrap")).json();
  state.personas = data.personas;
  state.catalog = data.catalog;
  state.byId = Object.fromEntries(data.catalog.map((p) => [p.id, p]));
  state.model = data.model;

  renderPersonas();
  renderCatalog();
  selectPersona(state.personas[0].id);
}

// ---------------------------------------------------------------- personas

function currentPersona() {
  return state.personas.find((p) => p.id === state.personaId);
}

function renderPersonas() {
  $("personaSwitch").innerHTML = state.personas
    .map(
      (p) => `
      <button class="persona-btn" role="tab" data-persona="${p.id}" aria-selected="false">
        <span class="avatar">${p.initials}</span>
        <span class="persona-meta">
          <b>${p.label}</b>
          <span>${p.account_type} · ${p.headcount_label}</span>
        </span>
      </button>`
    )
    .join("");

  $("personaSwitch").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-persona]");
    if (btn) selectPersona(btn.dataset.persona);
  });
}

// Switching persona resets the demo to a clean slate: empty cart, no kit.
function selectPersona(id) {
  state.personaId = id;
  state.cart = [];
  state.kit = [];
  state.scale = currentPersona().headcount;
  stopStream();

  document.querySelectorAll("[data-persona]").forEach((b) => {
    b.setAttribute("aria-selected", String(b.dataset.persona === id));
  });

  $("kitCard").hidden = true;
  renderCatalog();
  renderCart();
}

// ---------------------------------------------------------------- catalog

function renderCatalog() {
  const persona = currentPersona();
  const machines = state.catalog.filter((p) => p.category === "machine");
  const rest = state.catalog.filter((p) => p.category !== "machine");

  $("catalogCount").textContent = `${state.catalog.length} contracted items`;
  $("restCount").textContent = rest.length;

  $("machines").innerHTML = machines
    .map((m) => {
      const rec = persona && m.id === persona.recommended_machine;
      const inCart = state.cart.some((c) => c.id === m.id);
      return `
      <article class="machine ${rec ? "recommended" : ""}">
        ${rec ? `<span class="rec-badge">Recommended for ${persona.label.split(" ")[0]}</span>` : ""}
        <div class="machine-art">${ART[m.id] || "☕"}</div>
        <h3>${m.name}</h3>
        <div class="spec">${m.brew_type} · serves ${m.serves}</div>
        <div class="price">${money(m.price)}</div>
        <button class="${rec ? "primary" : "secondary"}" data-add="${m.id}" ${inCart ? "disabled" : ""}>
          ${inCart ? "In cart" : "Add to cart"}
        </button>
      </article>`;
    })
    .join("");

  // Group by category so the left column reads as a real, coffee-scoped catalog.
  const order = ["coffee", "filters", "sweetener", "creamer", "drinkware", "accessory", "maintenance"];
  const labels = {
    coffee: "Coffee", filters: "Filters", sweetener: "Sweeteners", creamer: "Creamers",
    drinkware: "Cups & mugs", accessory: "Station supplies", maintenance: "Maintenance",
  };

  $("restGroups").innerHTML = order
    .map((cat) => {
      const items = rest.filter((p) => p.category === cat);
      if (!items.length) return "";
      return `
      <section class="rest-group">
        <h3 class="rest-label">${labels[cat]}</h3>
        <div class="rest-grid">
          ${items
            .map(
              (p) => `
            <div class="rest-item" data-sku="${p.id}">
              <b>${p.short}</b>
              <div class="rest-meta"><span>${p.pack}</span><span>${money(p.price)}</span></div>
            </div>`
            )
            .join("")}
        </div>
      </section>`;
    })
    .join("");
}

// Highlight the catalog tiles the kit just picked, so the audience sees the AI
// reaching into the same catalog that is on screen.
function markKitPicks() {
  const picked = new Set(state.kit.map((i) => i.id));
  document.querySelectorAll("[data-sku]").forEach((el) => {
    el.classList.toggle("picked", picked.has(el.dataset.sku));
  });
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-add]");
  if (!btn) return;
  addToCart(btn.dataset.add, 1);
  renderCatalog();
  // Adding equipment is what wakes the kit builder up.
  if (state.byId[btn.dataset.add].category === "machine") generateKit();
});

// ---------------------------------------------------------------- cart

function addToCart(id, qty) {
  const line = state.cart.find((c) => c.id === id);
  if (line) line.qty += qty;
  else state.cart.push({ id, qty, fresh: true });
  renderCart();
}

function renderCart() {
  const el = $("cartLines");
  if (!state.cart.length) {
    el.innerHTML = `<p class="empty">Your cart is empty.</p>`;
    $("cartCount").textContent = "0";
    $("cartTotal").textContent = money(0);
    return;
  }

  let total = 0;
  el.innerHTML = state.cart
    .map((c) => {
      const p = state.byId[c.id];
      const amt = p.price * c.qty;
      total += amt;
      const fresh = c.fresh ? " new" : "";
      c.fresh = false;
      return `
      <div class="cart-line${fresh}">
        <span class="qty">${c.qty}×</span>
        <span class="nm">${p.name}</span>
        <span class="amt">${money(amt)}</span>
      </div>`;
    })
    .join("");

  $("cartCount").textContent = state.cart.reduce((n, c) => n + c.qty, 0);
  $("cartTotal").textContent = money(total);
}

// ---------------------------------------------------------------- kit stream

function stopStream() {
  if (state.abort) state.abort.abort();
  state.abort = null;
  state.streaming = false;
  clearInterval(state.timerId);
}

async function generateKit() {
  stopStream();

  const persona = currentPersona();
  state.kit = [];
  $("kitCard").hidden = false;
  $("kitBody").hidden = true;
  $("stream").innerHTML = `<div class="thought">Reading the cart<span class="caret"></span></div>`;
  $("kitItems").innerHTML = "";
  $("skipItems").innerHTML = "";
  $("kitCountLabel").textContent = "";
  $("kitTotal").textContent = money(0);
  $("skips").hidden = true;
  $("addAllBtn").disabled = true;

  const badge = $("modelBadge");
  badge.className = "model-badge thinking";
  $("modelName").textContent = state.model.model;

  const started = performance.now();
  state.timerId = setInterval(() => {
    $("timer").textContent = ((performance.now() - started) / 1000).toFixed(1) + "s";
  }, 100);

  state.abort = new AbortController();
  state.streaming = true;

  let res;
  try {
    res = await fetch("/api/kit/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: state.abort.signal,
      body: JSON.stringify({
        persona_id: persona.id,
        cart: state.cart.map((c) => ({ id: c.id, qty: c.qty })),
        scale: state.scale,
      }),
    });
  } catch (err) {
    if (err.name !== "AbortError") pushThought("Connection failed: " + err.message, true);
    stopStream();
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    let chunk;
    try {
      chunk = await reader.read();
    } catch {
      break;
    }
    if (chunk.done) break;
    buf += decoder.decode(chunk.value, { stream: true });

    let nl;
    while ((nl = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 2);
      if (frame.startsWith("data:")) handleEvent(JSON.parse(frame.slice(5).trim()));
    }
  }

  clearInterval(state.timerId);
  state.streaming = false;
  badge.classList.remove("thinking");
}

function pushThought(text, isError, detail) {
  document.querySelector(".caret")?.parentElement.remove();
  const div = document.createElement("div");
  div.className = "thought" + (isError ? " err" : "");
  div.textContent = text;
  if (detail) div.title = detail;
  $("stream").appendChild(div);
  const keep = document.createElement("div");
  keep.className = "thought";
  keep.innerHTML = `<span class="caret"></span>`;
  $("stream").appendChild(keep);
}

function handleEvent(evt) {
  switch (evt.type) {
    case "source": {
      const badge = $("modelBadge");
      badge.classList.toggle("offline", !evt.live);
      $("modelName").textContent = evt.live ? evt.model : evt.model + " (offline sample)";
      badge.title = evt.note || "";
      break;
    }

    case "thought":
      pushThought(evt.text, false);
      break;

    case "error":
      pushThought(evt.text, true, evt.detail);
      break;

    case "kit":
      document.querySelector(".caret")?.parentElement.remove();
      $("kitName").textContent = evt.name;
      $("kitSummary").textContent = evt.summary || "";
      $("kitBody").hidden = false;
      syncScaleControl();
      break;

    case "item": {
      state.kit.push(evt);
      const li = document.createElement("li");
      li.className = "kit-item";
      li.innerHTML = `
        <span class="qty">${evt.qty}×</span>
        <span>
          <div class="nm">${evt.name}</div>
          <div class="why">${evt.why || ""}</div>
        </span>
        <span>
          <div class="amt">${money(evt.line_total)}</div>
          <div class="pk">${evt.pack}</div>
        </span>`;
      $("kitItems").appendChild(li);
      updateKitTotal();
      markKitPicks();
      break;
    }

    case "skip": {
      $("skips").hidden = false;
      const li = document.createElement("li");
      li.innerHTML = `<s>${evt.short}</s> — <em>${evt.why || ""}</em>`;
      $("skipItems").appendChild(li);
      break;
    }

    case "done":
    case "end":
      document.querySelector(".caret")?.parentElement.remove();
      $("addAllBtn").disabled = state.kit.length === 0;
      // A kit with nothing left to add is the whole point: unlike a recommendation
      // widget, this one knows when the job is finished.
      if (state.kit.length === 0 && !$("kitBody").hidden) {
        $("kitItems").innerHTML = `<li class="kit-complete">Nothing missing — this station is complete.</li>`;
        $("kitCountLabel").textContent = "Complete";
        $("kitTotal").textContent = money(0);
      }
      break;
  }
}

function updateKitTotal() {
  const total = state.kit.reduce((s, i) => s + i.line_total, 0);
  $("kitTotal").textContent = money(total);
  $("kitCountLabel").textContent = `${state.kit.length} items to finish the job`;
}

// ---------------------------------------------------------------- controls

function syncScaleControl() {
  const persona = currentPersona();
  const slider = $("scale");
  // max must be widened before value, or the browser clamps a 12-person
  // business scale down to the individual persona's leftover max.
  slider.max = persona.account_type === "Business" ? 40 : 10;
  slider.value = state.scale;
  $("scaleOut").textContent =
    state.scale === 1 ? "1 person" : `${state.scale} people`;
}

$("scale").addEventListener("input", (e) => {
  state.scale = Number(e.target.value);
  $("scaleOut").textContent = state.scale === 1 ? "1 person" : `${state.scale} people`;
});

// Regenerate only once the buyer lets go of the slider - not on every pixel.
$("scale").addEventListener("change", () => generateKit());

$("regenBtn").addEventListener("click", () => generateKit());

$("addAllBtn").addEventListener("click", () => {
  state.kit.forEach((i) => addToCart(i.id, i.qty));
  $("addAllBtn").disabled = true;
  $("addAllBtn").textContent = "Added ✓";
  setTimeout(() => ($("addAllBtn").textContent = "Add kit to cart"), 1800);
  renderCatalog();
});

boot();
