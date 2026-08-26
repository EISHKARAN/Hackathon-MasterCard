"""`make artifact-audit` — how much of the headline does any SINGLE feature explain?

WHY THIS EXISTS. "Six leakage controls" is an assertion. The controls we have are real but each
answers a different question: `test_no_oracle_in_features` checks that no feature READS an oracle
field, `leakage_linter` checks that no feature NAME references a held-out family, and
`test_no_attack_only_separators` checks that no feature is populated ONLY on attack rows. None of
them answers the question a sceptical reviewer will actually ask:

    "Is one feature doing most of the work, because your generator drew it too cleanly?"

That failure mode survives every existing gate. `session_duration_minutes` is the worked example and
the reason this file exists. It is the #1 feature by gain on two views. The generator draws it as
|N(6,4)| minutes on ordinary traffic and |N(145,70)| on attacks carrying ACCESS =
authorised-but-deceived-payer (sim/rails/upi.py, sim/rails/a2a.py). Measured on a world covering
every seed family: the benign MAXIMUM is 36.5 minutes and the attack 5th percentile is 33.9, so
essentially every deceived-payer attack sits above every ordinary session. It is not a one-sided
sentinel -- 17.2% of benign rows carry the field -- so the separator test passes it, correctly.

WHAT THIS TOOL CONCLUDES ABOUT THAT FEATURE, and why it is a disclosure rather than a deletion. The
field is populated on only 9.47% of attack events, which CAPS its contribution. Scored alone over the
whole population it reaches recall@0.1%FPR = 0.056 against the system's 0.314 -- so it accounts for
at most ~18% of the headline, not most of it. And the MECHANISM is real: authorised-push-payment
fraud genuinely involves hour-long coerced sessions, and session duration is used in production APP
detection. What is artificial is the MAGNITUDE -- a real benign session distribution is heavy-tailed
because people leave apps open, so real overlap would be substantial and the real signal weaker.
Deleting a legitimate mechanism because our own generator drew it too cleanly would be the wrong
correction. Quantifying it is the right one.

HOW TO READ THE OUTPUT. For every feature this reports its SUPPORT (what share of each class carries
it at all), its standalone discrimination, and its standalone recall at the reported operating point
over the FULL population -- not over its own support, which flatters it by an order of magnitude and
is the mistake that produced a "TPR-FPR 0.949" claim for a feature worth 0.056 recall.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from core import paths
from core.config import load_config
from core.io import write_json
from core.stagelog import stage
from eval.metrics import average_precision, roc_auc
from eval.splits import temporal_split
from features.builder import build_matrix, fit_reference_stats, prepare_columns
from features.registry import load_registry
from gate.cli import _load_events, _load_label_table, _resolve_labels
from gate.scorer import GateBundle

#: A feature whose standalone recall exceeds this SHARE of the system's own recall is flagged. Not a
#: failure -- a legitimately strong feature can trip it -- but it is a number that must appear in the
#: write-up rather than being discovered by a reviewer.
FLAG_SHARE_OF_SYSTEM_RECALL = 0.25

#: SECOND CRITERION, and the reason it exists. The share test above is bounded by SUPPORT, so a
#: feature carried on 2% of attacks can never trip it however cleanly it separates. Measured at the
#: full preset, `token_assurance_vs_device_age` reaches AUC 0.9652 on its own support and contributes
#: only 6.8% of the headline -- invisible to the share test, and exactly the shape a reviewer would
#: pick out of a gain table. A near-perfect separator is worth disclosing at ANY support.
FLAG_SUPPORT_AUC = 0.90


def _standalone(y: np.ndarray, v: np.ndarray, target_fpr: float) -> dict:
    """Metrics for ONE feature used directly as a risk score, over the FULL population.

    Rows where the feature is absent carry the -1 sentinel and therefore rank at the bottom, which is
    what a tree effectively does with them. Restricting to the populated subset instead would measure
    the feature's power ON ITS OWN SUPPORT, which is a different and much larger number -- the exact
    error that turned a 0.056-recall feature into a claimed 0.949.
    """
    v = np.asarray(v, dtype=np.float64)
    pop = v > -1.0
    s = np.where(pop, v, -np.inf)
    order = np.argsort(-s, kind="stable")
    ys = y[order].astype(np.int64)
    n_pos, n_neg = int(ys.sum()), int((1 - ys).sum())
    if n_pos == 0 or n_neg == 0:
        return {"degenerate": True}
    tp = np.cumsum(ys)
    fp = np.cumsum(1 - ys)
    tpr = tp / n_pos
    fpr = fp / n_neg
    k = int(np.searchsorted(fpr, target_fpr, side="right")) - 1
    j = int(np.argmax(tpr - fpr))
    # AUC/AP on the finite part only; a -inf block is a tie at the bottom and adds no ordering.
    finite = np.isfinite(s)
    auc = float(roc_auc(y[finite].astype(int), s[finite])) if finite.any() else float("nan")
    return {
        "degenerate": False,
        "support_share_benign": float(pop[y == 0].mean()),
        "support_share_attack": float(pop[y == 1].mean()),
        "max_possible_recall": float(pop[y == 1].mean()),
        "recall_at_target_fpr_alone": float(tpr[max(k, 0)]),
        "best_threshold_tpr_minus_fpr": float(tpr[j] - fpr[j]),
        "roc_auc_on_support": auc,
        "pr_auc_on_support": float(average_precision(y[finite].astype(int), s[finite]))
        if finite.any() else float("nan"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="make artifact-audit", description=__doc__)
    ap.add_argument("--view", default="issuer")
    ap.add_argument("--generator", default="vajra-sim")
    ap.add_argument("--target-fpr", type=float, default=0.001)
    ap.add_argument("--top", type=int, default=25, help="how many features by gain to audit")
    args = ap.parse_args(argv)

    cfg = load_config()
    paths.ensure_writable()

    with stage("artifact-audit", f"view={args.view}") as summary:
        print("\n=== VAJRA ARTIFACT AUDIT — what does any ONE feature explain? ===")
        reg = load_registry()
        cols = prepare_columns(_load_events(args.generator))
        ts = cols["ts"]
        split = temporal_split(ts)
        table = _load_label_table(args.generator)
        deploy_ts = float(ts[split.test].min()) if split.test.any() else float(ts.max())
        y_train_pit, _a = _resolve_labels(table, cols["event_id"], deploy_ts)
        holdout = cols["entity_pool"].astype(str) == "sealed"
        ref = fit_reference_stats(cols, y_train_pit, train_mask=split.train, holdout_mask=holdout)
        fm = build_matrix(cols, ref).subset_features(reg.features_for_view(args.view))

        bdir = paths.models / f"gate-i_{args.view}"
        if not (bdir / "bundle_meta.json").exists():
            raise SystemExit(f"{bdir} not found — run `make train VIEW={args.view}` first")
        bundle = GateBundle.load(bdir)
        gains = dict(getattr(bundle.g1, "importance_gain", {}) or {})

        test = split.test
        fm_t = fm.subset_rows(test)
        y = cols["oracle_is_attack"].astype(int)[test]
        print(f"  test rows {len(fm_t):,}  attacks {int(y.sum()):,} "
              f"(base rate {y.mean():.4%})  view {args.view} ({len(fm_t.names)} features)")

        ranked = [nm for nm, _g in sorted(gains.items(), key=lambda kv: -kv[1]) if nm in fm_t.names]
        if not ranked:
            ranked = list(fm_t.names)
        ranked = ranked[: args.top]

        rows = []
        for nm in ranked:
            r = _standalone(y, fm_t.column(nm), args.target_fpr)
            if r.get("degenerate"):
                continue
            r["feature"] = nm
            r["gain"] = float(gains.get(nm, 0.0))
            rows.append(r)

        rows.sort(key=lambda r: -r["recall_at_target_fpr_alone"])
        sys_recall = None
        mpath = paths.reports / f"metrics_{args.view}.json"
        if mpath.exists():
            from core.io import read_json
            try:
                sys_recall = float(
                    read_json(mpath)["headline"]["recall_at_fixed_fpr"]["recall"]
                )
            except Exception:  # noqa: BLE001
                sys_recall = None

        print(f"\n  --- ranked by STANDALONE recall@{args.target_fpr:.2%}FPR over the full "
              f"population ---")
        if sys_recall is not None:
            print(f"  the SYSTEM's recall at the same point: {sys_recall:.4f}"
                  f"   (a feature above {FLAG_SHARE_OF_SYSTEM_RECALL:.0%} of it is flagged)")
        if not sys_recall:
            print("  !! the system's own recall is 0 or unavailable at this preset, so the SHARE")
            print("     column cannot be computed and nothing can be flagged. The support and cap")
            print("     columns are still meaningful; run at the full preset for the shares.")
        print(f"    {'feature':<40}{'gain':>9}{'supp-B':>8}{'supp-A':>8}"
              f"{'alone':>8}{'cap':>9}{'AUC':>8}  flag")
        flagged = []
        for r in rows:
            share = (r["recall_at_target_fpr_alone"] / sys_recall) if sys_recall else 0.0
            reasons = []
            if sys_recall and share >= FLAG_SHARE_OF_SYSTEM_RECALL:
                reasons.append(f"{share:.0%} OF THE HEADLINE")
            _a = r.get("roc_auc_on_support")
            if _a is not None and _a == _a and _a >= FLAG_SUPPORT_AUC:
                reasons.append(f"AUC {_a:.4f} ON ITS SUPPORT")
            flag = ("<- " + "; ".join(reasons)) if reasons else ""
            r["flag_reasons"] = reasons
            if reasons:
                flagged.append(r["feature"])
            print(f"    {r['feature']:<40}{r['gain']:>9,.0f}"
                  f"{r['support_share_benign']:>8.2%}{r['support_share_attack']:>8.2%}"
                  f"{r['recall_at_target_fpr_alone']:>8.4f}{r['max_possible_recall']:>9.2%}"
                  f"{r['roc_auc_on_support']:>8.4f}  {flag}")

        print("\n  READ THIS COLUMN CORRECTLY. `alone` is recall over the WHOLE population, so it is")
        print("  bounded by `cap` = the share of attacks that carry the field at all. Measuring a")
        print("  feature only on its own support inflates it by an order of magnitude and is how a")
        print("  0.056-recall feature gets described as a 0.949 separator.")
        if flagged:
            print(f"\n  FLAGGED: {', '.join(flagged)}")
            print("  A flag is not a failure. It means the number belongs in the write-up, stated by")
            print("  us, rather than derived by a reviewer from the per-feature gain table.")
        else:
            print("\n  No single feature reaches the flag threshold.")

        out = {
            "view": args.view,
            "target_fpr": args.target_fpr,
            "system_recall_at_target_fpr": sys_recall,
            "flag_share_of_system_recall": FLAG_SHARE_OF_SYSTEM_RECALL,
            "flag_support_auc": FLAG_SUPPORT_AUC,
            "flagged_features": flagged,
            "features": rows,
            "how_to_read": (
                "`recall_at_target_fpr_alone` is over the FULL test population with absent rows "
                "ranked last, and is therefore bounded by `max_possible_recall`, the share of "
                "attacks carrying the field. `roc_auc_on_support` is computed on populated rows only "
                "and is NOT comparable to it."
            ),
            "reportable": {
                "is_reportable": True,
                "why": "read-only over the sealed-excluded test window against oracle truth; no "
                       "model is refitted and nothing here feeds a threshold.",
            },
        }
        write_json(out, paths.reports / f"artifact_audit_{args.view}.json")
        print(f"\n  wrote reports/artifact_audit_{args.view}.json")
        summary.update({"n_audited": len(rows), "n_flagged": len(flagged)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
