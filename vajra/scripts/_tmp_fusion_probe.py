"""THROWAWAY verification probe: rank-average vs weighted-Fisher fusion on the on-disk smoke bundle.

Mirrors scripts/quick_eval.py exactly for data prep, then compares fusion arms on the SAME
components, so the only thing that differs between arms is the combination rule.
"""

from __future__ import annotations

import json
import sys

import numpy as np

from core import paths
from core.config import load_config
from eval.metrics import average_precision, precision_at_k, recall_at_fpr, roc_auc
from eval.splits import temporal_split
from features.builder import build_matrix, fit_reference_stats, prepare_columns
from features.registry import load_registry
from gate.cli import _load_events, _load_label_table, _resolve_labels
from gate.fusion import COMPONENTS, Fusion, IsotonicCalibrator
from gate.scorer import GateBundle, Scorer
from gate.sketches import OnlineStore

VIEW = "issuer"
GEN = "vajra-sim"
TARGET_FPR = 0.001


def main() -> int:
    cfg = load_config()
    cols = prepare_columns(_load_events(GEN))
    ts = cols["ts"]
    split = temporal_split(ts)
    table = _load_label_table(GEN)
    deploy_ts = float(ts[split.test].min()) if split.test.any() else float(ts.max())
    y_train_pit, _a = _resolve_labels(table, cols["event_id"], deploy_ts)
    stats_end = float(ts[split.stats].max()) if split.stats.any() else deploy_ts
    y_stats_pit, _a2 = _resolve_labels(table, cols["event_id"], stats_end)
    holdout = cols["entity_pool"].astype(str) == "sealed"
    ref = fit_reference_stats(cols, y_train_pit, train_mask=split.train, holdout_mask=holdout)
    fm = build_matrix(cols, ref).subset_features(load_registry().features_for_view(VIEW))

    bundle = GateBundle.load(paths.models / f"gate-i_{VIEW}")
    fusion = bundle.fusion
    print("weights:", fusion.weights)
    print("ecdf sizes:", {k: v.size for k, v in fusion.component_ecdf.items()})
    print("calibrator breakpoints:", fusion.calibrator.x_.size,
          "x range", float(fusion.calibrator.x_.min()), float(fusion.calibrator.x_.max()))

    # ---- test window --------------------------------------------------------------
    fm_test = fm.subset_rows(split.test)
    y = cols["oracle_is_attack"].astype(int)[split.test]
    print(f"test rows {len(fm_test):,}  positives {int(y.sum()):,}")
    batch = Scorer(bundle, cfg=cfg, store=OnlineStore()).score_batch(fm_test)
    comps = batch.components

    ranks = {c: fusion._rank_against_training(c, np.asarray(comps[c])) for c in COMPONENTS if c in comps}
    for c, r in ranks.items():
        print(f"  rank {c:<14} min {r.min():.4f} max {r.max():.4f} "
              f"share_at_1.0 {float((r >= 1.0 - 1e-12).mean()):.4%} "
              f"n_distinct {np.unique(r).size}")

    total_w = sum(fusion.weights.get(c, 0.0) for c in ranks)
    ref_size = max(int(min(v.size for v in fusion.component_ecdf.values())), 2)
    eps = 1.0 / ref_size

    def fisher(rk: dict[str, np.ndarray], w: dict[str, float]) -> np.ndarray:
        tw = sum(w.get(c, 0.0) for c in rk)
        acc = np.zeros(len(next(iter(rk.values()))), dtype=np.float64)
        for c, r in rk.items():
            acc += (w.get(c, 0.0) / tw) * -np.log(np.clip(1.0 - r + eps, eps, 1.0))
        return acc

    k_op = max(1, int(round(cfg.alert_budget_share * y.size)))
    k_stable = max(k_op, min(200, max(20, y.size // 100)))

    def report(name: str, s: np.ndarray) -> dict:
        s = np.asarray(s, dtype=np.float64)
        r = recall_at_fpr(y, s, TARGET_FPR)
        ap = average_precision(y, s)
        pk = precision_at_k(y, s, k=k_op, k_provenance="probe")["precision_at_k"]
        pks = precision_at_k(y, s, k=k_stable, k_provenance="probe")["precision_at_k"]
        au = roc_auc(y, s)
        print(f"  {name:<34} AP {ap:.5f}  rec@{TARGET_FPR:.1%}FPR {r['recall']:.4f} "
              f"(realised {r['realised_fpr']:.5f})  p@{k_op} {pk:.4f}  p@{k_stable} {pks:.4f} "
              f" ROC {au:.4f}  n_distinct {np.unique(s).size}")
        return {"ap": float(ap), "recall": float(r["recall"]), "p_at_k": float(pk),
                "p_at_k_stable": float(pks), "roc": float(au)}

    out: dict[str, dict] = {}
    print("\n--- arms on the PRE-CALIBRATION axis ---")
    out["g1_rank_alone"] = report("g1 rank alone", ranks["g1"])
    out["g1_raw_alone"] = report("g1 raw score alone", comps["g1"])
    out["rank_average_current"] = report("rank-average (CURRENT)", batch.fused_rank)
    out["fisher_default_w"] = report("FISHER, default weights", fisher(ranks, fusion.weights))
    out["fisher_equal_w"] = report("FISHER, equal weights", fisher(ranks, {c: 1.0 for c in ranks}))
    out["max_rule"] = report("max-rule", np.max(np.vstack(list(ranks.values())), axis=0))
    for p in (2, 4, 8):
        out[f"power_{p}"] = report(
            f"rank-average of r^{p}",
            sum((fusion.weights.get(c, 0.0) / total_w) * ranks[c] ** p for c in ranks),
        )

    print("\n--- what the CURRENT eval harness reads (calibrated axis) ---")
    out["calibrated_rank_average"] = report("calibrated rank-avg (as shipped)", batch.fused)
    out["calibrated_fisher_no_refit"] = report(
        "calibrated FISHER, calibrator NOT refit", fusion.calibrator.transform(fisher(ranks, fusion.weights))
    )

    # ---- refit the calibrator on the STATS window, Fisher axis ---------------------
    print("\n--- refitting the isotonic calibrator on the STATS window ---")
    st_idx = np.flatnonzero(split.stats & ~holdout)
    fm_stats = fm.subset_rows(np.isin(np.arange(len(fm)), st_idx))
    sc2 = Scorer(bundle, cfg=cfg, store=OnlineStore())
    cs = {"g1": sc2._g1_scores(fm_stats)}
    p_conf, novelty = sc2._conformal(fm_stats, cs["g1"])
    cs["g2_conformal"] = novelty
    cs["g2_density"] = sc2._density(fm_stats)
    cs["sketch"] = sc2._sketch(fm_stats)
    cs["gate_b"] = sc2._gate_b_component(fm_stats)
    y_st = y_stats_pit[st_idx]
    ranks_st = {c: fusion._rank_against_training(c, np.asarray(cs[c])) for c in ranks}
    fisher_st = fisher(ranks_st, fusion.weights)
    cal2 = IsotonicCalibrator().fit(fisher_st, np.where(y_st < 0, -1, y_st))
    print("  refit calibrator:", cal2.as_dict())
    out["calibrated_fisher_refit"] = report(
        "calibrated FISHER, calibrator REFIT", cal2.transform(fisher(ranks, fusion.weights))
    )

    (paths.reports / "_tmp_fusion_probe.json").write_text(json.dumps(out, indent=2) + "\n")
    print("\nwrote reports/_tmp_fusion_probe.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
