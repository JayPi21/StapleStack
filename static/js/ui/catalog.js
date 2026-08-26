// Catalog rendering: hero machines, grouped product tiles, and kit-only filtering.

import { esc, money } from "../format.js";
import { activeKit, liveLines, persona, state } from "../store.js";

const CATEGORY_ORDER = [
  "coffee", "filters", "sweetener", "creamer", "drinkware", "accessory", "maintenance", "ink", "paper",
];
const CATEGORY_LABEL = {
  coffee: "Coffee",
  filters: "Filters",
  sweetener: "Sweeteners",
  creamer: "Creamers",
  drinkware: "Cups & lids",
  accessory: "Station supplies",
  maintenance: "Maintenance",
  ink: "Ink & toner",
  paper: "Paper",
};

const el = (id) => document.getElementById(id);

export function renderCatalog() {
  const who = persona();
  const kit = activeKit();
  // Once a kit is chosen the shopper only wants to see that kit.
  const focusIds = kit ? new Set(liveLines(kit).map((i) => i.id)) : null;
  // Nothing to browse below the machines until a kit has been built at least once,
  // unless the shopper is actively searching for something specific.
  const hasKit = state.kits.length > 0;
  const search = state.search.trim().toLowerCase();

  renderMachines(who, focusIds, search);
  renderGroups(focusIds, hasKit, search);
  renderFilterNote(kit, focusIds, search);
}

const matches = (p, search) =>
  !search || p.name.toLowerCase().includes(search) || (p.tags || []).some((t) => t.includes(search));

function renderMachines(who, focusIds, search) {
  let machines = state.catalog.filter((p) => p.category === "machine");
  machines = search
    ? machines.filter((p) => matches(p, search))
    : machines.filter((p) => !focusIds || focusIds.has(p.id) || state.cart.some((c) => c.id === p.id));

  el("machines").innerHTML = machines
    .map((m) => {
      const recommended = who && m.id === who.recommended_machine;
      const inCart = state.cart.some((c) => c.id === m.id);
      const firstName = who ? esc(who.label.split(" ")[0]) : "";
      const demo = (m.tags || []).includes("placeholder");
      return `
      <article class="machine ${recommended ? "is-recommended" : ""}">
        ${recommended ? `<span class="rec-badge">Recommended for ${firstName}</span>` : ""}
        ${demo ? `<span class="demo-badge">Demo item</span>` : ""}
        <div class="machine-art"><img src="${esc(m.img)}" alt="${esc(m.name)}" loading="lazy"></div>
        <h3>${esc(m.name)}</h3>
        <div class="spec">${esc(m.spec || "")}</div>
        <div class="price">${money(m.price)}</div>
        <button class="${recommended ? "primary-btn" : "secondary-btn"}"
                data-add="${esc(m.id)}" ${inCart ? "disabled" : ""}>
          ${inCart ? "In your cart" : "Add to cart"}
        </button>
      </article>`;
    })
    .join("");
}

function renderGroups(focusIds, hasKit, search) {
  const searching = search.length > 0;
  if (!hasKit && !searching) {
    el("catalogRest").hidden = true;
    el("restGroups").innerHTML = "";
    return;
  }

  let rest = state.catalog.filter((p) => p.category !== "machine");
  rest = searching ? rest.filter((p) => matches(p, search)) : rest.filter((p) => !focusIds || focusIds.has(p.id));

  el("restCount").textContent = rest.length;
  el("catalogRest").hidden = rest.length === 0;

  const inKit = new Set(
    liveLines(activeKit()).map((i) => i.id)
  );

  el("restGroups").innerHTML = CATEGORY_ORDER.map((category) => {
    const items = rest.filter((p) => p.category === category);
    if (!items.length) return "";
    return `
      <section class="rest-group">
        <h3 class="rest-label">${CATEGORY_LABEL[category] ?? category}</h3>
        <div class="rest-grid">
          ${items.map((p) => tile(p, inKit.has(p.id))).join("")}
        </div>
      </section>`;
  }).join("");
}

function tile(p, highlighted) {
  const inCart = state.cart.some((c) => c.id === p.id);
  const demo = (p.tags || []).includes("placeholder");
  return `
    <div class="rest-item ${highlighted ? "is-in-kit" : ""}" data-sku="${esc(p.id)}">
      <img class="rest-thumb" src="${esc(p.img)}" alt="" loading="lazy">
      <div class="rest-text">
        <b>${esc(p.short)}${demo ? ` <span class="demo-tag">Demo</span>` : ""}</b>
        <div class="rest-meta"><span>${esc(p.pack)}</span><span>${money(p.price)}</span></div>
      </div>
      <button class="rest-add" data-add="${esc(p.id)}" aria-label="Add ${esc(p.short)} to cart" ${inCart ? "disabled" : ""}>
        ${inCart ? "✓" : "+"}
      </button>
    </div>`;
}

function renderFilterNote(kit, focusIds, search) {
  const note = el("kitFilterNote");
  const showAll = el("showAllBtn");

  if (search) {
    note.hidden = true;
    showAll.hidden = true;
    el("catalogTitle").textContent = `Results for "${state.search.trim()}"`;
    el("catalogSub").textContent = "Matching products from your contract";
    return;
  }

  if (!kit || !focusIds) {
    note.hidden = true;
    showAll.hidden = true;
    el("catalogTitle").textContent = "Coffee";
    el("catalogSub").textContent = `${state.catalog.length} products on your contract`;
    return;
  }

  const count = focusIds.size;
  note.hidden = false;
  showAll.hidden = false;
  el("kitFilterText").innerHTML =
    `Showing the <strong>${esc(kit.name)}</strong> kit only — ${count} item${count === 1 ? "" : "s"} from your contract.`;
  el("catalogTitle").textContent = kit.name;
  el("catalogSub").textContent = "Everything needed to finish this setup";
}

/** Highlight tiles belonging to the kit without a full re-render. */
export function markKitTiles() {
  const inKit = new Set(liveLines(activeKit()).map((i) => i.id));
  document.querySelectorAll("[data-sku]").forEach((node) => {
    node.classList.toggle("is-in-kit", inKit.has(node.dataset.sku));
  });
}
