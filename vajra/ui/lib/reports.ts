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

/**
 * WHERE THE EVIDENCE LIVES, in priority order.
 *
 *   1.  `<cwd>/reports`      a copy made INSIDE the deployed tree by the prebuild step. This is the
 *                            only candidate that survives serverless bundling, where the repository
 *                            root is not on the filesystem at request time.
 *   2.  `$VAJRA_ROOT/...`    an explicit override, for containers that mount the evidence somewhere
 *                            of their own choosing rather than beside the interface.
 *   3.  `<cwd>/../...`       the repository layout, which is what a local checkout and `make demo`
 *                            both have.
 *
 * Candidate 1 exists because of a specific failure: the deployed interface is built with the
 * interface directory as its root, so `..` is the container root and holds no evidence at all. The
 * screens would then render their absent-artefact fallback on every page, which looks like a broken
 * pipeline rather than a misconfigured path.
 */
const ENV_ROOT = process.env.VAJRA_ROOT;
const SEARCH_ROOTS = [
  path.join(process.cwd(), "reports"),
  ...(ENV_ROOT ? [path.join(ENV_ROOT, "reports"), path.join(ENV_ROOT, "bundles", "replay")] : []),
  path.resolve(process.cwd(), "..", "reports"),
  path.resolve(process.cwd(), "..", "bundles", "replay"),
];

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
  for (const dir of SEARCH_ROOTS) {
    const p = path.join(dir, name);
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
    let bytes = 0, ok = false;
    for (const dir of SEARCH_ROOTS) {
      try { bytes = fs.statSync(path.join(dir, n)).size; ok = true; break; } catch { /* next */ }
    }
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
