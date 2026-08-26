// The dummy checkout modal: a fake card form, then a confirmation.

import { money } from "../format.js";
import { cartTotal, persona, state } from "../store.js";

const el = (id) => document.getElementById(id);

export function renderPayment() {
  const p = state.payment;
  el("paymentOverlay").hidden = !p.open;
  if (!p.open) return;

  const done = p.result !== null;
  el("paymentForm").hidden = done;
  el("paymentDone").hidden = !done;

  if (!done) {
    el("payTotal").textContent = money(cartTotal());
    const who = persona();
    if (who) el("cardName").placeholder = who.label;
    const btn = el("payBtn");
    btn.disabled = p.submitting;
    btn.textContent = p.submitting ? "Processing…" : "Buy";
    return;
  }

  if (p.result.ok) {
    const n = p.result.item_count;
    el("paymentDoneText").textContent =
      `${n} item${n === 1 ? "" : "s"} · ${money(p.result.total)}. ` +
      "We'll remember your preferences for next time you shop.";
  } else {
    el("paymentDoneText").textContent = "Something went wrong placing the order. Please try again.";
  }
}
