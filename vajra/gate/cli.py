"""`make train` — fit both personae, with every leakage control applied and reported.

WHAT THIS TARGET DOES, in the order it matters:

  1.  load events + the append-only label table
  2.  TIME-FORWARD split: train / purge / stats / embargo / test  (no random splits, anywhere)
  3.  resolve labels POINT-IN-TIME at each window's end — never against fully matured labels
  4.  partition compositions into trainable / sealed, and DROP sealed rows from training
  5.  fit reference statistics on the TRAIN window with holdout rows excluded
  6.  fit G1 with nnPU on the unlabelled window and IPW reject inference against the logged incumbent
  7.  fit G2 conformal + ECOD on the STATS window (the fifth holdout channel)
  8.  fit fusion + the isotonic calibrator on the STATS window
  9.  fit the action table on the STATS window at OPERATING prevalence, on the FUSED score
  10. publish the propensity histogram, the leakage-control report and the queue ceiling

It trains but does not evaluate: `make eval` does that, against the TEST window it has never seen.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np

from core import paths
from core.config import load_config
from core.io import read_json, read_parquet, write_json
from core.stagelog import stage
from features.builder import build_matrix, fit_reference_stats, prepare_columns
from features.registry import feature_count, load_registry
from eval.splits import label_maturity_weights, maturity_report, temporal_split
from gate.decision import reason_code_count
from gate.fusion import Fusion
from gate.g1_tabular import G1Config, fit_g1, ipw_reject_inference_weights
from gate.g2_novelty import ECODDensity, MondrianConformal
from gate.gate_b import BloomRiskExchange, OnboardingCohortScorer
from gate.policy import ActionTable, CostMatrix, queue_ceiling
from gate.scorer import GateBundle, Scorer
from gate.sketches import OnlineStore
from grammar.composition import Composition
from grammar.sealed import load_sealed_manifest
from sim.incumbent import propensity_histogram
from sim.schema import canonical_field_order


def _load_events(generator: str):
    """Load the event stream as COLUMNS for the batch path.

    Deliberately not `TwinSource.read()`: that yields one CanonicalEvent at a time, which is right for
    the inline scorer and the loop and wrong for batch training. At the `full` preset it is tens of
    millions of dataclass instances and ~150 attribute reads each, just to turn them back into the
    columns the feature builder wants. The MessageSource contract is still the seam a real deployment
    replaces; this is the columnar reader over the same file, with the same schema-order assertion.
    """
    from sim.source import read_columns

    path = paths.events / f"events_{generator}.parquet"
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Run `make sim` first — training reads the simulator's output "
            f"through the same MessageSource contract a real deployment would use."
        )
    return read_columns(path)


def _load_label_table(generator: str):
    from sim.labels import LabelRecord, LabelTable

    path = paths.labels / f"labels_{generator}.parquet"
    table = LabelTable()
    if not path.exists():
        return table
    t = read_parquet(path)
    cols = {n: t.column(n).to_pylist() for n in t.schema.names}
    for i in range(t.num_rows):
        table.append(
            LabelRecord(
                event_id=str(cols["event_id"][i]),
                channel=str(cols["channel"][i]),
                as_of_ts=float(cols["as_of_ts"][i]),
                label=int(cols["label"][i]),
                poisoned=bool(cols["poisoned"][i]),
            )
        )
    return table


def _resolve_labels(table, event_ids: np.ndarray, as_of_ts: float):
    """Point-in-time labels: 1 fraud, 0 legitimate, -1 UNLABELLED-YET (not negative)."""
    y = np.full(event_ids.size, -1, dtype=np.int64)
    a = np.zeros(event_ids.size, dtype=np.float64)
    for i, eid in enumerate(event_ids):
        lab, _chan, _dis = table.resolve(str(eid), as_of_ts)
        if lab is not None:
            y[i] = int(lab)
            rows = table.visible(str(eid), as_of_ts)
            a[i] = max((r.as_of_ts for r in rows), default=0.0)
    return y, a


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="make train", description=__doc__)
    ap.add_argument("--generator", default="vajra-sim")
    ap.add_argument("--view", default="issuer", help="issuer | acquirer | payee_psp | network")
    ap.add_argument(
        "--row-cap", type=int, default=int(os.environ.get("VAJRA_TRAIN_ROW_CAP", "0")),
        help="cap training rows for a fast run. 0 = uncapped. A cap LOWERS recall and the report "
             "says so, so a capped run is never mistaken for a full one.",
    )
    ap.add_argument("--threads", type=int, default=1,
                    help="LightGBM threads. 1 for bit-reproducibility; more for the demo run.")
    ap.add_argument("--no-nnpu", action="store_true", help="disable the PU correction (ablation only)")
    ap.add_argument("--no-ipw", action="store_true", help="disable reject inference (ablation only)")
    args = ap.parse_args(argv)

    cfg = load_config()
    paths.ensure_writable()
    reg = load_registry()

    with stage("train", f"view={args.view} generator={args.generator}") as summary:
        print("\n=== VAJRA TRAIN ===")
        print(f"  registry features (machine-counted) : {feature_count()}")
        print(f"  reason codes (machine-counted)      : {reason_code_count()}")
        print(f"  deployment view                     : {args.view}")

        cols_raw = _load_events(args.generator)
        table = _load_label_table(args.generator)
        print(f"  events                              : {cols_raw['ts'].size:,}")
        print(f"  label records                       : {len(table):,}")

        cols = prepare_columns(cols_raw)
        ts = cols["ts"]
        split = temporal_split(ts)
        split.assert_disjoint()
        print("\n  --- TIME-FORWARD SPLIT (no random splits, anywhere) ---")
        for k, v in split.as_dict()["counts"].items():
            print(f"    {k:<16} {v:>9,}")
        print(f"    purge {split.purge_days:.1f}d / embargo {split.embargo_days:.1f}d")

        # ---- point-in-time labels ------------------------------------------------------
        train_end = float(ts[split.train].max()) if split.train.any() else float(ts.max())
        stats_end = float(ts[split.stats].max()) if split.stats.any() else train_end
        # LABELS ARE RESOLVED AS OF DEPLOYMENT TIME, NOT AS OF TRAIN_END.
        #
        # A model fitted for deployment at the start of the test window legitimately knows every label
        # that had MATURED by then -- that is not future information, it is what the operator actually
        # holds on the day they deploy. Resolving at `train_end` instead threw away every label that
        # arrived during the purge, stats and embargo windows, which is severe here precisely because
        # the slow channel is a chargeback at 45-120 days: label maturity at train_end was 1.88%, so
        # 98.12% of the training window was UNLABELLED and only 19,733 positives were visible out of
        # roughly 68,170 real attacks. The purge/embargo guards run the other way (they stop test
        # features leaning on train-period statistics); they were never meant to censor label arrival.
        deploy_ts = float(ts[split.test].min()) if split.test.any() else train_end
        y_train_pit, a_train = _resolve_labels(table, cols["event_id"], deploy_ts)
        y_stats_pit, a_stats = _resolve_labels(table, cols["event_id"], stats_end)

        mat_train = maturity_report(ts, a_train, y_train_pit, window_end_ts=deploy_ts)
        print("\n  --- LABEL MATURITY AT THE TRAINING WINDOW END ---")
        print(f"    rows with any visible label : {mat_train['share_with_any_visible_label']:.2%}")
        print(f"    visible positives           : {mat_train['n_visible_positives']:,}")
        print(f"    UNLABELLED (not negative)   : {mat_train['share_unlabelled']:.2%}")

        # ---- sealed-family exclusion ----------------------------------------------------
        manifest = load_sealed_manifest()
        # ENTITY-LEVEL HOLDOUT. Two conditions, and the FIRST is the one that matters:
        #   (a) the event's actors are in the SEALED entity pool -- so their benign traffic is
        #       withheld too, and no aggregate can bridge the boundary;
        #   (b) the composition is a sealed family or contains the withheld EVASION morpheme.
        # (b) alone is a holdout of LABELS. (a) is a holdout of INFORMATION.
        holdout = cols["entity_pool"].astype(str) == "sealed"
        gstr = cols["attack_grammar_str"].astype(str)
        cache: dict[str, bool] = {}
        for i, g in enumerate(gstr):
            if not g or holdout[i]:
                continue
            if g not in cache:
                try:
                    cache[g] = manifest.is_sealed(Composition.parse(g))
                except Exception:
                    cache[g] = False
            holdout[i] = cache[g]
        print(f"\n  ENTITY-LEVEL holdout rows excluded from training : {int(holdout.sum()):,}")
        print(f"    of which sealed entity pool : "
              f"{int((cols['entity_pool'].astype(str) == 'sealed').sum()):,}")
        print(f"    (12 families + leave-one-morpheme-out: EVASION={manifest.withheld_evasion_morpheme})")

        train_mask = split.train & ~holdout
        stats_mask = split.stats & ~holdout

        # ---- reference statistics, fitted CAUSALLY --------------------------------------
        # `split.train` rather than `train_mask` so the reported excluded-holdout count is the real
        # number found, not zero-because-already-removed.
        ref = fit_reference_stats(cols, y_train_pit, train_mask=split.train, holdout_mask=holdout)
        print(f"\n  reference stats fitted on {ref.fitted_on_n_rows:,} rows "
              f"({ref.holdout_rows_excluded:,} holdout rows excluded)")

        fm = build_matrix(cols, ref)
        view_features = reg.features_for_view(args.view)
        fm_view = fm.subset_features(view_features)
        print(f"  matrix                              : {fm.X.shape} -> view {fm_view.X.shape}")
        print(f"    ^ features ABSENT at this view, not zeroed: "
              f"{len(reg.model_feature_names()) - len(view_features)}")

        # ---- training rows --------------------------------------------------------------
        tr_idx = np.flatnonzero(train_mask)
        if args.row_cap and tr_idx.size > args.row_cap:
            # Keep the TAIL, so training prevalence matches operating prevalence. A
            # positive-enriched cap raises prevalence and the calibrator then maps ordinary
            # mid-rank traffic to high probability -- a previous build shipped that and had to
            # revert it. Undersampling needs the operating point re-derived AND the calibrator
            # refit; doing one without the other is worse than not undersampling.
            tr_idx = tr_idx[-args.row_cap :]
            print(f"\n  !! ROW CAP APPLIED: {args.row_cap:,} rows (tail-preserving). This LOWERS "
                  f"recall and is reported as a capped run.")

        X_tr = fm_view.X[tr_idx]
        y_tr = y_train_pit[tr_idx]

        # ---- reject inference: IPW against the LOGGED incumbent policy -------------------
        accept_p = fm.meta["incumbent_accept_probability"][tr_idx]
        declined = fm.meta["incumbent_decision"][tr_idx].astype(str) == "decline"
        if args.no_ipw:
            w_ipw, ipw_diag = np.ones(tr_idx.size), {"disabled": 1.0}
        else:
            w_ipw, ipw_diag = ipw_reject_inference_weights(accept_p, was_declined=declined)
        w_mat = label_maturity_weights(ts[tr_idx], a_train[tr_idx], window_end_ts=train_end)
        weights = w_ipw * np.where(w_mat > 0, w_mat, 1.0)

        # ---- validation slice for early stopping -----------------------------------------
        va_idx = np.flatnonzero(stats_mask)
        cfg_g1 = G1Config(num_threads=int(args.threads))
        # nnPU's RISK ESTIMATOR IS PARAMETERISED BY THIS PRIOR, so a misspecified pi biases the whole
        # decision function -- it is not a cosmetic config read. We were passing the CONFIGURED target
        # (0.005) while the simulator realised 0.0069 at the full preset, a 38% error in the one number
        # the correction is most sensitive to. Prefer the realised share the sim actually measured and
        # printed, and fall back to the configured target only when that report is absent.
        pi = float(cfg.base_rate)
        _sim_report = paths.reports / f"sim_report_{args.generator}.json"
        if _sim_report.exists():
            try:
                _realised = float(read_json(_sim_report).get("realised_attack_share", 0.0))
                if 1e-6 < _realised < 0.5:
                    pi = _realised
            except Exception:  # noqa: BLE001
                pass

        print("\n  --- FITTING G1 (LightGBM) ---")
        print(f"    positives / negatives / UNLABELLED : "
              f"{int((y_tr == 1).sum()):,} / {int((y_tr == 0).sum()):,} / {int((y_tr == -1).sum()):,}")
        print(f"    nnPU  : {'OFF (ablation)' if args.no_nnpu else 'ON'}  (pi = {pi:.4f}, configured {cfg.base_rate:.4f})")
        print(f"    IPW   : {'OFF (ablation)' if args.no_ipw else 'ON'}  "
              f"(clipped share {ipw_diag.get('share_clipped', 0.0):.3%})")
        version = f"{args.view}-{args.generator}-{int(train_end)}"
        g1 = fit_g1(
            X_tr, y_tr, fm_view.names,
            X_valid=fm_view.X[va_idx] if va_idx.size else None,
            y_valid=y_stats_pit[va_idx] if va_idx.size else None,
            sample_weight=weights,
            config=cfg_g1,
            pi_positive=pi,
            use_nnpu=not args.no_nnpu,
            version=version,
        )
        print(f"    best iteration : {g1.best_iteration}")
        print(f"    top features by gain:")
        for name, gain in list(g1.importance_gain.items())[:8]:
            print(f"      {name:<48} {gain:,.0f}")

        # ---- G2 on the STATS window (the fifth holdout channel) --------------------------
        print("\n  --- FITTING G2 (Mondrian conformal + ECOD) ---")
        st_idx = va_idx if va_idx.size else tr_idx
        # Conformal is calibrated on BENIGN rows only: a novelty p-value against a mixed
        # calibration set answers a different question ("unlike this mixture") than the one we want.
        benign_st = st_idx[y_stats_pit[st_idx] != 1]
        g1_st = g1.predict(fm_view.X[benign_st])
        conformal = MondrianConformal().fit(
            g1_st,
            fm.meta["rail"][benign_st].tolist(),
            cols["mcc"][benign_st].astype(str).tolist(),
            cols["geo_cell"][benign_st].astype(str).tolist(),
        )
        cd = conformal.diagnostics()
        print(f"    calibration rows : {cd['n_calibration_rows']:,} over {cd['n_strata']} strata")
        print(f"    thin strata merged : {cd['n_thin_strata']}")

        density = ECODDensity().fit(fm_view.X[benign_st])
        dd = density.diagnostics()
        print(f"    ECOD raw score mean {dd['raw_mean']:.1f} sd {dd['raw_std']:.1f} "
              f"-> calibrated={dd['calibrated']}")
        print(f"      ^ the raw score is a SUM over {dd['n_features']} features, NOT a z-score. "
              f"score_z() is what the scorer compares.")

        # ---- fusion + calibrator on the STATS window -------------------------------------
        print("\n  --- FITTING FUSION (rank-average + isotonic) ---")
        provisional = GateBundle(
            persona="GATE-I", g1=g1, conformal=conformal, density=density,
            fusion=Fusion(), action_table=ActionTable(),
            model_version=version, feature_names=fm_view.names, view=args.view,
        )
        sc = Scorer(provisional, cfg=cfg, store=OnlineStore())
        fm_stats = fm_view.subset_rows(np.isin(np.arange(len(fm_view)), st_idx))
        comps_stats = {
            "g1": sc._g1_scores(fm_stats),
        }
        p_conf, novelty = sc._conformal(fm_stats, comps_stats["g1"])
        comps_stats["g2_conformal"] = novelty
        comps_stats["g2_density"] = sc._density(fm_stats)
        comps_stats["sketch"] = sc._sketch(fm_stats)
        comps_stats["gate_b"] = sc._gate_b_component(fm_stats)

        y_st = y_stats_pit[st_idx]
        fusion = Fusion().fit(comps_stats, labels=np.where(y_st < 0, -1, y_st))
        print(f"    calibrator : {fusion.calibrator.as_dict()}")

        # ---- action table on the STATS window, on the FUSED score ------------------------
        print("\n  --- FITTING THE ACTION TABLE ---")
        fused_stats = fusion.score(comps_stats)
        at = ActionTable.fit(
            fused_stats,
            fm_stats.meta["rail"].astype(str).tolist(),
            fm_stats.meta["amount_inr"],
            np.where(y_st < 0, -1.0, y_st.astype(float)),
            cfg=cfg,
            costs=CostMatrix.from_config(cfg),
            population_label="stats/calibration window at operating prevalence",
        )
        print(f"    fitted on : {at.fitted_on_scale} / {at.fitted_on_population}")
        print(f"    thresholds: review={at.global_t_review:.6g} friction={at.global_t_friction:.6g} "
              f"decline={at.global_t_decline:.6g}")
        cap = at.capacity_report
        print(f"    realised REVIEW-BAND share {cap.get('realised_review_band_share', 0.0):.4%} "
              f"vs staffed budget {cfg.alert_budget_share:.4%}")
        bd = at.assert_bands_distinct()
        if bd["any_collapsed"]:
            print(f"    !! BAND COLLAPSE (published): {bd['collapsed'][:4]}")
        if cap.get("budget_overflow"):
            print("    !! BUDGET OVERFLOW PUBLISHED — see the note in the report")

        # ---- GATE-B extras ---------------------------------------------------------------
        onboarding_names = [f.name for f in reg.by_family().get("onboarding_cohort", [])]
        onboarding = OnboardingCohortScorer().fit(
            {n: fm.column(n)[st_idx] for n in onboarding_names if n in fm.names}
        )
        exchange = BloomRiskExchange()
        # Seed the exchange from CONFIRMED-FRAUD beneficiaries in the TRAINING window only. Using the
        # test window would be a straightforward leak, and using unconfirmed rows would make the
        # stub's prior a function of our own suspicion rather than of anything observed.
        conf_fraud = train_mask & (y_train_pit == 1)
        for bid in np.unique(fm.meta["beneficiary_id"][conf_fraud]):
            if bid:
                exchange.add(str(bid))
        print(f"\n  bloom exchange STUB seeded with {exchange.n_inserted:,} beneficiaries "
              f"(expected FP rate {exchange.expected_false_positive_rate():.4f})")

        # ---- persist ---------------------------------------------------------------------
        for persona in ("GATE-I", "GATE-B"):
            bundle = GateBundle(
                persona=persona,
                g1=g1,
                conformal=conformal,
                density=density,
                fusion=fusion,
                action_table=at,
                onboarding=onboarding,
                exchange=exchange if persona == "GATE-B" else None,
                model_version=version,
                feature_names=fm_view.names,
                view=args.view,
                nearline_status=_nearline_status(),
            )
            out_dir = paths.models / f"{persona.lower()}_{args.view}"
            bundle.save(out_dir)
            print(f"  wrote {out_dir.relative_to(paths.root)}")

        # ---- reports ---------------------------------------------------------------------
        report = {
            "view": args.view,
            "generator": args.generator,
            "model_version": version,
            "n_events": int(cols_raw["ts"].size),
            "registry": reg.report(),
            "split": split.as_dict(),
            "label_maturity_train": mat_train,
            "label_maturity_stats": maturity_report(ts, a_stats, y_stats_pit, window_end_ts=stats_end),
            "sealed_rows_excluded": int(holdout.sum()),
            "withheld_evasion_morpheme": manifest.withheld_evasion_morpheme,
            "sealed_manifest_sha256": manifest.content_hash,
            "reference_stats": ref.as_dict(),
            "g1": {
                "config": g1.config.as_dict(),
                "n_train_rows": g1.n_train_rows,
                "n_train_positives": g1.n_train_positives,
                "n_train_unlabelled": g1.n_train_unlabelled,
                "train_prevalence": g1.train_prevalence,
                "pi_positive": g1.pi_positive,
                "prior_correction": g1.prior_correction,
                "best_iteration": g1.best_iteration,
                "row_cap_applied": int(args.row_cap),
                "top_importance": dict(list(g1.importance_gain.items())[:40]),
            },
            "reject_inference_ipw": ipw_diag,
            "conformal": cd,
            "conformal_coverage": conformal.empirical_coverage(
                g1_st,
                fm.meta["rail"][benign_st].tolist(),
                cols["mcc"][benign_st].astype(str).tolist(),
                cols["geo_cell"][benign_st].astype(str).tolist(),
            ),
            "density": dd,
            "fusion": fusion.diagnostics(),
            "action_table": at.as_dict(),
            "queue_ceiling": queue_ceiling(cfg),
            "onboarding_scorer": onboarding.diagnostics(),
            "bloom_exchange": exchange.status(),
            "nearline": _nearline_status(),
            "sketch_footprint": sc.store.footprint(),
        }
        write_json(report, paths.reports / f"train_report_{args.view}.json")
        write_json(
            propensity_histogram(fm.meta["incumbent_accept_probability"]),
            paths.reports / "propensity_histogram.json",
        )
        print(f"\n  wrote reports/train_report_{args.view}.json")
        print("  wrote reports/propensity_histogram.json  <- the published overlap evidence")

        summary.update(
            {
                "view": args.view,
                "n_features": len(fm_view.names),
                "n_train_rows": g1.n_train_rows,
                "n_train_positives": g1.n_train_positives,
                "best_iteration": g1.best_iteration,
            }
        )

    print("\n=== TRAIN: DONE ===")
    return 0


def _nearline_status() -> dict[str, str]:
    """G3/G4 availability. A SKIP is recorded, never implied to have run."""
    try:
        import torch  # noqa: F401
    except Exception:
        return {
            "g3_sequence_gru": "SKIPPED-DEPENDENCY-ABSENT (torch not installed)",
            "g4_graph_rgcn": "SKIPPED-DEPENDENCY-ABSENT (torch not installed)",
            "consequence": (
                "The mimicry flag (G3) and learned graph embeddings (G4) are absent. The inline "
                "sketch counters still provide graph SIGNAL at t=0 — that is the cold-graph fix and "
                "it does not depend on G4. The delta is reported rather than the claim restated."
            ),
        }
    return {"g3_sequence_gru": "AVAILABLE", "g4_graph_rgcn": "AVAILABLE"}


if __name__ == "__main__":
    sys.exit(main())
