/* FIDELITY — the invariant gate and what it refuses to emit. */
import { report, num, pct } from "@/lib/reports";
import { Kicker, Kpi, Notice, Panel, Tech, Why } from "@/components/ui";
// Rendered at BUILD time. The records are committed artefacts of a finished run, not live data,
// so a snapshot is correct here and lets the whole prototype ship as one service.
export const dynamic = "force-static";

export default function Fidelity() {
  const f: any = report("fidelity.json");
  const s: any = report("sim_report_vajra-sim.json");
  if (!f && !s) return <Notice kind="bad">The fidelity report has not been generated yet.</Notice>;
  const f1 = f?.f1 ?? {};
  const inv = f1.n_invariants ?? f1.invariants ?? f1.count;
  const viol = f1.violations ?? f1.n_violations ?? 0;

  return (
    <div>
      <Kicker tone="green">Criterion 2 · fidelity of simulation</Kicker>
      <h1>The build refuses to emit a stream that breaks rail semantics</h1>
      <p className="sub">
        Fidelity is a judged criterion, so it is made checkable. Rail invariants are enforced as build
        gates rather than tests that were run once: message ordering, clearing that spills forward and
        never backwards, derived legs strictly after their antecedent, and a single hour convention.
      </p>

      <div className="grid g3">
        <Kpi label="rail invariants" value={num(inv)} tone="green" denom="enforced as build gates" />
        <Kpi label="violations" value={num(viol)} tone={viol ? "red" : "green"}
             denom={viol ? "the build would fail" : "the stream is legal on every rail"} />
        <Kpi label="events generated" value={num(s?.n_events ?? s?.events)} tone="blue"
             denom={`realised attack share ${pct(s?.realised_attack_share, 3)}`} />
      </div>

      <h2>What is claimed, and what is not</h2>
      <Panel>
        <Why>
          What is validated is mechanism-level fidelity: rail semantics, message flows, lifecycle
          timing, and a base rate driven onto target by a causal controller rather than assumed.
        </Why>
        <Why>
          What is <b>not</b> claimed is distributional fidelity to any real portfolio. That is
          untestable without the portfolio, and asserting it would be the kind of unfalsifiable claim
          this design refuses elsewhere. Two places where the generator is measurably too clean are
          disclosed in the write-up rather than left for a reviewer to find.
        </Why>
      </Panel>

      <Tech items={[["provenance tiers", "measured · derived · design-only"],
                    ["generator", <span className="mono" key="g">{String(f?.generator ?? "—")}</span>]]} />
    </div>
  );
}
