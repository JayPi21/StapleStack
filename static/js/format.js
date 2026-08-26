// Presentation helpers shared across views.

export const money = (n) => "$" + Number(n || 0).toFixed(2);

export const plural = (n, one, many = one + "s") => `${n} ${n === 1 ? one : many}`;

/** Escape text before it reaches innerHTML. */
export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}
