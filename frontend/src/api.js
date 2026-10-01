// All fetch() wrappers live here; components never call fetch directly.
const BASE = import.meta.env.VITE_API_BASE ?? "";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`${options.method ?? "GET"} ${path} → ${res.status}`);
  return res.status === 204 ? null : res.json();
}

export const getHealth = () => request("/health");
export const listItems = () => request("/items");
export const createItem = (item) =>
  request("/items", { method: "POST", body: JSON.stringify(item) });
