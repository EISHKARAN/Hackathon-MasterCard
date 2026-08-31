/* Server-side report loader.
 *
 * WHY THIS EXISTS. Every screen previously fetched its data from the browser through a proxy to the
 * backend. That chain has four independent ways to fail — the service dying, Node resolving localhost
 * to IPv6 against an IPv4-only bind, a stale client bundle, and a hydration error — and all four
 * present identically as a loading skeleton that never resolves. The screens are read-only views over
 * JSON that already sits on disk, so they read it directly on the server. No fetch, no proxy, no
 * client state. If the JSON is on disk, the screen renders.
 */
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(process.cwd(), "..");

/**
 * Python's json module emits bare NaN / Infinity, which are NOT valid JSON and which JSON.parse
 * rejects outright — one such value anywhere in a file blanks the whole screen. This rewrites them
 * to null in value position only, so a report containing one undefined statistic still renders with
 * that single field showing as absent.
 */
function sanitise(s: string): string {
  return s
    .replace(/([:[,]\s*)-?NaN(\s*[,}\]])/g, "$1null$2")
    .replace(/([:[,]\s*)-?Infinity(\s*[,}\]])/g, "$1null$2");
}

export function report<T = any>(name: string): T | null {
  for (const p of [path.join(ROOT, "reports", name), path.join(ROOT, "bundles", "replay", name)]) {
    try {
      if (fs.existsSync(p)) return JSON.parse(sanitise(fs.readFileSync(p, "utf8"))) as T;
    } catch { /* fall through to the next candidate */ }
  }
  return null;
}

/** Which artifacts are present, for the fallback panel when a report is absent. */
export function inventory(): Array<{ name: string; ok: boolean; bytes: number }> {
  return ["money.json", "metrics_issuer.json", "loop_report.json", "archive_report.json",
          "fidelity.json", "grammar_census.json", "train_report_issuer.json"].map((n) => {
    const p = path.join(ROOT, "reports", n);
    let bytes = 0, ok = false;
    try { const s = fs.statSync(p); bytes = s.size; ok = true; } catch { /* absent */ }
    return { name: n.replace(".json", ""), ok, bytes };
  });
}

export const num = (v: any, d = 0) =>
  typeof v === "number" && isFinite(v) ? v.toLocaleString("en-IN", { maximumFractionDigits: d }) : "—";
export const pct = (v: any, d = 2) =>
  typeof v === "number" && isFinite(v) ? `${(v * 100).toFixed(d)}%` : "—";
export const sig = (v: any, d = 4) =>
  typeof v === "number" && isFinite(v) ? v.toFixed(d) : "—";
export const rupees = (v: any) => {
  if (typeof v !== "number" || !isFinite(v)) return "—";
  if (v >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`;
  if (v >= 1e5) return `₹${(v / 1e5).toFixed(2)} L`;
  return `₹${Math.round(v).toLocaleString("en-IN")}`;
};
