/* LOOP — the closed loop and whether it bought anything. */
import { report, num, sig } from "@/lib/reports";
import { Kicker, Kpi, Notice, Panel, Pipeline, Tech, Why } from "@/components/ui";
// Rendered at BUILD time. The records are committed artefacts of a finished run, not live data,
// so a snapshot is correct here and lets the whole prototype ship as one service.
export const dynamic = "force-static";

const STAGES = [
  { t: "archive-select", d: "elites + under-filled cells", tone: "red" as const },
  { t: "plan", d: "one composer call per tick", tone: "red" as const },
  { t: "execute", d: "bandit under a P&L budget", tone: "red" as const },
  { t: "score", d: "both personae", tone: "blue" as const },
  { t: "mine", d: "cluster the escapes", tone: "grey" as const },
  { t: "forge", d: "retrain + promotion gate", tone: "blue" as const },
];

export default function Loop() {
  const l: any = report("loop_report.json");
  if (!l) return <Notice kind="bad">The loop report has not been generated yet.</Notice>;
  const lift = l.loop_lift ?? {};
  const arms: any[] = Array.isArray(l.arms) ? l.arms : Object.values(l.arms ?? {});

  return (
    <div>
      <Kicker tone="amber">The mechanism</Kicker>
      <h1>The loop, and whether it bought anything</h1>
      <p className="sub">
        The red side proposes, the blue side scores, and the gaps the defence reveals raise the
        sampling weight of the regions that produced them. That return path is what makes this a
        mechanism rather than a diagram — and it is reported even when the lift is small.
      </p>

      <Pipeline stages={STAGES} />

      <div className="grid g3">
        <Kpi label="ticks completed" value={num(l.n_ticks)} tone="blue" denom="one full cycle each" />
        <Kpi label="control arms" value={num(arms.length)} tone="blue" denom="the loop is compared, not asserted" />
        <Kpi label="gate difficulty" value={sig(l.difficulty, 3)} tone="amber"
             denom="calibrated from the realised action rate" />
      </div>

      {Object.keys(lift).length > 0 && (
        <>
          <h2>Loop lift</h2>
          <Panel tight>
            <div className="tbl-wrap">
              <table><tbody>{Object.entries(lift).map(([k, v]: any) => (
                <tr key={k}><td className="mono">{k.replace(/_/g, " ")}</td>
                  <td className="num">{typeof v === "number" ? sig(v) : String(v).slice(0, 160)}</td></tr>))}</tbody>
              </table>
            </div>
            <Why>
              If the loop bought little, this screen says so. A closed loop that cannot show its own
              contribution is a claim, and the whole point of running control arms is to avoid making one.
            </Why>
          </Panel>
        </>
      )}

      {arms.length > 0 && (
        <>
          <h2>Control arms</h2>
          <div className="tbl-wrap">
            <table>
              <thead><tr><th>arm</th><th>what it isolates</th></tr></thead>
              <tbody>{arms.slice(0, 8).map((a: any, i: number) => (
                <tr key={i}><td className="mono">{a.name ?? a.arm ?? `arm ${i + 1}`}</td>
                  <td style={{ fontSize: 11.5, color: "var(--muted)" }}>
                    {a.description ?? a.note ?? a.what ?? "—"}</td></tr>))}</tbody>
            </table>
          </div>
        </>
      )}

      <Tech items={[["ticks", <span className="mono" key="a">{num(l.n_ticks)}</span>],
                    ["stamped", <span className="mono" key="b">{String(l.stamped_at ?? "—").slice(0, 19)}</span>]]} />
    </div>
  );
}
