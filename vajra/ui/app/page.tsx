/* Screen 0 — MONEY. Server component: reads the report from disk, so it cannot hang on a fetch. */
import { report, rupees, num, pct, inventory } from "@/lib/reports";
import { Kicker, Kpi, Notice, Panel, Stack, Tech, Why } from "@/components/ui";

// Rendered at BUILD time. The records are committed artefacts of a finished run, not live data,
// so a snapshot is correct here and lets the whole prototype ship as one service.
export const dynamic = "force-static";

export default function Money() {
  const d: any = report("money.json");
  const inv = inventory();

  if (!d || d.error) {
    return (
      <div>
        <Kicker tone="green">Screen 0 · the number an issuer buys</Kicker>
        <h1>What does this stop, and what does it cost good customers?</h1>
        <Notice kind="bad">
          The economics report has not been generated yet. It is produced by the pipeline and read
          from disk — no service call is involved.
        </Notice>
        <Panel><div className="label">Artifacts on disk</div>
          <div className="tbl-wrap" style={{ marginTop: 10 }}>
            <table><tbody>{inv.map((a) => (
              <tr key={a.name}><td className="mono">{a.name}</td>
                <td className="num">{a.ok ? `${num(a.bytes)} bytes` : "—"}</td>
                <td>{a.ok ? <span className="badge pass">present</span> : <span className="badge fail">missing</span>}</td>
              </tr>))}</tbody></table>
          </div>
        </Panel>
      </div>
    );
  }

  const arm = d.loop_on ?? {};
  const off = d.loop_off ?? {};
  const den = d.denominator ?? {};
  const stopped = arm.rupees_fraud_stopped ?? 0;
  const missed = Math.max(0, (arm.rupees_fraud_attempted ?? 0) - stopped);

  return (
    <div>
      <Kicker tone="green">Screen 0 · the number an issuer buys</Kicker>
      <h1>What does this stop, and what does it cost good customers?</h1>
      <p className="sub">
        Before any detection metric. Both figures are <b>simulator-internal rupees</b>, labelled as
        such — not real money. Scored only on {num(den.n_events_scored)} events from the{" "}
        <b>withheld populations</b> ({num(den.n_attack)} attacks), with every loop-discovered
        composition excluded, so this opening number is not the circularity we disown later.
      </p>

      <div className="grid g2">
        <Kpi label="Rupees of fraud stopped" value={rupees(stopped)} tone="green"
             denom={<>of {rupees(arm.rupees_fraud_attempted)} attempted · VDR {pct(arm.value_detection_rate)}</>}
             note="Value-detection rate, not event recall: one large mule cash-out matters more than many sub-ceiling debits, and an event-counted metric hides that." />
        <Kpi label="Rupees of good customers declined" value={rupees(arm.rupees_good_declined)} tone="red"
             denom={<>plus {rupees(arm.rupees_good_frictioned)} frictioned · {num(arm.n_good_frictioned)} customers</>}
             note="Friction is priced separately. A system that frictions everything has moved the cost onto good customers rather than stopping fraud." />
      </div>

      <h2>Where the attempted fraud value went</h2>
      <Panel tight>
        <Stack parts={[{ name: "stopped", value: stopped, tone: "green" },
                       { name: "not stopped", value: missed, tone: "red" }]} />
        <Why>
          Withheld population only. The split is the whole claim: a detector that stops nothing and one
          that declines everything both look good on a single number, and neither survives this bar.
        </Why>
      </Panel>

      {d.toggle_is_live && (
        <>
          <h2>With the closed loop, and without it</h2>
          <div className="grid g2">
            <Kpi label="Loop ON · fraud stopped" value={rupees(stopped)} tone="green"
                 denom={`VDR ${pct(arm.value_detection_rate)}`} />
            <Kpi label="Loop OFF · fraud stopped" value={rupees(off.rupees_fraud_stopped)} tone="amber"
                 denom={`VDR ${pct(off.value_detection_rate)}`} />
          </div>
          <Why>{d.toggle}</Why>
        </>
      )}
      {!d.toggle_is_live && <Notice>{d.toggle_caveat}</Notice>}

      <Tech items={[
        ["events scored", <span className="mono" key="a">{num(den.n_events_scored)}</span>],
        ["of which attacks", <span className="mono" key="b">{num(den.n_attack)}</span>],
        ["population", "withheld only"],
        ["loop-discovered compositions", "excluded"],
        ["currency", "simulator-internal"],
      ]} />

      <Notice>
        <b>Read the ratio, not the totals.</b> The declined figure is the <b>auto-decline band only</b>.
        Declining is the bluntest of three tools — friction and review exist to move volume out of
        decline — and the band thresholds are fitted to a <b>cost matrix that is a swept parameter,
        not a claim</b>. A different false-decline lifetime cost moves this trade directly, which is
        why it ships as a trade-off rather than a headline.
      </Notice>
      <Notice kind="honest">{d.provenance} {den.why}</Notice>
    </div>
  );
}
