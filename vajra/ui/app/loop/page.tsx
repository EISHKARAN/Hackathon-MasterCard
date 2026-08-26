"use client";
import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
import { pct } from "@/lib/format";

// Screen 2 — LOOP. CPRE, time-to-evade, time-to-close, SIBLING TRANSFER RECALL, the regression ledger,
// the tick timer, and the Gap Miner's plain-English escape region rendered as a sentence. Recorded ticks
// replayed; a live tick serves its LLM response from cache.
export default function Loop() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { getJSON("/loop").then(setData).catch((e) => setErr(String(e))); }, []);

  if (err) return <div className="err">Could not load LOOP: {err}. Run <span className="mono">make loop</span>.</div>;
  if (!data) return <div className="sub">loading…</div>;
  if (data.error) return <div className="notice">{data.error}</div>;

  const full = data.arms?.full;
  const ticks = full?.ticks || [];
  const lift = data.loop_lift?.comparisons || [];

  return (
    <div>
      <h1>The loop, closed <span className="badge replay">REPLAY</span></h1>
      <p className="sub">
        Gate difficulty held frozen at {data.difficulty?.toFixed(3)} so the attacker and defender cannot
        co-drift into a meaningless number. Every series below is a <b>direction of travel</b>, not an
        absolute — the cost constants and base rate are ours.
      </p>

      <h2>What each tick did (timer displayed whatever it reads)</h2>
      <table>
        <thead><tr><th>tick</th><th>wall clock</th><th>proposals</th><th>admitted</th><th>cells</th><th>escape region (plain English)</th></tr></thead>
        <tbody>
          {ticks.map((t: any) => (
            <tr key={t.tick}>
              <td>{t.tick}</td>
              <td>{t.wall_clock_seconds}s</td>
              <td>{t.n_proposals}</td>
              <td>{t.n_admitted}</td>
              <td>{t.coverage?.occupied_cells}</td>
              <td style={{ fontSize: 12, color: t.escape_region?.reportable ? "var(--text)" : "var(--muted)" }}>
                {t.escape_region?.escape_region_text}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>LOOP-LIFT and the RL ablations</h2>
      <table>
        <thead><tr><th>comparison</th><th>verdict</th></tr></thead>
        <tbody>{lift.map((r: any, i: number) => <tr key={i}><td>{r.comparison}</td><td className="mono">{r.verdict}</td></tr>)}</tbody>
      </table>
      <div className="notice honest">{data.loop_lift?.single_seed_caveat}</div>

      <h2>Sibling transfer recall — the anti-tautology number</h2>
      <p className="sub">
        Retraining on the attack you just injected and catching it is a tautology. Every closure withholds
        a <b>one-morpheme-different sibling</b> and reports recall on it at the <b>pre-retrain</b> threshold.
        The headline is the cross-cell, EVASION-mutated sibling.
      </p>
      <SiblingTable ticks={ticks} />

      {full && (
        <>
          <h2>What the attacker LEARNED (the tabular policy, rendered)</h2>
          <p className="sub">
            The Level-2 agent is tabular on purpose: you can read exactly what it learned to do in which
            situation. A deep policy would be a black box on both sides of the loop.
          </p>
          <PolicyTable rows={full.ticks?.[full.ticks.length - 1]?.rl?.policy_table || []} />
          <p className="sub" style={{ marginTop: 16 }}>{full.final_coverage?.search_claim}</p>
        </>
      )}
    </div>
  );
}

function SiblingTable({ ticks }: { ticks: any[] }) {
  const rows = ticks.map((t) => t.sibling).filter(Boolean);
  if (!rows.length) return <div className="notice">No closures recorded in this run.</div>;
  return (
    <table>
      <thead><tr><th>mutated slot</th><th>tier</th><th>closed recall</th><th>sibling recall</th><th>n</th></tr></thead>
      <tbody>
        {rows.map((s: any, i: number) => (
          <tr key={i}>
            <td className="mono">{s.mutated_slot}</td>
            <td style={{ fontSize: 12 }}>{s.tier}</td>
            <td>{s.closed_vector_recall_after_retrain?.toFixed(3)}</td>
            {/* eval emits float("nan"), which serialises to JSON null -- so Number.isNaN(null)
                is false and null?.toFixed(3) rendered an empty cell. Check for null explicitly. */}
            <td><b>{s.sibling_recall === null || s.sibling_recall === undefined ||
                     Number.isNaN(s.sibling_recall)
                       ? "n/a (no sibling positives)" : s.sibling_recall.toFixed(3)}</b></td>
            <td>{s.n_sibling_positives}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PolicyTable({ rows }: { rows: any[] }) {
  if (!rows.length) return <div className="sub">policy table empty (no states visited yet).</div>;
  return (
    <table>
      <thead><tr><th>stage</th><th>last outcome</th><th>budget</th><th>heat</th><th>best tactic</th><th>Q</th></tr></thead>
      <tbody>
        {rows.slice(0, 12).map((r: any, i: number) => (
          <tr key={i}>
            <td>{r.stage}</td><td>{r.last_outcome}</td><td>{r.budget}</td><td>{r.heat}</td>
            <td><b style={{ color: "var(--red)" }}>{r.best_tactic}</b></td>
            <td className="mono">{r.q_value?.toFixed(1)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
