/* GATE OPS — the reportable detection numbers, read from disk. */
import { report, sig, num, pct } from "@/lib/reports";
import { Badge, Kicker, Kpi, Notice, Tech, Why } from "@/components/ui";
// Rendered at BUILD time. The records are committed artefacts of a finished run, not live data,
// so a snapshot is correct here and lets the whole prototype ship as one service.
export const dynamic = "force-static";

export default function Gate() {
  const m: any = report("metrics_issuer.json");
  if (!m) return <Notice kind="bad">The evaluation report has not been generated yet.</Notice>;
  const h = m.headline ?? {}, p = m.population ?? {}, cc = m.controlled_comparison ?? {};
  const sh = m.sealed_holdout_recall ?? {}, lk = m.leakage ?? {}, va = m.visibility_ablation ?? {};
  const prf = h.precision_recall_f1_at_operating_threshold ?? {};
  const pa = cc.pr_auc_same_rows_same_truth ?? {};
  const checks: any[] = lk.checks ?? lk.results ?? [];

  return (
    <div>
      <Kicker>Criterion 3 · detection efficacy</Kicker>
      <h1>Results — issuer view, reportable</h1>
      <p className="sub">
        Test window {num(p.n_test_rows)} rows · {num(p.n_positives_oracle)} attacks · base rate{" "}
        {pct(p.base_rate_realised_oracle, 4)}. Measured against oracle attack truth on a time-forward
        split with a purge and an embargo, sealed entities excluded from training.
      </p>

      <div className="grid g4">
        <Kpi label="PR-AUC" value={sig(h.pr_auc_average_precision)} tone="green"
             denom={`${sig((h.pr_auc_average_precision ?? 0) / (p.base_rate_realised_oracle || 1), 1)}× lift over base rate`} />
        <Kpi label="recall @ 0.1% FPR" value={sig(h.recall_at_fixed_fpr?.recall)} tone="green"
             denom={`realised FPR ${sig(h.recall_at_fixed_fpr?.realised_fpr, 7)}`} />
        <Kpi label="precision@k" value={sig(h.precision_at_k?.precision_at_k)} tone="green"
             denom={`k = ${num(h.precision_at_k?.k)} · staffed queue`} />
        <Kpi label="value-detection rate" value={sig(h.value_detection_rate?.vdr)} tone="green"
             denom="share of fraud VALUE caught" />
      </div>

      <h2>The comparisons</h2>
      <div className="tbl-wrap">
        <table>
          <thead><tr><th>arm</th><th className="num">recall @ 0.1% FPR</th><th className="num">PR-AUC</th><th>note</th></tr></thead>
          <tbody>
            <tr><td><b>this system</b></td><td className="num">{sig(h.recall_at_fixed_fpr?.recall)}</td>
                <td className="num">{sig(pa.gate)}</td><td>oracle truth, full test window</td></tr>
            <tr><td>modelled incumbent</td><td className="num">{sig(cc.absolute?.modelled_incumbent)}</td>
                <td className="num">{sig(pa.modelled_incumbent)}</td>
                <td style={{ color: "var(--green)" }}>we lead by {cc.delta_vs_incumbent?.reported_as ?? "—"}</td></tr>
            <tr><td>baseline replica</td><td className="num">{sig(cc.absolute?.baseline_replica)}</td>
                <td className="num">{sig(pa.baseline_replica)}</td>
                <td style={{ color: "var(--amber)" }}>trained on a random split · see note</td></tr>
          </tbody>
        </table>
      </div>
      <Why>
        The replica gets the same features, the same library and the same hyper-parameters; only the
        methodology differs. It trains on a random split spanning the whole timeline and on fully
        matured labels, so a large share of our test window sits inside its training set. Neither of
        its numbers is attainable at decision time, and we report it beating us rather than hiding it.
      </Why>

      <h2>Generalisation to compositions never trained on</h2>
      <div className="grid g3">
        <Kpi label="sealed compositions" value={sig(sh.sealed_compositions?.recall)} tone="blue"
             denom={`${num(sh.sealed_compositions?.n_attacks)} attacks, never seen`} />
        <Kpi label="trainable compositions" value={sig(sh.trainable_compositions?.recall)} tone="green"
             denom={`${num(sh.trainable_compositions?.n_attacks)} attacks`} />
        <Kpi label="generalisation gap" value={sig(sh.generalisation_gap)} tone="amber"
             denom={`withheld evasion morpheme: ${sh.withheld_evasion_morpheme ?? "—"}`} />
      </div>

      <h2>Leakage controls — any failure fails the build</h2>
      <div className="row" style={{ marginBottom: 10 }}>
        <Badge kind={lk.passed ? "pass" : "fail"}>{lk.passed ? "all controls pass" : "a control failed"}</Badge>
        <span className="mono" style={{ color: "var(--faint)", fontSize: 11 }}>{checks.length} controls</span>
      </div>
      {checks.length > 0 && (
        <div className="tbl-wrap">
          <table>
            <thead><tr><th>control</th><th>result</th><th>what it proves</th></tr></thead>
            <tbody>{checks.map((c: any, i: number) => (
              <tr key={i}><td className="mono">{c.name ?? c.check ?? "—"}</td>
                <td><Badge kind={/pass/i.test(String(c.status ?? c.result)) ? "pass" : /skip/i.test(String(c.status ?? c.result)) ? "skip" : "fail"}>{c.status ?? c.result ?? "—"}</Badge></td>
                <td style={{ fontSize: 11.5, color: "var(--muted)" }}>{c.detail ?? c.note ?? c.message ?? ""}</td></tr>
            ))}</tbody>
          </table>
        </div>
      )}

      {va.per_view && (
        <>
          <h2>What each deployment position can see</h2>
          <div className="tbl-wrap">
            <table><thead><tr><th>view</th><th className="num">recall @ 0.1% FPR</th></tr></thead>
              <tbody>{Object.entries(va.per_view).map(([k, v]: any) => (
                <tr key={k}><td>{k}</td><td className="num">{sig(v)}</td></tr>))}</tbody>
            </table>
          </div>
          <Why>
            Features an institution genuinely cannot construct are absent, not zeroed. Zeroing would
            assert that an entity has no fan-out, which is a different and false claim from an
            institution being unable to observe it.
          </Why>
        </>
      )}

      <Tech items={[
        ["precision / recall / F1", <span className="mono" key="a">{sig(prf.precision)} / {sig(prf.recall)} / {sig(prf.f1)}</span>],
        ["ROC-AUC", <span className="mono" key="b">{sig(h.roc_auc?.value)}</span>],
        ["reportable", m.reportable?.is_reportable ? "yes" : "NO"],
      ]} />
      <Notice kind="honest">
        ROC-AUC is computed but is not the headline: at a base rate under one percent it is dominated
        by the true-negative mass and is near-1 for any competent model, which is why it is not
        comparable across submissions.
      </Notice>
    </div>
  );
}
