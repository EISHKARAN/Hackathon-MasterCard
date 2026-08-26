"use client";
import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
import { pct, num } from "@/lib/format";

// Screen 1 — ARCHIVE. The behaviour grid: coverage over the feasible denominator, pre- and post-merge,
// with evaluations per occupied cell alongside (a cell with two executions has an "elite" only trivially).
export default function Archive() {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { getJSON("/archive").then(setD).catch((e) => setErr(String(e))); }, []);
  if (err) return <div className="err">Could not load archive: {err}. Run <span className="mono">make loop</span> then <span className="mono">make archive-report</span>.</div>;
  if (!d) return <div className="sub">loading…</div>;
  if (d.error) return <div className="notice">{d.error}</div>;
  const c = d.coverage || {};
  const dist = d.distinctness || {};
  const od = d.observable_delta?.per_slot || {};
  return (
    <div>
      <h1>Archive — diversity that is counted, not asserted</h1>
      <p className="sub">
        Coverage over a pre-declared feasible denominator, reported pre- and post-merge. The headline is
        the post-merge occupied-cell integer; the type-legal string-space size is subordinate. This number
        can go DOWN when validated — that is the point.
      </p>
      <div className="grid g3">
        <Stat label="Feasible denominator" v={c.feasible_denominator} />
        <Stat label="Pre-merge cells = elites" v={c.occupied_cells} sub={`assertion holds: ${c.occupied_equals_elites}`} />
        <Stat label="Post-merge cells" v={dist.post_merge_cells} sub={`coverage ${pct(dist.post_merge_coverage)}, can only fall`} />
        <Stat label="Coverage (all elites)" v={pct(c.coverage_all_elites)} />
        <Stat label="Coverage (solvent only)" v={pct(c.coverage_solvent_only)} />
        <Stat label="Evals / occupied cell" v={c.evaluations_per_occupied_cell_mean?.toFixed(1)} />
      </div>
      <div className="notice honest">{c.search_claim}</div>
      <h2>Per-slot observable delta</h2>
      <p className="sub">A slot that moves nothing in the feature vector is visibly credited with nothing — MONETISATION most of all.</p>
      <table>
        <thead><tr><th>slot</th><th>mean |delta|</th><th>spread across values</th></tr></thead>
        <tbody>{Object.entries(od).map(([s, x]: any) => <tr key={s}><td>{s}</td><td className="mono">{x.mean_abs_delta?.toFixed(4)}</td><td className="mono">{x.spread_across_values?.toFixed(4)}</td></tr>)}</tbody>
      </table>
      <div className="notice">{dist.note} {dist.caveat}</div>
    </div>
  );
}
function Stat({ label, v, sub }: { label: string; v: any; sub?: string }) {
  return <div className="panel"><div className="label">{label}</div><div className="stat" style={{ fontSize: 26 }}>{v ?? "n/a"}</div>{sub && <div className="sub" style={{ margin: 0, fontSize: 11 }}>{sub}</div>}</div>;
}
