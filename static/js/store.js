// A single observable state object. Views subscribe; nothing mutates state directly.

const listeners = new Set();

export const state = {
  personas: [],
  catalog: [],
  byId: {},
  discount: { rate: 0, label: "" },

  personaId: null,
  cart: [],            // [{ id, qty, isNew }]
  search: "",

  // Kit lifecycle: "idle" -> "thinking" -> "choosing" -> "selected"
  phase: "idle",
  thoughts: [],
  kits: [],            // [{ index, name, summary, items: [...] }]
  skips: [],
  selectedKit: null,   // index into kits
  aiLive: true,

  payment: { open: false, submitting: false, result: null },
};

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function commit(mutator) {
  mutator(state);
  for (const fn of listeners) fn(state);
}

// ---------------------------------------------------------------- selectors

export const persona = () => state.personas.find((p) => p.id === state.personaId);

export const product = (id) => state.byId[id];

export const activeKit = () =>
  state.selectedKit === null ? null : state.kits[state.selectedKit] ?? null;

/** Kit lines the buyer has not zeroed out. */
export const liveLines = (kit) => (kit ? kit.items.filter((i) => i.qty > 0) : []);

export function kitTotals(kit, rate) {
  const lines = liveLines(kit);
  const listed = lines.reduce((sum, i) => sum + i.unit_price * i.qty, 0);
  const total = listed * (1 - rate);
  return {
    count: lines.length,
    units: lines.reduce((sum, i) => sum + i.qty, 0),
    listed,
    total,
    saving: listed - total,
  };
}

export function cartTotal() {
  return state.cart.reduce((sum, line) => {
    const p = state.byId[line.id];
    return sum + (p ? p.price * line.qty : 0);
  }, 0);
}
