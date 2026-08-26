// Cart lines and the running order summary.

import { esc, money } from "../format.js";
import { cartTotal, product, state } from "../store.js";

const el = (id) => document.getElementById(id);

export function renderCart() {
  const lines = el("cartLines");
  el("checkoutBtn").disabled = state.cart.length === 0;

  if (!state.cart.length) {
    lines.innerHTML = `<p class="cart-empty">Nothing in your cart yet.</p>`;
    el("cartCount").textContent = "0";
    el("cartSummary").innerHTML = row("Subtotal", money(0), "is-total", true);
    return;
  }

  lines.innerHTML = state.cart
    .map((line) => {
      const p = product(line.id);
      if (!p) return "";
      const wasNew = line.isNew;
      line.isNew = false;
      return `
        <div class="cart-line ${wasNew ? "is-new" : ""}">
          <span class="qty">${line.qty}×</span>
          <img class="cart-thumb" src="${esc(p.img)}" alt="" loading="lazy">
          <span class="nm">${esc(p.name)}</span>
          <span class="amt">${money(p.price * line.qty)}</span>
        </div>`;
    })
    .join("");

  const units = state.cart.reduce((sum, l) => sum + l.qty, 0);
  el("cartCount").textContent = units;

  const gross = cartTotal();
  const saved = state.cart.reduce((sum, l) => sum + (l.savedTotal || 0), 0);

  el("cartSummary").innerHTML =
    (saved > 0
      ? row("Items", money(gross), "") +
        row(`Kit bundle saving (${esc(state.discount.label)})`, "−" + money(saved), "is-saving")
      : "") +
    row("Subtotal", money(gross - saved), "is-total", true);
}

function row(label, value, className = "", strong = false) {
  const shown = strong ? `<strong>${value}</strong>` : value;
  return `<div class="sum-row ${className}"><span>${label}</span>${shown}</div>`;
}
