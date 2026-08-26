// Thin client over the FastAPI backend. Every screen reads committed reports through it, so the demo
// path touches only committed artifacts and works on venue wifi that does not exist.

export async function getJSON<T = any>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

export async function postJSON<T = any>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}
