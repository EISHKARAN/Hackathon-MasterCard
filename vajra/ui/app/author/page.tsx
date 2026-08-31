/* AUTHOR-AN-ATTACK — the closed loop in one screen.
 * The walkthrough and the architecture are SERVER-RENDERED from the committed run, so they always
 * draw. Live authoring is a separate client island that degrades to a message if the composer
 * service is unreachable. */
import { report, num, pct } from "@/lib/reports";
import { ArchScene } from "@/components/ArchScene";
import { AuthorRunner } from "@/components/AuthorRunner";
import { Kicker, Kpi, Panel, Pipeline, Why } from "@/components/ui";
// Rendered at BUILD time. The records are committed artefacts of a finished run, not live data,
// so a snapshot is correct here and lets the whole prototype ship as one service.
export const dynamic = "force-static";

const STAGES = [
  { t: "compose", d: "six typed slots", tone: "red" as const },
  { t: "compile", d: "type-check + cell", tone: "red" as const },
  { t: "execute", d: "simulator emits messages", tone: "green" as const },
  { t: "invariant gate", d: "rail invariants", tone: "green" as const },
  { t: "score", d: "promoted model", tone: "blue" as const },
  { t: "action", d: "three-band ladder", tone: "blue" as const },
];

export default function Author() {
  const g: any = report("grammar_census.json");
  const m: any = report("metrics_issuer.json");
  const sh = m?.sealed_holdout_recall ?? {};

  return (
    <div>
      <Kicker tone="red">Screen 5 · the closed loop, in one screen</Kicker>
      <h1>Author an attack — watch how it happens, and how we catch it</h1>
      <p className="sub">
        Compose a string from the six morpheme slots. The picker is constrained to{" "}
        <b>type-valid combinations</b>, so what you author is a novel <b>composition within the
        grammar</b> rather than an unbounded new idea. It compiles, executes in the simulator, passes
        the invariant gate, and is scored against the <b>promoted</b> model.
      </p>

      <Panel tight style={{ padding: 0, overflow: "hidden", marginBottom: 14 }}>
        <div className="spread" style={{ padding: "12px 16px 0" }}>
          <span className="label">The architecture, in order</span>
          <span className="row" style={{ gap: 14 }}>
            {(["author", "simulate", "defend"] as const).map((p, i) => (
              <span key={p} className="row" style={{ gap: 6 }}>
                <i style={{ width: 8, height: 8, borderRadius: 2, display: "inline-block",
                            background: ["var(--red)", "var(--green)", "var(--blue)"][i] }} />
                <span className="mono" style={{ fontSize: 11, letterSpacing: 1, textTransform: "uppercase",
                            color: ["var(--red)", "var(--green)", "var(--blue)"][i] }}>{p}</span>
              </span>
            ))}
          </span>
        </div>
        <ArchScene phase="defend" nEvents={48}
                   outcome={{ caught_by_score: 12, routed_to_abstention: 5,
                              blocked_by_invariant: 3, approved_slipped_through: 4 }}
                   height={330} />
      </Panel>

      <Pipeline stages={STAGES} />

      <div className="grid g3">
        <Kpi label="type-legal compositions" value={num(g?.type_legal)} tone="red"
             denom={`of ${num(g?.raw_space)} raw · the rest are impossible on the rail`} />
        <Kpi label="recall on compositions never trained on" value={
               typeof sh.sealed_compositions?.recall === "number" ? sh.sealed_compositions.recall.toFixed(4) : "—"}
             tone="blue" denom={`${num(sh.sealed_compositions?.n_attacks)} attacks, never seen`} />
        <Kpi label="coverage ceiling" value={pct(g?.coverage_ceiling)} tone="amber"
             denom="the archive states its own limit" />
      </div>

      <Why>
        What you author is new to the model but inside the grammar. That is the honest bound, and the
        screen states it rather than implying open-ended novelty.
      </Why>

      <h2>Try it</h2>
      <AuthorRunner />
    </div>
  );
}
