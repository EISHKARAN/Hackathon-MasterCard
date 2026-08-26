"""`make refit-fusion` — find out where the gap between G1 alone and the FUSED score comes from,
and refit the fusion WITHOUT retraining G1 or G2.

THE OBSERVATION THIS EXISTS TO EXPLAIN. At the full preset, `make quick-eval --components` on the
issuer view reported:

    g1 alone        PR-AUC 0.3505   recall@0.1%FPR 0.3133   ROC-AUC 0.7234
    g2_conformal    PR-AUC 0.2753   recall@0.1%FPR 0.2380   ROC-AUC 0.7233
    FUSED (shipped) PR-AUC 0.0862   recall@0.1%FPR 0.1164   ROC-AUC 0.7006
    g2_density      PR-AUC 0.0083   recall@0.1%FPR 0.0015   ROC-AUC 0.6404
    sketch          PR-AUC 0.0044   recall@0.1%FPR 0.0003   ROC-AUC 0.3632   <- BELOW 0.5
    gate_b          PR-AUC 0.0056   recall@0.1%FPR 1.0000   ROC-AUC 0.5000   <- CONSTANT

The shipped score is 4.1x WORSE than its own strongest channel. There are exactly two candidate
mechanisms and they are not mutually exclusive:

  (A) CALIBRATION. Every reported metric is computed on `batch.fused`, the isotonic-calibrated
      probability. `IsotonicCalibrator.transform` (gate/fusion.py:134) is np.interp, so it is
      piecewise LINEAR and order-preserving in the interior -- but it CLAMPS above the last knot and
      maps every row below the first non-zero knot to exactly 0.0. With 30 breakpoints fitted on
      25,505 rows, the bottom flat region is a single enormous tie across the test window. Ranking
      inside a tie is impossible, and PR-AUC is precisely a statement about ranking resolution.

  (B) WEIGHTS. `_fuse_from_ranks` (gate/fusion.py:215) is a weighted arithmetic mean of per-channel
      ECDF ranks. Rank averaging is SCALE-FREE: a channel with weight w can reorder any two rows
      whose rank gap is under w. The top-k rows span a rank gap of only k/n = 641/2,672,910 = 2.4e-4,
      while `sketch` carries w=0.10 -- so sketch alone can move a row ~267,000 rank positions, and
      it is ANTI-predictive at full scale (ROC-AUC 0.3632). The fused top-k is therefore drawn from
      roughly G1's top third and then ORDERED BY THE CHANNELS THAT DO NOT KNOW WHAT FRAUD IS.

Discriminating (A) from (B) needs one number the server build cannot currently produce: the fused
score on the PRE-CALIBRATION axis. This script produces both axes for several weight vectors.

WHY IT IS CHEAP. Changing fusion weights touches `_fuse_from_ranks`, the isotonic calibrator and the
action-table thresholds. It does NOT touch G1, the Mondrian conformal calibration, or ECOD -- those
are loaded from the existing bundle. So the LightGBM fit (167 boosting rounds over 4.5M rows) is not
repeated. The only unavoidable cost is the feature build plus one scoring pass, and this script
CACHES the resulting component arrays, after which every additional weight vector costs seconds
rather than the 2.4 hours a train+quick-eval round trip costs.

THE SELECTION PROTOCOL, WHICH IS THE PART A REVIEWER WILL ATTACK. Weights are chosen on the STATS
window against POINT-IN-TIME labels resolved at `stats_end` -- the same window and the same labels
the isotonic calibrator and the action table are already fitted on, excluding sealed entities. The
TEST window is scored for reporting only and never enters selection. That distinction is enforced
here in code, not asserted in a comment: `_select` is handed the stats arrays and cannot see test.

WHAT THIS IS NOT. It is not a learned stacker, and it is not a fine-grained sweep. The candidate arms
are a SLATE of named design positions, each with a stated reason, because tuning a fusion against
recall measured on our own simulator is the untrustworthy optimisation the design refuses elsewhere
(gate/fusion.py:56). The default arm needs no labels to justify at all: it is what the module's own
docstring already argues for.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

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
from gate.fusion import COMPONENTS, DEFAULT_WEIGHTS, Fusion
from gate.policy import ActionTable, CostMatrix
from gate.scorer import GateBundle, Scorer
from gate.sketches import OnlineStore
from grammar.composition import Composition
from grammar.sealed import load_sealed_manifest

#: Bumped by hand when the cache layout changes, so an old cache is refused rather than misread.
CACHE_VERSION = 1

#: Below this many VISIBLE positives, the stats window cannot support a choice between arms and this
#: script REFUSES to make one.
#:
#: This is not a defensive nicety, it is a measured failure. At the smoke preset the stats window
#: holds 10 visible positives and k collapses to 1, so precision@k is 0/1 or 1/1 and PR-AUC swings on
#: single events: selection picked the `equal` arm, which is the WORST arm on the test window
#: (0.0153 vs 0.0285 for the best). An automatic choice made on 10 positives is a coin flip wearing
#: the costume of a protocol. At the full preset the stats window is ~990k rows and this will not
#: bind; if it ever does bind again, the honest output is "I cannot tell", not a number.
MIN_STATS_POSITIVES = 200

#: Arms whose stats-window PR-AUC is within this RELATIVE band of the best are treated as tied, and
#: the simplicity tiebreak in `_select` decides between them. 1% is well inside the sampling noise of
#: a PR-AUC estimated from ~3,000 visible positives.
TIE_RELATIVE_TOLERANCE = 0.01


def _arms() -> list[dict]:
    """The candidate slate. Every arm carries the REASON it is on the list.

    Renormalisation is left to `_fuse_from_ranks`, which divides by the sum of the present weights
    (gate/fusion.py:219), so these do not have to sum to 1.
    """
    cur = dict(DEFAULT_WEIGHTS)
    return [
        {
            "name": "current",
            "weights": cur,
            "reason": "the shipped DEFAULT_WEIGHTS. The baseline every other arm must beat.",
        },
        {
            "name": "g1_only",
            "weights": {"g1": 1.0, "g2_conformal": 0.0, "g2_density": 0.0, "sketch": 0.0,
                        "gate_b": 0.0},
            "reason": (
                "IMPLEMENTS THE MODULE'S OWN DOCSTRING. gate/fusion.py:43-53 argues that G1 is the "
                "only supervised channel, that letting the unsupervised channels hold a majority of "
                "the score means the ranking is decided by channels that have never seen a label, "
                "and that their real work is the SEPARATE abstention path. The code then hands them "
                "0.38. This arm needs no label-based justification: it is the stated design."
            ),
        },
        {
            "name": "drop_dead_channels",
            "weights": {"g1": 0.62, "g2_conformal": 0.10, "g2_density": 0.06, "sketch": 0.0,
                        "gate_b": 0.0},
            "reason": (
                "Zeroes only the two channels that are DEFECTIVE rather than merely weak, on "
                "evidence that requires no tuning. `gate_b` is identically constant on this view: "
                "_gate_b_component (gate/scorer.py:245-256) returns zeros when none of its five "
                "beneficiary features is present, and they are among the 73 features ABSENT at the "
                "issuer view -- hence ROC-AUC exactly 0.5000. `sketch` is ANTI-predictive at full "
                "scale (ROC-AUC 0.3632), so its 0.10 actively inverts ordering. Between them they "
                "hold 0.22 of the weight. Keeps the shipped ratio among the surviving channels."
            ),
        },
        {
            "name": "g1_conformal_90_10",
            "weights": {"g1": 0.90, "g2_conformal": 0.10, "g2_density": 0.0, "sketch": 0.0,
                        "gate_b": 0.0},
            "reason": "Does the second-strongest channel (PR-AUC 0.2753) add anything at a weight "
                      "small enough that it cannot reorder the top-k? k/n = 2.4e-4 << 0.10, so this "
                      "is a real question, not a rhetorical one.",
        },
        {
            "name": "g1_conformal_75_25",
            "weights": {"g1": 0.75, "g2_conformal": 0.25, "g2_density": 0.0, "sketch": 0.0,
                        "gate_b": 0.0},
            "reason": "The two channels have near-identical ROC-AUC (0.7234 vs 0.7233) but differ in "
                      "PR-AUC, which means they disagree about the TAIL. If the disagreement is "
                      "complementary this arm wins; if conformal is a noisier copy of G1 it loses.",
        },
        {
            "name": "equal",
            "weights": {c: 1.0 for c in COMPONENTS},
            "reason": (
                "The equal-weight ablation arm. gate/fusion.py:57 claims `eval/ablations.py` "
                "publishes this; that file DOES NOT EXIST (eval/ablations/ is an empty directory), "
                "so the claim has never been true. Including it here makes the citation honest."
            ),
        },
        {
            "name": "fisher_current_weights",
            "weights": cur,
            "tail": True,
            "reason": (
                "WEIGHTED FISHER COMBINATION at the shipped weights: -log(1-rank) instead of rank. "
                "Attacks the pathology at its cause rather than by muting channels -- a weak channel "
                "keeps its weight but can only spend it near its OWN extreme, so it can no longer "
                "reorder G1's top-k from the middle of its distribution. Parameter-free (Fisher "
                "1932), fits nothing, so the no-tuning position survives."
            ),
        },
        {
            "name": "fisher_drop_dead",
            "weights": {"g1": 0.62, "g2_conformal": 0.10, "g2_density": 0.06, "sketch": 0.0,
                        "gate_b": 0.0},
            "tail": True,
            "reason": "Fisher combination AND the two defective channels zeroed. The tail transform "
                      "cannot rescue a channel that is constant (gate_b) or inverted (sketch); it "
                      "only stops them reordering from mid-distribution.",
        },
    ]


def _cache_dir(view: str) -> Path:
    return paths.data / "cache" / "fusion" / view


# --------------------------------------------------------------------------------------------
# Phase 1: compute the component arrays once.
# --------------------------------------------------------------------------------------------
def dump_components(view: str, generator: str) -> dict:
    """Score the STATS and TEST windows through the EXISTING bundle and cache the raw components.

    This reproduces gate/cli.py's construction exactly -- same split, same sealed-entity holdout,
    same point-in-time label resolution, same component call order -- because a component array
    built any other way would not be the one the shipped fusion was fitted against.
    """
    cfg = load_config()
    reg = load_registry()

    cols = prepare_columns(_load_events(generator))
    ts = cols["ts"]
    split = temporal_split(ts)
    train_end = float(ts[split.train].max()) if split.train.any() else float(ts.max())
    stats_end = float(ts[split.stats].max()) if split.stats.any() else train_end
    deploy_ts = float(ts[split.test].min()) if split.test.any() else train_end

    table = _load_label_table(generator)
    y_train_pit, _a_train = _resolve_labels(table, cols["event_id"], deploy_ts)
    y_stats_pit, _a_stats = _resolve_labels(table, cols["event_id"], stats_end)

    # ---- the sealed holdout, replicated EXACTLY -------------------------------------------
    # BOTH components are load-bearing and gate/cli.py:168-172 says so: (a) the sealed ENTITY pool,
    # and (b) sealed COMPOSITIONS / the withheld EVASION morpheme. Omitting (b) would put sealed
    # compositions into the window a parameter is selected on, which is the leak this whole design
    # exists to prevent, and it is why an earlier caching script that omitted it was deleted.
    manifest = load_sealed_manifest()
    holdout = cols["entity_pool"].astype(str) == "sealed"
    gstr = cols["attack_grammar_str"].astype(str)
    seen: dict[str, bool] = {}
    for i, g in enumerate(gstr):
        if not g or holdout[i]:
            continue
        if g not in seen:
            try:
                seen[g] = manifest.is_sealed(Composition.parse(g))
            except Exception:  # noqa: BLE001
                seen[g] = False
        holdout[i] = seen[g]

    stats_mask = split.stats & ~holdout
    print(f"  stats rows (sealed excluded) : {int(stats_mask.sum()):,}")
    print(f"  test rows                    : {int(split.test.sum()):,}")
    print(f"  sealed rows excluded         : {int(holdout.sum()):,}")

    ref = fit_reference_stats(cols, y_train_pit, train_mask=split.train, holdout_mask=holdout)
    fm = build_matrix(cols, ref)
    fm_view = fm.subset_features(reg.features_for_view(view))

    bundle_dir = paths.models / f"gate-i_{view}"
    if not (bundle_dir / "bundle_meta.json").exists():
        raise SystemExit(f"{bundle_dir} not found -- run `make train VIEW={view}` first")
    bundle = GateBundle.load(bundle_dir)
    if tuple(bundle.feature_names) != tuple(fm_view.names):
        raise SystemExit(
            "REFUSING TO CONTINUE: the bundle's feature names disagree with the matrix this tree "
            f"builds ({len(bundle.feature_names)} vs {len(fm_view.names)}). The feature code changed "
            f"since `make train VIEW={view}` ran, so the cached G1 would be scored on a different "
            "matrix than it was fitted on. Retrain before refitting the fusion."
        )

    st_idx = np.flatnonzero(stats_mask)
    if st_idx.size == 0:
        raise SystemExit("empty stats window; nothing to select weights on")

    out: dict[str, np.ndarray] = {}
    for tag, idx in (("stats", st_idx), ("test", np.flatnonzero(split.test))):
        # A FRESH OnlineStore per window. The sketch channel is stateful (gate/sketches.py), so
        # reusing one store would let the test pass observe the stats window's fan-out and the two
        # arrays would no longer be independently interpretable.
        sc = Scorer(bundle, cfg=cfg, store=OnlineStore())
        sub = fm_view.subset_rows(np.isin(np.arange(len(fm_view)), idx))
        # Same call ORDER as gate/cli.py:307-313. `_conformal` consumes the G1 score, so the order
        # is not cosmetic.
        g1 = sc._g1_scores(sub)
        _p, novelty = sc._conformal(sub, g1)
        comp = {
            "g1": g1,
            "g2_conformal": novelty,
            "g2_density": sc._density(sub),
            "sketch": sc._sketch(sub),
            "gate_b": sc._gate_b_component(sub),
        }
        for c, v in comp.items():
            out[f"{tag}__{c}"] = np.asarray(v, dtype=np.float64)
        out[f"{tag}__rail"] = np.asarray(sub.meta["rail"], dtype=object)
        out[f"{tag}__amount_inr"] = np.asarray(sub.meta["amount_inr"], dtype=np.float64)
        print(f"  scored {tag}: {len(sub):,} rows")

    out["stats__y_pit"] = y_stats_pit[st_idx].astype(np.int8)
    out["test__y_oracle"] = cols["oracle_is_attack"].astype(np.int8)[split.test]
    out["meta__version"] = np.asarray([CACHE_VERSION, len(fm_view.names)], dtype=np.int64)
    out["meta__names"] = np.asarray(list(fm_view.names), dtype=object)

    d = _cache_dir(view)
    d.mkdir(parents=True, exist_ok=True)
    np.savez(d / "components.npz", allow_pickle=True, **out)
    print(f"  wrote {(d / 'components.npz').relative_to(paths.root)}")
    return {"stats_rows": int(st_idx.size), "test_rows": int(split.test.sum())}


def load_components(view: str) -> dict:
    p = _cache_dir(view) / "components.npz"
    if not p.exists():
        raise SystemExit(f"no component cache for view={view}; run without --grid-only first")
    z = np.load(p, allow_pickle=True)
    d = {k: z[k] for k in z.files}
    if int(d["meta__version"][0]) != CACHE_VERSION:
        raise SystemExit("component cache has a stale layout version; delete it and re-dump")
    return d


# --------------------------------------------------------------------------------------------
# Phase 2: evaluate the slate. Selection sees STATS ONLY.
# --------------------------------------------------------------------------------------------
def _metrics(y: np.ndarray, s: np.ndarray, k_share: float, target_fpr: float) -> dict:
    y = np.asarray(y).astype(int)
    # Rows with no visible label are UNLABELLED, not negative. Scoring them as negatives would
    # measure the model against an absence of evidence. On the stats window that is most rows.
    vis = y >= 0
    yv, sv = y[vis], np.asarray(s, dtype=np.float64)[vis]
    if yv.sum() == 0 or yv.sum() == yv.size:
        return {"n": int(yv.size), "n_pos": int(yv.sum()), "degenerate": True}
    k = max(1, int(round(k_share * yv.size)))
    r = recall_at_fpr(yv, sv, target_fpr)
    return {
        "n": int(yv.size),
        "n_pos": int(yv.sum()),
        "pr_auc": float(average_precision(yv, sv)),
        "roc_auc": float(roc_auc(yv, sv)),
        "recall_at_target_fpr": float(r["recall"]),
        "realised_fpr": float(r["realised_fpr"]),
        "precision_at_k": float(
            precision_at_k(yv, sv, k=k, k_provenance="staffed alert budget from config/ops.yaml")[
                "precision_at_k"
            ]
        ),
        "degenerate": False,
    }


def _fit_arm(
    d: dict, weights: dict, *, tail: bool = False
) -> tuple[Fusion, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Fit a fusion at these weights on the stats window; return both axes on both windows.

    The calibrator is refitted PER ARM and that is not optional. Its knots live on the fused axis, so
    reusing the shipped calibrator against a new axis produces a score that looks spectacular and is
    meaningless -- measured during review as recall 0.7789 at a realised FPR of 0.4328, because every
    row above the last stored knot ties at y_[-1] and no threshold can be placed inside the tie.
    """
    comps_stats = {c: d[f"stats__{c}"] for c in COMPONENTS}
    comps_test = {c: d[f"test__{c}"] for c in COMPONENTS}
    y_st = d["stats__y_pit"].astype(int)
    f = Fusion(weights=dict(weights), tail_transform=bool(tail))
    f = f.fit(comps_stats, labels=np.where(y_st < 0, -1, y_st))
    st_rank = f.combine(comps_stats)
    te_rank = f.combine(comps_test)
    return f, st_rank, f.calibrator.transform(st_rank), te_rank, f.calibrator.transform(te_rank)


def _bands_feasible(d: dict, fusion: Fusion, cfg) -> dict:
    """Would this arm still yield an intact friction <= review <= decline ladder on every rail?

    THIS IS A HARD FEASIBILITY CONSTRAINT ON SELECTION, and it is label-free: it asks only whether
    the action table can still be expressed as three distinct bands, never whether the arm scores
    well. Measured at the full preset, `g1_only` collapses the ladder on `card-clearing-dispute`
    (8.07% of volume, 388 visible positives) and `agentic-commerce`, converting each rail's ENTIRE
    friction band into auto-declines -- because `t_friction` is the top cap_share of the whole rail
    while `t_review`/`t_decline` are global, and `_enforce_ordering` (gate/policy.py:400) reconciles
    the conflict by raising decline UP to meet friction. An arm that does that is not shippable no
    matter what its PR-AUC is, so it must be excluded BEFORE ranking rather than caught afterwards.
    """
    comps = {c: d[f"stats__{c}"] for c in COMPONENTS}
    y = d["stats__y_pit"].astype(int)
    at = ActionTable.fit(
        fusion.score(comps),
        [str(x) for x in d["stats__rail"]],
        d["stats__amount_inr"].astype(np.float64),
        np.where(y < 0, -1.0, y.astype(float)),
        cfg=cfg, costs=CostMatrix.from_config(cfg),
        population_label="feasibility probe",
    )
    bd = at.assert_bands_distinct()
    rails = sorted({r.split(":")[0] for r in bd["collapsed"]})
    return {"ok": not bd["any_collapsed"], "collapsed_rails": rails,
            "n_collapsed_rails": len(rails)}


def _select(arms: list[dict], stats_scored: dict[str, dict], n_stats_pos: int) -> tuple[str, str]:
    """Pick an arm using the STATS window only. Cannot see test: it is not passed in.

    Returns (chosen_or_empty, why). An EMPTY choice is a real outcome, not an error.

    Ordered on PR-AUC of the RANK axis. PR-AUC rather than ROC-AUC because at a 0.56% base rate
    ROC-AUC is dominated by the vast benign majority and barely moves (0.7006 vs 0.7234 across a
    4.1x PR-AUC gap, which is exactly why ROC-AUC alone hid this). The rank axis rather than the
    calibrated one because the calibrator is refitted per arm, so comparing calibrated scores
    compares two different quantisations as well as two different weightings.
    """
    if n_stats_pos < MIN_STATS_POSITIVES:
        return "", (
            f"REFUSED: the stats window has {n_stats_pos} visible positives, below the "
            f"{MIN_STATS_POSITIVES} needed for the arms to be distinguishable. Selecting here would "
            f"be noise. Name an arm explicitly, or run at a preset whose stats window carries labels."
        )
    ok = [a for a in arms if not stats_scored[a["name"]]["rank"].get("degenerate", True)]
    if not ok:
        return "", "REFUSED: every arm was degenerate on the stats window (no visible positives)."

    # FEASIBILITY FIRST, ranking second. An arm that collapses the ladder cannot be shipped, so it
    # is removed from consideration rather than ranked and then vetoed at commit time.
    feasible = [a for a in ok if stats_scored[a["name"]].get("bands", {}).get("ok", True)]
    if not feasible:
        broken = ", ".join(
            f"{a['name']}({'/'.join(stats_scored[a['name']]['bands']['collapsed_rails'])})"
            for a in ok
        )
        return "", (
            "REFUSED: EVERY arm collapses the three-band ladder on at least one rail, so none is "
            f"shippable as-is [{broken}]. This points at gate/policy.py rather than at the fusion: "
            "the friction threshold is the top cap_share of a whole rail while review and decline "
            "are global, so a rail whose tail scores high loses both its friction and review bands. "
            "Fix the friction derivation to span only the band below t_review -- the same correction "
            "already applied to the review band at gate/policy.py:371 -- then re-run."
        )
    dropped = [a["name"] for a in ok if a not in feasible]
    ok = feasible
    top = max(stats_scored[a["name"]]["rank"]["pr_auc"] for a in ok)

    # TIEBREAK ON SIMPLICITY, and it is pre-registered here rather than chosen after seeing the test
    # column. At the full preset `g1_only` and `fisher_drop_dead` came out TIED on the stats window
    # (both 0.3665) while differing by 0.028 on test -- so whichever arm a bare `max()` happened to
    # return would have been decided by dict ordering, not by evidence. Among arms statistically
    # indistinguishable on the selection window, prefer:
    #   1. the fewest ACTIVE channels  -- fewer moving parts, fewer ways to be wrong at serve time;
    #   2. no tail transform           -- the plain rank average is the simpler, older rule;
    #   3. higher stats PR-AUC         -- only as a final, deterministic ordering.
    # This is Occam applied to a tie, which is ordinary model selection. It is NOT a peek at test:
    # the rule is stated in code, applies to any tie, and never reads the test arrays.
    band = top * (1.0 - TIE_RELATIVE_TOLERANCE)
    tied = [a for a in ok if stats_scored[a["name"]]["rank"]["pr_auc"] >= band]
    tied.sort(key=lambda a: (
        sum(1 for w in a["weights"].values() if w > 0.0),
        bool(a.get("tail")),
        -stats_scored[a["name"]]["rank"]["pr_auc"],
    ))
    best = tied[0]["name"]
    note = ""
    if dropped:
        note += (f"; EXCLUDED as ladder-infeasible: {', '.join(dropped)}")
    if len(tied) > 1:
        note += (f"; {len(tied)} arms were within {TIE_RELATIVE_TOLERANCE:.0%} of the best "
                 f"({', '.join(a['name'] for a in tied)}) and the SIMPLICITY tiebreak chose this one")
    return best, (
        f"highest stats-window PR-AUC on the rank axis "
        f"({stats_scored[best]['rank']['pr_auc']:.4f} vs best {top:.4f}) over {n_stats_pos:,} "
        f"visible positives{note}"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="make refit-fusion", description=__doc__)
    ap.add_argument("--view", default="issuer")
    ap.add_argument("--generator", default="vajra-sim")
    ap.add_argument("--target-fpr", type=float, default=0.001)
    ap.add_argument("--grid-only", action="store_true",
                    help="skip the feature build and reuse the cached component arrays (seconds)")
    ap.add_argument("--allow-band-collapse", action="store_true",
                    help="commit even if the refitted action table collapses a band (recorded)")
    ap.add_argument("--write", metavar="ARM", default="",
                    help="COMMIT this arm into the bundle. Omit for a read-only report. "
                         "Use 'auto' to commit whichever arm selection chose on the stats window.")
    args = ap.parse_args(argv)

    cfg = load_config()
    paths.ensure_writable()

    with stage("refit-fusion", f"view={args.view}") as summary:
        print("\n=== VAJRA FUSION REFIT — no G1/G2 retrain ===")
        if not args.grid_only:
            print("\n  --- scoring the existing bundle over stats + test (this is the slow part) ---")
            dump_components(args.view, args.generator)
        d = load_components(args.view)

        y_st = d["stats__y_pit"].astype(int)
        y_te = d["test__y_oracle"].astype(int)
        print(f"\n  stats window : {y_st.size:,} rows, {int((y_st == 1).sum()):,} visible positives, "
              f"{float((y_st < 0).mean()):.2%} UNLABELLED")
        print(f"  test window  : {y_te.size:,} rows, {int(y_te.sum()):,} oracle attacks "
              f"(base rate {y_te.mean():.4%})")

        ks = float(cfg.alert_budget_share)

        # ---- the reference ceiling: G1 alone, no fusion at all ----------------------------
        g1_te = _metrics(y_te, d["test__g1"], ks, args.target_fpr)
        print("\n  --- REFERENCE (test, oracle): the strongest single channel, unfused ---")
        print(f"    g1 alone            PR-AUC {g1_te['pr_auc']:.4f}  "
              f"recall@{args.target_fpr:.1%}FPR {g1_te['recall_at_target_fpr']:.4f}  "
              f"p@k {g1_te['precision_at_k']:.4f}  ROC-AUC {g1_te['roc_auc']:.4f}")

        arms = _arms()
        stats_scored: dict[str, dict] = {}
        test_scored: dict[str, dict] = {}
        fitted: dict[str, Fusion] = {}
        for a in arms:
            f, st_r, st_c, te_r, te_c = _fit_arm(d, a["weights"], tail=bool(a.get("tail")))
            fitted[a["name"]] = f
            stats_scored[a["name"]] = {
                "rank": _metrics(y_st, st_r, ks, args.target_fpr),
                "calibrated": _metrics(y_st, st_c, ks, args.target_fpr),
                "bands": _bands_feasible(d, f, cfg),
            }
            test_scored[a["name"]] = {
                "rank": _metrics(y_te, te_r, ks, args.target_fpr),
                "calibrated": _metrics(y_te, te_c, ks, args.target_fpr),
                "n_breakpoints": int(f.calibrator.x_.size),
                "distinct_calibrated_values": int(np.unique(te_c).size),
            }

        # ---- the safety check the tail transform lives or dies on --------------------------
        # A channel whose top tie holds a large share of the population hands that entire tie the
        # maximum tail bonus at once, which floods the queue with a block far bigger than k. Print it
        # before anyone reads the arm table, so a tail arm that wins for the wrong reason is visible.
        sat = fitted["current"].saturation_report({c: d[f"test__{c}"] for c in COMPONENTS})
        print("\n  --- CHANNEL SATURATION ON TEST (decides whether a tail arm is trustworthy) ---")
        print(f"    {'channel':<16} {'share at rank 1.0':>18} {'distinct ranks':>15}")
        for c, s in sat["channels"].items():
            flag = "  <- FLOODS THE QUEUE" if s["share_at_rank_1"] > 0.001 else ""
            print(f"    {c:<16} {s['share_at_rank_1']:>18.4%} {s['n_distinct_ranks']:>15,}{flag}")

        n_stats_pos = int((y_st == 1).sum())
        print("\n  --- SELECTION (stats window, point-in-time labels, sealed excluded) ---")
        print(f"    {'arm':<22} {'PR-AUC(rank)':>13} {'p@k(rank)':>11}  ladder")
        for a in arms:
            m = stats_scored[a["name"]]["rank"]
            b = stats_scored[a["name"]]["bands"]
            lad = "ok" if b["ok"] else f"INFEASIBLE ({', '.join(b['collapsed_rails'])})"
            if m.get("degenerate"):
                print(f"    {a['name']:<22} {'DEGENERATE (no visible positives)':>25}  {lad}")
            else:
                print(f"    {a['name']:<22} {m['pr_auc']:>13.4f} {m['precision_at_k']:>11.4f}  {lad}")
        chosen, why = _select(arms, stats_scored, n_stats_pos)
        print(f"\n    SELECTED: {chosen or '(none)'}")
        print(f"    {why}")

        print("\n  --- TEST WINDOW, ORACLE TRUTH. Reporting only; NOT used for selection. ---")
        print("    !! READING THIS COLUMN TO PICK AN ARM *IS* SELECTION ON TEST, and it invalidates")
        print("       the number. If you commit an arm other than the one selected above, the report")
        print("       records the divergence so a reviewer can see it.")
        print(f"    {'arm':<22} {'PR-AUC rank':>12} {'PR-AUC calib':>13} "
              f"{'rec@FPR rank':>13} {'rec@FPR calib':>14} {'distinct':>9}")
        for a in arms:
            t = test_scored[a["name"]]
            r, c = t["rank"], t["calibrated"]
            print(f"    {a['name']:<22} {r['pr_auc']:>12.4f} {c['pr_auc']:>13.4f} "
                  f"{r['recall_at_target_fpr']:>13.4f} {c['recall_at_target_fpr']:>14.4f} "
                  f"{t['distinct_calibrated_values']:>9,}")

        # ---- attribute the gap -----------------------------------------------------------
        cur_r = test_scored["current"]["rank"]["pr_auc"]
        cur_c = test_scored["current"]["calibrated"]["pr_auc"]
        # The BEST arm on test, named only to attribute the gap. It is not a selection: the committed
        # arm is `chosen`, and the report flags any divergence between the two.
        best_on_test = max(
            (a["name"] for a in arms), key=lambda n: test_scored[n]["rank"]["pr_auc"]
        )
        best_r = test_scored[best_on_test]["rank"]["pr_auc"]
        print("\n  --- WHERE THE GAP CAME FROM (test PR-AUC, decomposed) ---")
        print(f"    {'shipped, calibrated axis':<38} {cur_c:.4f}")
        print(f"    {'shipped, rank axis (same weights)':<38} {cur_r:.4f}"
              f"   <- ATTRIBUTABLE TO CALIBRATION: {cur_r - cur_c:+.4f}")
        print(f"    {'g1 alone, unfused':<38} {g1_te['pr_auc']:.4f}")
        print(f"    {'best arm (' + best_on_test + '), rank axis':<38} {best_r:.4f}"
              f"   <- ATTRIBUTABLE TO THE COMBINE RULE: {best_r - cur_r:+.4f}")

        report = {
            "view": args.view,
            "generator": args.generator,
            "selection": {
                "chosen": chosen,
                "why": why,
                "n_stats_visible_positives": n_stats_pos,
                "min_stats_positives_required": MIN_STATS_POSITIVES,
                "window": "stats (point-in-time labels at stats_end, sealed entities excluded)",
                "criterion": "PR-AUC on the pre-calibration rank axis",
                "best_arm_on_test_for_reference_only": best_on_test,
                "stats_selection_agrees_with_test": bool(chosen) and chosen == best_on_test,
            },
            "reference_g1_alone_test": g1_te,
            "channel_saturation_test": sat,
            "arms": [
                {"name": a["name"], "weights": a["weights"],
                 "combine_rule": fitted[a["name"]].diagnostics()["combine_rule"],
                 "reason": a["reason"],
                 "stats": stats_scored[a["name"]], "test": test_scored[a["name"]]}
                for a in arms
            ],
            "gap_attribution_test_pr_auc": {
                "shipped_calibrated": cur_c,
                "shipped_rank": cur_r,
                "chosen_rank": best_r,
                "g1_alone": g1_te["pr_auc"],
                "attributable_to_calibration": cur_r - cur_c,
                "attributable_to_weights": best_r - cur_r,
            },
            "reportable": {
                "is_reportable": False,
                "why": "no baseline replica, no leakage suite, no confidence intervals. "
                       "Run `make eval` after committing an arm.",
            },
        }
        write_json(report, paths.reports / f"fusion_ablation_{args.view}.json")
        print(f"\n  wrote reports/fusion_ablation_{args.view}.json")
        print("    ^ this is the arm table gate/fusion.py:57 has always claimed eval/ablations.py "
              "publishes.")

        # ---- optional commit -------------------------------------------------------------
        if args.write:
            arm = chosen if args.write == "auto" else args.write
            names = [a["name"] for a in arms]
            if args.write == "auto" and not chosen:
                raise SystemExit(
                    "--write auto REFUSED: selection could not choose an arm on the stats window "
                    f"({why}). Name the arm explicitly if you want to commit one anyway; the report "
                    "will record that it was not selected by the protocol."
                )
            if arm not in names:
                raise SystemExit(f"unknown arm {arm!r}; expected one of {names} or 'auto'")
            if chosen and arm != chosen:
                print(f"\n  !! COMMITTING {arm!r}, WHICH IS NOT THE ARM SELECTION CHOSE ({chosen!r}).")
                print("     This is recorded in reports/fusion_ablation_*.json as a divergence.")
            report["selection"]["committed"] = arm
            report["selection"]["committed_arm_was_selected_by_protocol"] = arm == chosen
            write_json(report, paths.reports / f"fusion_ablation_{args.view}.json")
            _commit(args.view, arm, fitted[arm], d, cfg,
                    allow_band_collapse=bool(args.allow_band_collapse))
            summary["committed"] = arm
        else:
            target = chosen or "<arm-name>"
            print("\n  READ-ONLY. Nothing was written to the bundle. Re-run with "
                  f"--grid-only --write {target} to commit (the existing fusion is backed up).")

        summary.update({"chosen": chosen, "test_pr_auc_best_arm_rank": best_r})
    return 0


def _commit(view: str, arm: str, fusion: Fusion, d: dict, cfg, *,
            allow_band_collapse: bool = False) -> None:
    """Write the new fusion and a REFITTED action table into both persona bundles.

    The action table MUST be refitted: its thresholds live on the calibrated fused scale
    (gate/policy.py, `fitted_on_scale`), and both the weights and the calibrator just changed.
    Keeping the old thresholds against a new score is how a band silently collapses.
    """
    comps_stats = {c: d[f"stats__{c}"] for c in COMPONENTS}
    y_st = d["stats__y_pit"].astype(int)
    fused_stats = fusion.score(comps_stats)
    at = ActionTable.fit(
        fused_stats,
        [str(x) for x in d["stats__rail"]],
        d["stats__amount_inr"].astype(np.float64),
        np.where(y_st < 0, -1.0, y_st.astype(float)),
        cfg=cfg,
        costs=CostMatrix.from_config(cfg),
        population_label=f"stats/calibration window at operating prevalence (fusion arm={arm})",
    )
    print(f"\n  --- REFITTED ACTION TABLE (arm={arm}) ---")
    print(f"    thresholds: review={at.global_t_review:.6g} friction={at.global_t_friction:.6g} "
          f"decline={at.global_t_decline:.6g}")
    cap = at.capacity_report
    print(f"    realised REVIEW-BAND share {cap.get('realised_review_band_share', 0.0):.4%} "
          f"vs staffed budget {cfg.alert_budget_share:.4%}")
    bd = at.assert_bands_distinct()
    if bd["any_collapsed"]:
        # gate/cli.py PUBLISHES a collapse rather than crashing, and this follows that convention --
        # but a commit overwrites a shipped bundle, so the default here is to refuse and make the
        # operator say so out loud. A collapsed band means two of the three actions are the same
        # threshold, i.e. the three-band story cannot be told for that rail.
        print(f"    !! BAND COLLAPSE (published): {bd['collapsed'][:6]}")
        if not allow_band_collapse:
            raise SystemExit(
                "REFUSING TO COMMIT: the refitted action table has a collapsed band, so the "
                "friction <= review <= decline guarantee no longer holds for the rails listed above. "
                "Either pick a different arm, or pass --allow-band-collapse to commit anyway (the "
                "collapse is then recorded in action_table.json and surfaces in `make report`)."
            )
        print("    proceeding under --allow-band-collapse; the collapse is recorded, not hidden.")

    for persona in ("gate-i", "gate-b"):
        out = paths.models / f"{persona}_{view}"
        if not (out / "bundle_meta.json").exists():
            print(f"    skipped {persona}_{view} (not present)")
            continue
        backup = out.parent / f"{out.name}.prefusion-{arm}"
        if not backup.exists():
            shutil.copytree(out, backup)
            print(f"    backed up {out.name} -> {backup.name}")
        b = GateBundle.load(out)
        b.fusion = fusion
        b.action_table = at
        b.save(out)
        print(f"    rewrote {out.name} (fusion_meta.json, fusion_ecdf.npz, action_table.json)")
    print("\n  COMMITTED. Re-run `make quick-eval` to confirm, then `make eval` for reportable "
          "numbers, then `make report && make bundle`.")


if __name__ == "__main__":
    sys.exit(main())
