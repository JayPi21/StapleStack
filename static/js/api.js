// Server access: bootstrap data and the kit event stream.

export async function bootstrap() {
  const res = await fetch("/api/bootstrap");
  if (!res.ok) throw new Error(`bootstrap failed (${res.status})`);
  return res.json();
}

/** Place a dummy order. The server records it so future kits for this buyer
 *  can be personalised against what they actually bought. */
export async function checkout({ personaId, cart }) {
  const res = await fetch("/api/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ persona_id: personaId, cart }),
  });
  if (!res.ok) throw new Error(`checkout failed (${res.status})`);
  return res.json();
}

/**
 * Stream kit events. Calls onEvent for each parsed SSE frame.
 * Returns an abort handle so a persona switch can cancel an in-flight run.
 */
export function streamKit({ personaId, cart, scale }, onEvent) {
  const controller = new AbortController();

  const run = async () => {
    const res = await fetch("/api/kit/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({ persona_id: personaId, cart, scale }),
    });
    if (!res.ok) throw new Error(`kit stream failed (${res.status})`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let split;
      while ((split = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, split).trim();
        buffer = buffer.slice(split + 2);
        if (!frame.startsWith("data:")) continue;
        try {
          onEvent(JSON.parse(frame.slice(5).trim()));
        } catch {
          /* ignore a malformed frame rather than killing the stream */
        }
      }
    }
  };

  return { promise: run(), abort: () => controller.abort() };
}
