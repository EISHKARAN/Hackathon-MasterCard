"use client";
import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
import { rupees, num, pct } from "@/lib/format";
import { Kicker, Kpi, Notice, Panel, Skeleton, Stack, Tech, Why } from "@/components/ui";

// Screen 0 — MONEY. Opens the demo and owns the first fifteen seconds: two numbers, one toggle, no
// jargon. Both arms are precomputed from recorded runs, so the toggle switches between two stored
// result sets — a real comparison of two real runs, not an animation.
//
// The technicalities are ON this screen rather than in a footnote, because the first question a
// payments person asks about a fraud number is "measured on what?", and the answer has to arrive
// before they have to ask.
export default function Money() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  const [loopOn, setLoopOn] = useState(true);

  useEffect(() => {
    getJSON("/money").then(setData).catch((e) => setErr(String(e)));
  }, []);

  if (err)
    return (
      <Notice kind="bad">
        Could not load MONEY: {err}. Run <span className="mono">make money</span> then{" "}
        <span className="mono">make api</span>.
      </Notice>
    );
  if (!data) return <><div className="skel" style={{ width: "40%", height: 22 }} /><Skeleton rows={5} /></>;
  if (data.error) return <Notice>{data.error}</Notice>;

  const arm = loopOn ? data.loop_on : data.loop_off;
  const denom = data.denominator || {};
  const stopped = arm.rupees_fraud_stopped || 0;
  const missed = Math.max(0, (arm.rupees_fraud_attempted || 0) - stopped);

  return (
    <div>
      <Kicker tone="green">Screen 0 · the number an issuer buys</Kicker>
      <h1>What does this stop, and what does it cost good customers?</h1>
      <p className="sub">
        Before any detection metric. Both figures are <b>simulator-internal rupees</b>, labelled as
        such — not real money. Scored only on {num(denom.n_events_scored)} events from the{" "}
        <b>withheld populations</b> ({num(denom.n_attack)} attacks), with every loop-discovered
        composition excluded — so this opening number is not the circularity we spend a later section
        disowning.
      </p>

      {/* The toggle is the loop-lift claim. If no static arm was trained it says so and disables
          itself, rather than showing two identical numbers as though they were a comparison. */}
      <div className="row" style={{ margin: "4px 0 18px" }}>
        <span className="label">the closed loop</span>
        <button className={loopOn ? "go" : "secondary"} disabled={!data.toggle_is_live}
                onClick={() => setLoopOn(true)}>Loop ON</button>
        <button className={loopOn ? "secondary" : "go"} disabled={!data.toggle_is_live}
                onClick={() => setLoopOn(false)}>Loop OFF</button>
        {!data.toggle_is_live && (
          <span className="badge skip">
            comparison unavailable — no static arm trained, so both sides are the same model
          </span>
        )}
      </div>

      <div className="grid g2">
        <Kpi
          label="Rupees of fraud stopped"
          value={rupees(stopped)}
          tone="green"
          denom={<>of {rupees(arm.rupees_fraud_attempted)} attempted · VDR {pct(arm.value_detection_rate)}</>}
          note={<>Value-detection rate, not event recall: one large mule cash-out matters more than
            many sub-ceiling debits, and an event-counted metric hides that.</>}
        />
        <Kpi
          label="Rupees of good customers declined"
          value={rupees(arm.rupees_good_declined)}
          tone="red"
          denom={<>plus {rupees(arm.rupees_good_frictioned)} frictioned · {num(arm.n_good_frictioned)} customers</>}
          note={<>Friction is priced separately. A system that frictions everything has moved the cost
            onto good customers rather than stopping fraud.</>}
        />
      </div>

      <h2>Where the attempted fraud value went</h2>
      <Panel tight>
        <Stack parts={[
          { name: "stopped", value: stopped, tone: "green" },
          { name: "not stopped", value: missed, tone: "red" },
        ]} />
        <Why>
          Both segments are simulator-internal rupees over the withheld population only. The split is
          the whole claim: a detector that stops nothing and a detector that declines everything both
          look good on a single number, and neither survives this bar.
        </Why>
      </Panel>

      <Tech items={[
        ["events scored", <span className="mono">{num(denom.n_events_scored)}</span>],
        ["of which attacks", <span className="mono">{num(denom.n_attack)}</span>],
        ["population", "withheld only"],
        ["loop-discovered compositions", "excluded"],
        ["currency", "simulator-internal"],
        data.toggle_is_live ? ["arms", "two recorded runs"] : ["arms", "single model"],
      ]} />

      <Notice>
        <b>Read the ratio, not just the totals.</b> The declined figure is the <b>auto-decline band
        only</b>. Declining is the bluntest of three tools — friction and review exist to move volume
        out of decline — and the band thresholds are fitted to a <b>cost matrix that is a swept
        parameter, not a claim</b> (see <span className="mono">make sensitivity</span>). A different
        false-decline lifetime cost moves this trade directly, which is why it ships as a trade-off
        rather than as a headline.
      </Notice>
      <Notice kind="honest">{data.provenance} {denom.why}</Notice>
      <p className="sub">{data.toggle_is_live ? data.toggle : data.toggle_caveat}</p>
    </div>
  );
}
