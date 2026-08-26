"use client";
import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";
import { pct, num } from "@/lib/format";

// Screen 4 — GATE OPS. The metrics table, the three-band decomposition in ABSOLUTE DAILY COUNTS, the
// queue ceiling, and the per-family red cells. The threshold trade is a static precomputed curve read
// from the metrics report (a four-way coupled slider is stretch and promised to nobody).
export default function GateOps() {
  const [m, setM] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { getJSON("/metrics").then(setM).catch((e) => setErr(String(e))); }, []);

  if (err) return <div className="err">Could not load metrics: {err}. Run <span className="mono">make eval</span>.</div>;
  if (!m) return <div className="sub">loading…</div>;
  if (m.error) return <div className="notice">{m.error}</div>;

  const h = m.headline || {};
  const rp = m.reportable || {};
  const bands = m.action_bands || {};
  const qc = m.queue_ceiling || {};
  const cc = m.controlled_comparison || {};
  const families = m.stratified?.per_family_recall?.families || {};
  const ablation = m.visibility_ablation?.per_view || {};
  const bandCollapse: string[] = m.action_bands?.collapsed || m.action_table?.collapsed || [];

  return (
    <div>
      <h1>GATE OPS</h1>
      {!rp.is_reportable && (
        <div className="notice">
          <b>NOT REPORTABLE at this scale</b> — {rp.n_positives_in_test_window} attack events in the test
          window, below the {rp.minimum_for_headline} floor. Numbers below are wiring evidence. Run{" "}
          <span className="mono">make sim PRESET=full</span>.
        </div>
      )}

      <h2>Headline (every number with its denominator)</h2>
      <div className="grid g3">
        <Stat label="Recall @ 0.1% FPR" value={h.recall_at_fixed_fpr?.recall?.toFixed(3)} sub={`realised FPR ${pct(h.recall_at_fixed_fpr?.realised_fpr,2)}`} />
        <Stat label="PR-AUC (headline)" value={h.pr_auc_average_precision?.toFixed(3)} sub="degrades honestly under imbalance" />
        <Stat label="ROC-AUC (not headline)" value={h.roc_auc?.value?.toFixed(3)} sub="near-1 for any competent model at this base rate" />
        <Stat label="Precision@k (staffed)" value={h.precision_at_k?.precision_at_k?.toFixed(3)} sub={`k=${h.precision_at_k?.k_effective}`} />
        <Stat label="Value-detection rate" value={h.value_detection_rate?.vdr?.toFixed(3)} sub="the number a CFO recognises" />
        <Stat label="Precision / Recall / F1" value={`${(h.precision_recall_f1_at_operating_threshold?.precision||0).toFixed(2)} / ${(h.precision_recall_f1_at_operating_threshold?.recall||0).toFixed(2)} / ${(h.precision_recall_f1_at_operating_threshold?.f1||0).toFixed(2)}`} sub="at the fixed-FPR operating point" />
      </div>

      <h2>Controlled comparison (never a bare absolute)</h2>
      <div className="notice honest">
        vs modelled incumbent: {cc.delta_vs_incumbent?.reported_as}<br />
        vs baseline replica: {cc.delta_vs_baseline?.reported_as}
        {cc.baseline_arm_caveat && <div style={{ marginTop: 6 }}>{cc.baseline_arm_caveat}</div>}
      </div>

      <h2>Action bands, in absolute daily counts</h2>
      <p className="sub">
        Scaled to a {num(bands.reference_volume_per_day)}-authorisation reference portfolio. A "0.05pp"
        movement is thousands of events/day — roughly twice the whole staffed queue.
      </p>
      <table>
        <thead><tr><th>band</th><th>share</th><th>scaled daily count</th></tr></thead>
        <tbody>
          {["approve", "friction", "review", "auto_decline"].map((b) => bands[b] && (
            <tr key={b}><td><span className={`pill ${b}`}>{b}</span></td><td>{pct(bands[b].share, 3)}</td><td>{num(bands[b].scaled_daily_count)}</td></tr>
          ))}
        </tbody>
      </table>
      <div className="notice">
        Queue ceiling: at a {pct(qc.base_rate, 2)} base rate, {num(qc.implied_frauds_per_day)} frauds/day
        against {num(qc.staffed_alert_budget_per_day)} staffed cases/day — the <b>review band alone cannot
        exceed {pct(qc.review_band_recall_ceiling)}</b> recall before precision is even discussed.
      </div>

      {bandCollapse.length > 0 && (
        <div className="notice">
          <b>BAND COLLAPSE, published rather than hidden:</b> {bandCollapse.join("; ")}.
          A collapsed ladder is not always an error — at a small per-rail population every score can be
          tied — but it empties the three-band decomposition for that rail, so it is shown.
        </div>
      )}

      <div className="notice honest">
        <b>Three feature counts, all correct, all different:</b> the registry declares{" "}
        <b>388</b> features; <b>387</b> enter the model matrix (one is audit-only and must never be a
        model input); and <b>{h.n_features_in_view ?? 314}</b> survive this deployment view, because a
        view that cannot construct a feature has it <b>absent</b>, not zeroed.
      </div>

      <h2>Per-family recall — no aggregation, families at zero recall named</h2>
      <table>
        <thead><tr><th>family</th><th>positives</th><th>recall</th><th>Wilson 95% CI</th></tr></thead>
        <tbody>
          {Object.entries(families).sort((a: any, b: any) => a[1].recall - b[1].recall).map(([f, r]: any) => (
            <tr key={f}>
              <td className="mono">{f}</td><td>{r.n_positives}</td>
              <td style={{ color: r.recall === 0 ? "var(--red)" : "var(--text)" }}>{r.recall.toFixed(3)}</td>
              <td className="mono">[{r.wilson_ci[0].toFixed(2)}, {r.wilson_ci[1].toFixed(2)}]</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Single-institution visibility ablation (never cut)</h2>
      <p className="sub">
        The <b>issuer</b> row IS the reference: its Δ is 0.0000 by definition, not by measurement.
        Every other view is measured against it. Features are <b>absent</b> at a view, never zeroed.
      </p>
      <table>
        <thead><tr><th>view</th><th>recall</th><th>Δ vs issuer reference</th><th>share of reference</th></tr></thead>
        <tbody>
          {Object.entries(ablation)
            .sort((a: any, b: any) => b[1].recall - a[1].recall)
            .map(([v, r]: any) => {
            const isRef = (r.delta_vs_full ?? 0) === 0 && (r.share_of_full ?? 0) === 1;
            return (
              <tr key={v}>
                <td>{v} {isRef && <span className="badge skip">reference</span>}</td>
                <td>{r.recall?.toFixed(4)}</td>
                <td className="mono">{isRef ? "— (reference)" : r.delta_vs_full?.toFixed(4)}</td>
                <td className="mono">{isRef ? "—" : pct(r.share_of_full)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: any; sub: string }) {
  return (
    <div className="panel">
      <div className="label">{label}</div>
      <div className="stat blue" style={{ fontSize: 26 }}>{value ?? "n/a"}</div>
      <div className="sub" style={{ margin: 0, fontSize: 11 }}>{sub}</div>
    </div>
  );
}
