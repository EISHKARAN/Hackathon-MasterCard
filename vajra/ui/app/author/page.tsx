"use client";
import { useEffect, useState } from "react";
import { getJSON, postJSON } from "@/lib/api";
import { score, pct } from "@/lib/format";

// Screen 5 — AUTHOR-AN-ATTACK. THE screen that shows HOW THE ATTACK HAPPENED AND HOW WE IDENTIFIED IT.
// A stranger composes a grammar string from the six morpheme slots against a guided picker constrained
// to type-valid combinations; it compiles, executes in the simulator, passes the invariant gate, and is
// scored LIVE against the FROZEN endpoint. The result splits into caught-by-score / routed-to-abstention
// / blocked-by-invariant, with the pinned model version shown so a judge sees it is not the model we
// just retrained.
const SLOT_ORDER = ["ACCESS", "TRUST", "RAIL", "EVASION", "MONETISATION", "LABEL"];

export default function Author() {
  const [picker, setPicker] = useState<any>(null);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [legal, setLegal] = useState<Record<string, string[]>>({});
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    getJSON("/picker").then((p) => {
      setPicker(p);
      const init: Record<string, string> = {};
      for (const s of p.slots) init[s.slot] = s.values[0].id;
      setChoice(init);
    }).catch((e) => setErr(String(e)));
  }, []);

  // As each slot is chosen, refresh which morphemes keep the composition type-legal, so what a judge
  // authors always compiles — the bound the screen states out loud.
  useEffect(() => {
    if (!picker) return;
    (async () => {
      const next: Record<string, string[]> = {};
      for (const s of SLOT_ORDER) {
        const r = await postJSON("/legal-next", { partial: choice, slot: s });
        next[s] = r.legal;
      }
      setLegal(next);
    })().catch(() => {});
  }, [choice, picker]);

  const grammar = SLOT_ORDER.map((s) => `${s}=${choice[s] || ""}`).join("/");

  async function run() {
    setBusy(true); setResult(null); setErr("");
    try {
      setResult(await postJSON("/author-attack", { grammar_str: grammar, view: "issuer" }));
    } catch (e) { setErr(String(e)); }
    setBusy(false);
  }

  if (err && !picker) return <div className="err">Could not load the picker: {err}. Run <span className="mono">make train</span> then <span className="mono">make api</span>.</div>;
  if (!picker) return <div className="sub">loading…</div>;

  const outcome = result?.outcome;
  return (
    <div>
      <h1>Author an attack — watch how it happens, and how we catch it</h1>
      <p className="sub">
        Compose a grammar string from the six morpheme slots. The picker is constrained to <b>type-valid
        combinations</b>, so what you author is a novel <b>composition within our grammar</b>, not an
        unbounded new idea. It compiles, executes in the simulator, passes the invariant gate, and is
        scored live against the <b>currently promoted</b> model, named on the result badge.
      </p>

      <div className="panel">
        {picker.slots.map((s: any) => {
          const allowed = legal[s.slot];
          const isRed = s.slot === "ACCESS";
          const isAmber = s.slot === "EVASION";
          return (
            <div key={s.slot} style={{ marginBottom: 10 }}>
              <span className="label" style={{ display: "inline-block", width: 130 }}>{s.slot}</span>
              <select
                value={choice[s.slot] || ""}
                onChange={(e) => setChoice({ ...choice, [s.slot]: e.target.value })}
                style={{ minWidth: 340, borderColor: isRed ? "var(--red)" : isAmber ? "var(--amber)" : undefined }}
              >
                {s.values.map((v: any) => {
                  const ok = !allowed || allowed.includes(v.id);
                  return <option key={v.id} value={v.id} disabled={!ok}>{v.label}{ok ? "" : " — would not type-check"}</option>;
                })}
              </select>
            </div>
          );
        })}
        <div className="mono" style={{ margin: "12px 0", color: "var(--muted)" }}>{grammar}</div>
        <button onClick={run} disabled={busy}>{busy ? "compiling · executing · scoring…" : "Run it against the gate"}</button>
      </div>

      {err && <div className="err" style={{ marginTop: 12 }}>{err}</div>}

      {result && (
        <div style={{ marginTop: 20 }}>
          <h2>1 · Did it compile?</h2>
          {result.compiled.ok ? (
            <p className="sub">
              <span className="badge pass">TYPE-LEGAL</span> occupies archive cell{" "}
              <span className="mono">{result.compiled.cell_id}</span> · resolves{" "}
              {result.compiled.signatures.length} observable signatures to schema fields.
            </p>
          ) : (
            <div className="notice">
              <span className="badge fail">REJECTED</span> {result.compiled.reasons?.join("; ")}
              <div style={{ marginTop: 6 }}>A rejection is an explanation, not a red cross — the grammar
              told you exactly which pairwise constraint the composition violates.</div>
            </div>
          )}

          {result.stage === "scored" && (
            <>
              <h2>2 · How the attack happened</h2>
              <p className="sub">
                {result.n_events_generated} events generated in the simulator · invariant gate:{" "}
                <span className={`badge ${result.f1.passed ? "pass" : "fail"}`}>
                  {result.f1.violations} F1 violations
                </span>{" "}
                — structurally legal payment messages, not rows.
              </p>

              <h2>3 · How we identified it <span className="badge replay">scored by: {result.model_version}</span></h2>
              <div className="grid g2">
                <div className="panel">
                  <div className="label">Outcome split</div>
                  <table>
                    <tbody>
                      <tr><td>caught by score</td><td><b style={{ color: "var(--green)" }}>{outcome.caught_by_score}</b></td></tr>
                      <tr><td>routed to abstention (friction, not decline)</td><td><b style={{ color: "var(--purple)" }}>{outcome.routed_to_abstention}</b></td></tr>
                      <tr><td>blocked by invariant guard (G0)</td><td><b style={{ color: "var(--blue)" }}>{outcome.blocked_by_invariant}</b></td></tr>
                      <tr><td>slipped through</td><td><b style={{ color: "var(--red)" }}>{outcome.approved_slipped_through}</b></td></tr>
                      <tr><td><b>total</b></td><td><b>{outcome.total_events}</b>{" "}
                        {outcome.buckets_sum_to_total
                          ? <span className="badge pass">rows sum to total</span>
                          : <span className="badge fail">DOES NOT SUM</span>}</td></tr>
                    </tbody>
                  </table>
                  <div className="sub" style={{ marginTop: 8 }}>{outcome.note}</div>
                </div>
                <div className="panel">
                  <div className="label">Per-event score trace (real calls, real latency)</div>
                  <table>
                    <thead><tr><th>score</th><th>band</th><th>conformal p</th><th>why</th></tr></thead>
                    <tbody>
                      {result.score_trace_sample.map((t: any, i: number) => (
                        <tr key={i}>
                          <td className="mono">{score(t.score)}</td>
                          <td><span className={`pill ${t.band}`}>{t.band}</span></td>
                          <td className="mono">{score(t.conformal_p)}</td>
                          <td style={{ fontSize: 11 }}>{(t.reason_texts || []).slice(0, 2).join("; ") || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <p className="sub" style={{ marginTop: 12 }}>
                end-to-end {Math.round(result.elapsed_ms)} ms · {result.elapsed_note}
              </p>
              <div className="notice honest">{result.bound_statement}</div>
            </>
          )}
          {result.stage !== "scored" && result.stage !== "compile" && (
            <div className="notice">{result.reason}</div>
          )}
        </div>
      )}
    </div>
  );
}
