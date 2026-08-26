"use client";
import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
import { rupees, num, pct } from "@/lib/format";

// Screen 0 — MONEY. Opens the demo and owns the first 15 seconds. Two numbers, one toggle, no jargon.
// Both arms are precomputed from recorded runs; the toggle switches between two stored result sets, so
// it is a real comparison of two real runs, not an animation.
export default function Money() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  const [loopOn, setLoopOn] = useState(true);

  useEffect(() => {
    getJSON("/money").then(setData).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="err">Could not load MONEY: {err}. Run <span className="mono">make money</span> then <span className="mono">make api</span>.</div>;
  if (!data) return <div className="sub">loading…</div>;
  if (data.error) return <div className="notice">{data.error}</div>;

  const arm = loopOn ? data.loop_on : data.loop_off;
  const denom = data.denominator || {};

  return (
    <div>
      <h1>What does this stop, and what does it cost good customers?</h1>
      <p className="sub">
        The number an issuer buys, before any detection metric. Both figures are <b>simulator-internal
        rupees</b>, labelled as such — not real money. Scored only on {num(denom.n_events_scored)} events
        from the withheld populations ({denom.n_attack} attacks), with every loop-discovered composition
        excluded, so this opening number is not the circularity we spend a section disowning.
      </p>

      <div style={{ display: "flex", gap: 12, alignItems: "center", margin: "8px 0 20px" }}>
        <span className="label">the closed loop</span>
        <button className={loopOn ? "" : "secondary"} disabled={!data.toggle_is_live}
                onClick={() => setLoopOn(true)}>Loop ON</button>
        <button className={loopOn ? "secondary" : ""} disabled={!data.toggle_is_live}
                onClick={() => setLoopOn(false)}>Loop OFF</button>
        {!data.toggle_is_live && (
          <span className="badge skip">
            comparison unavailable — no static arm was trained, so both sides are the same model
          </span>
        )}
      </div>

      <div className="grid g2">
        <div className="panel">
          <div className="label">Rupees of fraud stopped</div>
          <div className="stat green">{rupees(arm.rupees_fraud_stopped)}</div>
          <div className="sub">of {rupees(arm.rupees_fraud_attempted)} attempted · value-detection rate {pct(arm.value_detection_rate)}</div>
        </div>
        <div className="panel">
          <div className="label">Rupees of good customers declined</div>
          <div className="stat red">{rupees(arm.rupees_good_declined)}</div>
          <div className="sub">
            plus {rupees(arm.rupees_good_frictioned)} frictioned ({num(arm.n_good_frictioned)} customers).
            Friction is priced separately — a system that frictions everything has moved friction onto good
            customers, not stopped fraud.
          </div>
        </div>
      </div>

      <div className="notice">
        <b>Read the ratio, not just the totals.</b> The declined figure is the <b>auto-decline band
        only</b>. Declining is the bluntest of three tools — friction and review exist to move volume
        out of decline — and the band thresholds are fitted to a <b>cost matrix that is a swept
        parameter, not a claim</b> (see <span className="mono">make sensitivity</span>). A different
        false-decline lifetime cost moves this trade directly, which is why it is published as a
        trade-off rather than as a headline.
      </div>
      <div className="notice honest">
        {data.provenance} {denom.why}
      </div>
      <p className="sub">{data.toggle_is_live ? data.toggle : data.toggle_caveat}</p>
    </div>
  );
}
