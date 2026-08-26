// The account switcher. Selecting a buyer resets the demo to a clean slate.

import { esc } from "../format.js";
import { state } from "../store.js";

const el = (id) => document.getElementById(id);

export function renderPersonas(onSelect) {
  el("personaSwitch").innerHTML = state.personas
    .map(
      (p) => `
      <button class="persona-btn" role="tab" data-persona="${esc(p.id)}" aria-selected="false">
        <span class="avatar">${esc(p.initials)}</span>
        <span class="persona-meta">
          <b>${esc(p.label)}</b>
          <span>${esc(p.account_type)} · ${esc(p.headcount_label)}</span>
        </span>
      </button>`
    )
    .join("");

  el("personaSwitch").addEventListener("click", (event) => {
    const button = event.target.closest("[data-persona]");
    if (button) onSelect(button.dataset.persona);
  });
}

export function markSelectedPersona() {
  document.querySelectorAll("[data-persona]").forEach((node) => {
    node.setAttribute("aria-selected", String(node.dataset.persona === state.personaId));
  });
}
