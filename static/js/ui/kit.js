// The Cart-to-Complete panel: opt-in prompt, live reasoning, the two kit
// options, and the editable kit with per-line steppers.

import { esc, money, plural } from "../format.js";
import { activeKit, kitTotals, liveLines, persona, state } from "../store.js";

const el = (id) => document.getElementById(id);

const STATUS = {
  thinking: "Working out what this setup needs…",
  choosing: "Here are two ways to finish it",
  selected: "Your kit is ready",
};

/** Full re-render of everything kit-related, driven by state.phase. */
export function renderKit() {
  const machineInCart = state.cart.some((line) => {
    const p = state.byId[line.id];
    return p && p.category === "machine";
  });

  // Opt-in card: only once there is equipment to complete, and only before opting in.
  const showCta = machineInCart && state.phase === "idle";
  el("ctaCard").hidden = !showCta;
  if (showCta) renderCta();

  const showPanel = state.phase !== "idle";
  el("kitCard").hidden = !showPanel;
  if (!showPanel) return;

  el("restartBtn").hidden = state.phase === "thinking";
  renderThinking();
  renderChoices();
  renderDetail();
}

function renderCta() {
  const machine = state.cart
    .map((line) => state.byId[line.id])
    .find((p) => p && p.category === "machine");

  el("ctaCopy").textContent = machine
    ? `A ${machine.short} on its own can't make coffee. We'll work out everything else it needs, sized for you.`
    : "We'll work out everything else this setup needs, sized for you.";
  el("ctaDiscount").textContent = `${state.discount.label} off`;
}

function renderThinking() {
  const box = el("thinking");
  const visible = state.phase === "thinking" || state.thoughts.length > 0;
  box.hidden = !visible;
  if (!visible) return;

  el("thinkingStatus").textContent = STATUS[state.phase] ?? "";
  box.querySelector(".spinner").hidden = state.phase !== "thinking";

  el("thoughtList").innerHTML = state.thoughts
    .map((t) => `<li class="thought ${t.error ? "is-error" : ""}">${esc(t.text)}</li>`)
    .join("");
}

function renderChoices() {
  const show = state.phase === "choosing" && state.kits.length > 0;
  el("kitChoices").hidden = !show;
  if (!show) return;

  el("choiceGrid").innerHTML = state.kits
    .map((kit, index) => {
      const { total, saving, count, units } = kitTotals(kit, state.discount.rate);
      const thumbs = kit.items.slice(0, 5);
      const extra = kit.items.length - thumbs.length;
      return `
      <button class="choice" data-choose="${index}" style="animation-delay:${index * 90}ms">
        <span class="choice-top">
          <span class="choice-name">${esc(kit.name)}</span>
          <span class="choice-price">${money(total)}</span>
        </span>
        <span class="choice-sum">${esc(kit.summary)}</span>
        <span class="choice-thumbs">
          ${thumbs.map((i) => `<img src="${esc(i.img)}" alt="" loading="lazy">`).join("")}
          ${extra > 0 ? `<span class="choice-more">+${extra}</span>` : ""}
        </span>
        <span class="choice-foot">
          <span>${plural(count, "product")} · ${plural(units, "pack")}</span>
          <span class="choice-save">You save ${money(saving)}</span>
        </span>
      </button>`;
    })
    .join("");
}

// Identity of the currently drawn list, so quantity edits patch rows in place
// instead of rebuilding the list - which would restart the entry animations and
// destroy the very button the shopper just clicked.
let renderedKey = null;

function renderDetail() {
  const kit = activeKit();
  const show = state.phase === "selected" && kit;
  el("kitDetail").hidden = !show;
  if (!show) {
    renderedKey = null;
    return;
  }

  el("kitName").textContent = kit.name;
  el("kitSummary").textContent = kit.summary;
  el("switchKitBtn").hidden = state.kits.length < 2;

  const key = `${state.selectedKit}:${kit.items.map((i) => i.id).join(",")}`;
  if (key === renderedKey) {
    patchLines(kit);
  } else {
    el("kitItems").innerHTML = kit.items.map(itemRow).join("");
    renderedKey = key;
  }

  renderSkips();
  renderTotals(kit);

  el("addKitBtn").disabled = liveLines(kit).length === 0;
}

/** Update quantities and prices without touching the DOM structure. */
function patchLines(kit) {
  for (const item of kit.items) {
    const row = el("kitItems").querySelector(`[data-line="${cssEscape(item.id)}"]`);
    if (!row) continue;
    const removed = item.qty === 0;
    row.classList.toggle("is-removed", removed);
    row.querySelector(".count").textContent = item.qty;
    row.querySelector("[data-step='-1']").disabled = removed;
    row.querySelector(".amt").innerHTML = amountHtml(item);
  }
}

function cssEscape(value) {
  return window.CSS && CSS.escape ? CSS.escape(value) : value.replace(/"/g, '\\"');
}

function amountHtml(item) {
  if (item.qty === 0) return "Removed";
  const listed = item.unit_price * item.qty;
  const net = listed * (1 - state.discount.rate);
  return `<span class="amt-was">${money(listed)}</span>${money(net)}`;
}

function itemRow(item) {
  const removed = item.qty === 0;
  return `
    <li class="kit-item ${removed ? "is-removed" : ""}" data-line="${esc(item.id)}">
      <img class="kit-thumb" src="${esc(item.img)}" alt="" loading="lazy">
      <div>
        <div class="nm">${esc(item.name)}</div>
        <div class="why">${esc(item.why || "")}</div>
        <div class="pack">${esc(item.pack)}</div>
      </div>
      <div class="kit-item-right">
        <div class="amt">${amountHtml(item)}</div>
        <div class="stepper">
          <button data-step="-1" data-id="${esc(item.id)}" aria-label="Decrease quantity"
            ${item.qty === 0 ? "disabled" : ""}>−</button>
          <span class="count">${item.qty}</span>
          <button data-step="1" data-id="${esc(item.id)}" aria-label="Increase quantity">+</button>
        </div>
      </div>
    </li>`;
}

function renderSkips() {
  const box = el("skips");
  box.hidden = state.skips.length === 0;
  if (box.hidden) return;
  el("skipCount").textContent = state.skips.length;
  el("skipItems").innerHTML = state.skips
    .map((s) => `<li><s>${esc(s.short)}</s> — ${esc(s.why || "")}</li>`)
    .join("");
}

function renderTotals(kit) {
  const { listed, total, saving, count } = kitTotals(kit, state.discount.rate);
  el("totals").innerHTML = `
    <div class="sum-row">
      <span>${plural(count, "product")}</span><span>${money(listed)}</span>
    </div>
    <div class="sum-row is-saving">
      <span><span class="saving-flag">Kit only</span> ${esc(state.discount.label)} bundle saving</span>
      <span>−${money(saving)}</span>
    </div>
    <div class="sum-row is-total">
      <span>Kit total</span><strong>${money(total)}</strong>
    </div>`;
}
