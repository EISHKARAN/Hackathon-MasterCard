"use client";
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { getJSON, postJSON } from "@/lib/api";
import { score, pct } from "@/lib/format";
import {
  Badge, Kicker, Kpi, Morphemes, Notice, Panel, Pipeline, Step, Tech, Why,
} from "@/components/ui";

// SERVER-RENDERED ON PURPOSE. The scene is pure SVG with no browser API, so the diagram ships in the
// HTML: it draws even if client JS fails, and its markup can be verified with curl. The WebGL version
// had to be ssr:false, which is precisely why four broken renders were invisible to every check.
const ArchScene = dynamic(() => import("@/components/ArchScene").then((m) => m.ArchScene), {
  ssr: true,
});

// Screen 5 — AUTHOR-AN-ATTACK. THE screen that shows HOW THE ATTACK HAPPENED AND HOW WE IDENTIFIED
// IT. A stranger composes a grammar string from the six morpheme slots against a guided picker
// constrained to type-valid combinations; it compiles, executes in the simulator, passes the
// invariant gate, and is scored LIVE against the FROZEN endpoint. The result splits into
// caught-by-score / routed-to-abstention / blocked-by-invariant, with the pinned model version shown
// so a judge sees it is not the model we just retrained.
//
// The composition renders as TYPED CHIPS rather than a string. A grammar string is data; chips are a
// structure, and the whole diversity claim rests on the composition being structured.
const SLOT_ORDER = ["ACCESS", "TRUST", "RAIL", "EVASION", "MONETISATION", "LABEL"];

const STAGES = [
  { t: "compose", d: "six typed slots", tone: "red" as const },
  { t: "compile", d: "type-check + cell", tone: "red" as const },
  { t: "execute", d: "simulator emits messages", tone: "green" as const },
  { t: "invariant gate", d: "126 F1 rail invariants", tone: "green" as const },
  { t: "score", d: "frozen promoted model", tone: "blue" as const },
  { t: "action", d: "three-band ladder", tone: "blue" as const },
];

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

  if (err && !picker)
    return (
      <Notice kind="bad">
        Could not load the picker: {err}. Run <span className="mono">make train</span> then{" "}
        <span className="mono">make api</span>.
      </Notice>
    );

  const outcome = result?.outcome;
  // The 3D walkthrough runs AUTHOR -> SIMULATE -> DEFEND. It advances with the real run: composing
  // is AUTHOR, a successful compile-and-execute is SIMULATE, and a scored result is DEFEND.
  const phase: "idle" | "author" | "simulate" | "defend" =
    busy ? "simulate"
    : result?.stage === "scored" ? "defend"
    : result ? "simulate"
    : "author";
  const stageIdx = !result ? 0
    : result.stage === "compile" ? 1
    : result.stage === "scored" ? 5 : 3;

  // How many of this slot's morphemes remain type-legal — the pruning IS the type system working.
  const legalCount = (slot: string, total: number) =>
    legal[slot] ? `${legal[slot].length}/${total}` : `${total}/${total}`;

  return (
    <div>
      <Kicker tone="red">Screen 5 · the closed loop, in one screen</Kicker>
      <h1>Author an attack — watch how it happens, and how we catch it</h1>
      <p className="sub">
        Compose a grammar string from the six morpheme slots. The picker is constrained to{" "}
        <b>type-valid combinations</b>, so what you author is a novel <b>composition within our
        grammar</b>, not an unbounded new idea. It compiles, executes in the simulator, passes the
        invariant gate, and is scored live against the <b>currently promoted</b> model, named on the
        result badge.
      </p>

      {/* The architecture, split into its three pillars and lit in order. The packet stream and
          the four outcome lanes are driven by the REAL run — event count and outcome split — so the
          picture cannot flatter the result: if the model misses, the red lane is visibly tall. */}
      <Panel tight style={{ padding: 0, overflow: "hidden", marginBottom: 14 }}>
        <div className="spread" style={{ padding: "12px 16px 0" }}>
          <span className="label">The architecture, in order</span>
          <span className="row" style={{ gap: 14 }}>
            {([["author", "red"], ["simulate", "green"], ["defend", "blue"]] as const).map(([p, c]) => (
              <span key={p} className="row" style={{ gap: 6 }}>
                <i style={{
                  width: 8, height: 8, borderRadius: 2, display: "inline-block",
                  background: `var(--${c})`,
                  opacity: phase === p ? 1 : 0.28,
                  boxShadow: phase === p ? `0 0 0 3px color-mix(in srgb, var(--${c}) 18%, transparent)` : "none",
                }} />
                <span className="mono" style={{
                  fontSize: 11, letterSpacing: 1, textTransform: "uppercase",
                  color: phase === p ? `var(--${c})` : "var(--faint)",
                }}>{p}</span>
              </span>
            ))}
          </span>
        </div>
        <ArchScene
          phase={phase}
          nEvents={result?.n_events_generated ?? 0}
          outcome={outcome}
          height={340}
        />
      </Panel>

      <Pipeline stages={STAGES} active={stageIdx} />

      <div className="grid g-2-1">
        <Panel accent="red">
          <div className="spread" style={{ marginBottom: 14 }}>
            <span className="label">Compose the composition</span>
            <span className="badge info">picker pruned to type-legal</span>
          </div>

          {!picker && (
            <Notice kind="bad">
              Waiting on <span className="mono">/api/picker</span>. If this persists the backend is
              not up — run <span className="mono">make api</span>. The architecture above needs no
              data and is drawn regardless.
            </Notice>
          )}

          {(picker?.slots ?? []).map((s: any) => {
            const allowed = legal[s.slot];
            const tone = s.slot === "ACCESS" ? "var(--red)"
              : s.slot === "EVASION" ? "var(--amber)"
              : s.slot === "RAIL" ? "var(--blue)"
              : s.slot === "MONETISATION" ? "var(--purple)" : undefined;
            return (
              <div key={s.slot} className="row" style={{ marginBottom: 9 }}>
                <span className="label" style={{ width: 118, flex: "0 0 118px" }}>{s.slot}</span>
                <select
                  value={choice[s.slot] || ""}
                  onChange={(e) => setChoice({ ...choice, [s.slot]: e.target.value })}
                  style={{ minWidth: 330, borderColor: tone }}
                >
                  {s.values.map((v: any) => {
                    const ok = !allowed || allowed.includes(v.id);
                    return (
                      <option key={v.id} value={v.id} disabled={!ok}>
                        {v.label}{ok ? "" : " — would not type-check"}
                      </option>
                    );
                  })}
                </select>
                <span className="mono" style={{ color: "var(--faint)", fontSize: 11 }}>
                  {legalCount(s.slot, s.values.length)} legal
                </span>
              </div>
            );
          })}

          <div style={{ margin: "16px 0 6px" }}>
            <span className="label">the composition, as a typed sentence</span>
          </div>
          <Morphemes choice={choice} order={SLOT_ORDER} />
          <div className="code" style={{ marginTop: 12 }}>{grammar}</div>

          <div className="row" style={{ marginTop: 14 }}>
            <button onClick={run} disabled={busy} className={busy ? "" : "go"}>
              {busy ? "compiling · executing · scoring…" : "Run it against the gate"}
            </button>
            <span className="mono" style={{ color: "var(--faint)", fontSize: 11 }}>
              scores against the frozen promoted bundle, not a model retrained for this demo
            </span>
          </div>
        </Panel>

        <Panel>
          <span className="label">Why this is bounded</span>
          <Why>
            The grammar admits <b>15,271 type-legal compositions</b> out of 188,160 raw strings. The
            rest are rejected because they are physically impossible on the rail — a beneficiary leg
            on AePS, which terminates in cash. So the picker cannot produce an illegal message, and a
            rejection is an explanation rather than an error.
          </Why>
          <Why>
            What you author is <b>new to the model</b> but <b>inside our grammar</b>. That is the
            honest bound, and the screen states it rather than implying open-ended novelty.
          </Why>
          <Tech items={[
            ["slots", "6"],
            ["type-legal", <span className="mono">15,271</span>],
            ["archive cells", <span className="mono">268/380</span>],
            ["view", "issuer"],
          ]} />
        </Panel>
      </div>

      {err && <Notice kind="bad">{err}</Notice>}

      {result && (
        <div style={{ marginTop: 8 }}>
          <Step n={1} title="Did it compile?" tone={result.compiled.ok ? "green" : "red"} />
          {result.compiled.ok ? (
            <Panel tight>
              <div className="row">
                <Badge kind="pass">type-legal</Badge>
                <span className="sub" style={{ margin: 0 }}>
                  occupies archive cell <span className="mono">{result.compiled.cell_id}</span> ·
                  resolves <b>{result.compiled.signatures.length}</b> observable signatures to schema
                  fields.
                </span>
              </div>
            </Panel>
          ) : (
            <Notice kind="bad">
              <div className="row" style={{ marginBottom: 6 }}>
                <Badge kind="fail">rejected</Badge>
                <span>{result.compiled.reasons?.join("; ")}</span>
              </div>
              A rejection is an explanation, not a red cross — the grammar told you exactly which
              pairwise constraint the composition violates.
            </Notice>
          )}

          {result.stage === "scored" && (
            <>
              <Step n={2} title="How the attack happened" tone="green" />
              <div className="grid g4">
                <Kpi label="events generated" value={result.n_events_generated} tone="green"
                     denom="structurally legal payment messages, not rows" />
                <Kpi label="F1 invariant gate" tone={result.f1.passed ? "green" : "red"}
                     value={result.f1.violations}
                     denom={result.f1.passed ? "violations — gate passed" : "violations — gate FAILED"} />
                <Kpi label="signatures resolved" value={result.compiled.signatures.length} tone="blue"
                     denom="observables mapped to schema fields" />
                <Kpi label="end to end" value={`${Math.round(result.elapsed_ms)} ms`} tone="blue"
                     denom={result.elapsed_note} />
              </div>

              <Step n={3} title="How we identified it" tone="blue" />
              <Tech items={[
                ["scored by", <span className="mono">{result.model_version}</span>],
                ["endpoint", "frozen · promoted"],
                ["truth", "oracle attack labels"],
                ["latency", <span className="mono">{Math.round(result.elapsed_ms)} ms</span>],
              ]} />

              <div className="grid g2">
                <Panel accent="blue">
                  <div className="spread" style={{ marginBottom: 10 }}>
                    <span className="label">Outcome split</span>
                    {outcome.buckets_sum_to_total
                      ? <Badge kind="pass">rows sum to total</Badge>
                      : <Badge kind="fail">does not sum</Badge>}
                  </div>
                  <div className="tbl-wrap">
                    <table>
                      <tbody>
                        <tr><td>caught by score</td>
                            <td className="num" style={{ color: "var(--green)", fontWeight: 700 }}>{outcome.caught_by_score}</td></tr>
                        <tr><td>routed to abstention <span style={{ color: "var(--faint)" }}>(friction, not decline)</span></td>
                            <td className="num" style={{ color: "var(--purple)", fontWeight: 700 }}>{outcome.routed_to_abstention}</td></tr>
                        <tr><td>blocked by invariant guard (G0)</td>
                            <td className="num" style={{ color: "var(--blue)", fontWeight: 700 }}>{outcome.blocked_by_invariant}</td></tr>
                        <tr><td>slipped through</td>
                            <td className="num" style={{ color: "var(--red)", fontWeight: 700 }}>{outcome.approved_slipped_through}</td></tr>
                        <tr><td><b>total</b></td><td className="num"><b>{outcome.total_events}</b></td></tr>
                      </tbody>
                    </table>
                  </div>
                  <Why>{outcome.note}</Why>
                </Panel>

                <Panel accent="blue">
                  <div className="spread" style={{ marginBottom: 10 }}>
                    <span className="label">Per-event score trace</span>
                    <span className="badge info">real calls · real latency</span>
                  </div>
                  <div className="tbl-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th className="num">score</th><th>band</th>
                          <th className="num">conformal p</th><th>why</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.score_trace_sample.map((t: any, i: number) => (
                          <tr key={i}>
                            <td className="num">{score(t.score)}</td>
                            <td><span className={`pill ${t.band}`}>{String(t.band).replace(/_/g, " ")}</span></td>
                            <td className="num">{score(t.conformal_p)}</td>
                            <td style={{ fontSize: 11, color: "var(--muted)" }}>
                              {(t.reason_texts || []).slice(0, 2).join("; ") || "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <Why>
                    The <b>why</b> column is the reason code the decision actually carried — one of 54
                    in a fixed vocabulary. A score without an explanation is not an action an issuer
                    can take.
                  </Why>
                </Panel>
              </div>

              <Notice kind="honest">{result.bound_statement}</Notice>
            </>
          )}

          {result.stage !== "scored" && result.stage !== "compile" && (
            <Notice>{result.reason}</Notice>
          )}
        </div>
      )}
    </div>
  );
}
