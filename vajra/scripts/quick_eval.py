"""`make quick-eval` — the headline metrics only, for ITERATING on model quality.

WHY THIS EXISTS: `make eval` takes ~2.8 hours at the full preset because it also fits the
baseline-equivalent replica, runs the leakage suite over the whole stream, scores the test window once
per deployment view for the visibility ablation, and bootstraps confidence intervals. All of that is
required for a REPORTED result and none of it is required to answer "did that change help?".

WHAT IT DELIBERATELY DOES NOT DO, so nothing here is ever mistaken for a publishable number:
  * no baseline replica, so no controlled comparison
  * no leakage suite, so this output is NOT gated on the controls passing
  * no ablation, no bootstrap intervals, no per-family breakdown
  * writes to reports/quick_eval.json, NEVER to reports/metrics*.json

Every number it prints is stamped NOT REPORTABLE for that reason. Use `make eval` for anything that
leaves the building.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from core import paths
from core.config import load_config
from core.io import write_json
from core.stagelog import stage
from eval.metrics import average_precision, precision_at_k, recall_at_fpr, roc_auc
from eval.splits import temporal_split
from features.builder import build_matrix, fit_reference_stats, prepare_columns
from features.registry import load_registry
from gate.cli import _load_events, _load_label_table, _resolve_labels
from gate.scorer import GateBundle, Scorer
from gate.sketches import OnlineStore


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="make quick-eval", description=__doc__)
    ap.add_argument("--view", default="issuer")
    ap.add_argument("--generator", default="vajra-sim")
    ap.add_argument("--target-fpr", type=float, default=0.001)
    ap.add_argument("--components", action="store_true",
                    help="also score each fusion channel alone, to see which carries the signal")
    args = ap.parse_args(argv)

    cfg = load_config()
    paths.ensure_writable()

    with stage("quick-eval", f"view={args.view}") as summary:
        print("\n=== VAJRA QUICK EVAL — NOT REPORTABLE (no replica, no leakage suite, no CIs) ===")
        cols = prepare_columns(_load_events(args.generator))
        ts = cols["ts"]
        split = temporal_split(ts)
        table = _load_label_table(args.generator)
        deploy_ts = float(ts[split.test].min()) if split.test.any() else float(ts.max())
        y_train_pit, _a = _resolve_labels(table, cols["event_id"], deploy_ts)
        holdout = cols["entity_pool"].astype(str) == "sealed"
        ref = fit_reference_stats(cols, y_train_pit, train_mask=split.train, holdout_mask=holdout)
        fm = build_matrix(cols, ref).subset_features(load_registry().features_for_view(args.view))

        bundle_dir = paths.models / f"gate-i_{args.view}"
        if not (bundle_dir / "bundle_meta.json").exists():
            raise SystemExit(f"{bundle_dir} not found — run `make train VIEW={args.view}` first")
        scorer = Scorer(GateBundle.load(bundle_dir), store=OnlineStore())

        test = split.test
        fm_test = fm.subset_rows(test)
        print(f"  test rows: {int(test.sum()):,}")
        batch = scorer.score_batch(fm_test)

        # The ORACLE label, which is what every reported metric is measured against.
        y = cols["oracle_is_attack"].astype(int)[test]
        n_pos = int(y.sum())
        base_rate = n_pos / max(1, y.size)
        print(f"  positives: {n_pos:,}  (base rate {base_rate:.4%})")

        def row(name: str, s: np.ndarray) -> dict[str, float]:
            r = recall_at_fpr(y, s, args.target_fpr)
            ap_ = average_precision(y, s)
            out = {
                "recall_at_target_fpr": float(r["recall"]),
                "realised_fpr": float(r["realised_fpr"]),
                "pr_auc": float(ap_),
                "lift_over_base_rate": float(ap_ / base_rate) if base_rate else 0.0,
                "roc_auc": float(roc_auc(y, s)),
            }
            print(f"  {name:<22} recall@{args.target_fpr:.1%}FPR {out['recall_at_target_fpr']:.4f}"
                  f"  PR-AUC {out['pr_auc']:.4f}  lift {out['lift_over_base_rate']:.1f}x"
                  f"  ROC-AUC {out['roc_auc']:.4f}")
            return out

        print("\n  --- headline ---")
        result = {"fused_calibrated": row("FUSED (calibrated)", batch.fused)}
        # WRITE AS WE GO. A crash after the headline previously discarded a 71-minute run's worth of
        # results; the expensive part is the feature build and the scoring pass, both already paid for
        # by this point. Partial output beats an exception.
        write_json(result, paths.reports / f"quick_eval_{args.view}.json")
        # `fused_rank` is OPTIONAL: it only exists on builds that carry the pre-calibration score.
        # Referencing it unconditionally is what crashed this script on a tree that did not have it.
        _rank = getattr(batch, "fused_rank", None)
        if _rank is not None:
            result["fused_rank"] = row("FUSED (rank, uncalib)", _rank)
        else:
            print("  FUSED (rank, uncalib)  SKIPPED — this build has no pre-calibration score")

        if args.components:
            print("\n  --- per channel, to see where the signal actually is ---")
            for c, v in batch.components.items():
                try:
                    result[f"component:{c}"] = row(f"  {c}", np.asarray(v, dtype=np.float64))
                except Exception as exc:  # noqa: BLE001
                    print(f"    {c}: FAILED ({exc})")
            write_json(result, paths.reports / f"quick_eval_{args.view}.json")

        # Operational point: precision at the staffed alert budget.
        k = max(1, int(round(cfg.alert_budget_share * y.size)))
        pk = precision_at_k(y, batch.fused, k=k, k_provenance="staffed alert budget from config/ops.yaml")
        print(f"\n  precision@k (k={k:,}, staffed budget) : {pk['precision_at_k']:.4f}")
        print(f"  abstention rate: attack {float(batch.abstained[y == 1].mean()) if n_pos else 0:.4f}"
              f"  benign {float(batch.abstained[y == 0].mean()):.4f}")

        result["precision_at_k"] = pk
        result["abstention"] = {
            "attack": float(batch.abstained[y == 1].mean()) if n_pos else 0.0,
            "benign": float(batch.abstained[y == 0].mean()),
        }
        result["reportable"] = {
            "is_reportable": False,
            "why": "quick-eval omits the baseline replica, the leakage suite, the ablation and all "
                   "confidence intervals. Use `make eval` for any number that leaves the building.",
        }
        write_json(result, paths.reports / f"quick_eval_{args.view}.json")
        print(f"\n  wrote reports/quick_eval_{args.view}.json")
        summary.update({"n_test": int(test.sum()), "pr_auc": result["fused_calibrated"]["pr_auc"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
