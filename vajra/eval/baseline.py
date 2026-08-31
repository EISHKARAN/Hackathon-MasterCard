"""The baseline-equivalent replica — an in-repo reconstruction of the submission most of the field
will make, scored through the IDENTICAL harness.

THE BASELINE IS NOT DESCRIBED, IT IS EXECUTED NEXT TO US. That is the direct attack on the field:
"their headline would be 0.99 AUC" is an assertion, while running their methodology on our data and
showing what its PR-AUC and precision@k actually are is a measurement.

WHAT MAKES IT A BASELINE, and every one of these is a METHODOLOGY choice rather than a capability
handicap:

  1.  **RANDOM STRATIFIED SPLIT**, not time-forward. The same card, device, merchant and campaign
      appear on both sides, so it measures interpolation within a campaign.
  2.  **FULLY MATURED LABELS**, resolved at the END of all time rather than point-in-time. This is
      the future-label leak, and it is the default behaviour of every notebook.
  3.  **UNLABELLED TREATED AS NEGATIVE.** No PU correction: absence of a label is read as evidence of
      legitimacy.
  4.  **NO REJECT INFERENCE.** Trains on approved traffic as though it were a random sample.
  5.  **NO G0, NO G2, NO GATE-B.** A single tabular model, no invariant guards, no abstention, no
      beneficiary side.
  6.  **THRESHOLD AT A ROUND QUANTILE**, not from a cost matrix under a capacity constraint.

WHAT WE DELIBERATELY DO **NOT** HANDICAP:
  * It gets the SAME feature matrix and the SAME library (LightGBM). Using a weaker library or fewer
    features would confound methodology with capability and make the comparison worthless — and a
    reviewer would be right to say so. The ONLY differences are the six above.
  * It gets the same hyper-parameters.

That is what makes the delta attributable to methodology. `reports/metrics.md` prints both its
flattering headline (ROC-AUC on its own random split) and its honest one (PR-AUC and precision@k on
OUR time-forward test set), side by side. The gap between those two numbers is the whole argument.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

from gate.g1_tabular import G1Config, fit_g1
from eval.metrics import (
    average_precision,
    precision_at_k,
    recall_at_fpr,
    recall_precision_f1,
    roc_auc,
)


@dataclass
class BaselineReplica:
    """The replica model, plus the two numbers it would report and the two it should."""

    model: Any
    feature_names: tuple[str, ...]
    #: The metrics IT would put on a slide, computed the way IT would compute them.
    self_reported: dict[str, Any] = field(default_factory=dict)
    #: The same model, scored through OUR harness on OUR time-forward test set, restricted to rows
    #: the replica did NOT train on.
    honest: dict[str, Any] = field(default_factory=dict)
    #: The CONTAMINATED number: our test window WITHOUT removing the replica's own training rows.
    #: Reported deliberately, because the gap between it and `honest` is a direct measurement of what
    #: a random split costs you.
    contaminated: dict[str, Any] = field(default_factory=dict)
    n_train: int = 0
    n_test_random: int = 0
    n_test_clean: int = 0
    contamination_share: float = 0.0

    #: Boolean mask ALIGNED TO OUR TEST WINDOW's row order, true where the replica never trained.
    #:
    #: WHY THIS IS EXPOSED. Without it there is no way to score BOTH arms on the same uncontaminated
    #: rows against the same truth, and every replica comparison is either contaminated (our window
    #: including rows it memorised) or incomparable (its `honest` block, which uses matured labels
    #: over a different population). `random_test_share=0.25` means the replica trains on 75% of all
    #: rows, so roughly three quarters of our test window is memorised — a comparison on that window
    #: measures the replica's recall of its own training data and nothing about generalisation.
    clean_within_test: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool), repr=False)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict(X)

    def as_dict(self) -> dict[str, Any]:
        return {
            "methodology": {
                "split": "RANDOM STRATIFIED (not time-forward)",
                "labels": "FULLY MATURED, resolved at the end of all time (future-label leak)",
                "unlabelled_rows": "TREATED AS NEGATIVE (no PU correction)",
                "reject_inference": "NONE (approved traffic treated as a random sample)",
                "detector_stack": "G1 only — no G0 guards, no G2 abstention, no GATE-B",
                "threshold": "round quantile, not a cost matrix under a capacity constraint",
            },
            "not_handicapped": {
                "features": "IDENTICAL feature matrix",
                "library": "IDENTICAL library (LightGBM)",
                "hyperparameters": "IDENTICAL",
                "why": (
                    "Using a weaker library or fewer features would confound methodology with "
                    "capability and make the comparison worthless. The only differences are the six "
                    "methodology choices above, which is what makes the delta attributable."
                ),
            },
            "n_train": self.n_train,
            "n_test_random": self.n_test_random,
            "n_test_clean": self.n_test_clean,
            "contamination_share_of_our_test_window": self.contamination_share,
            "self_reported_headline": self.self_reported,
            "honest_metrics_on_our_test_set": self.honest,
            "contaminated_metrics_on_our_test_set": self.contaminated,
            "the_argument": (
                "Three numbers from ONE model, one feature matrix and one library. (1) "
                "`self_reported_headline.roc_auc`: what a random-split submission puts on a slide. "
                "(2) `contaminated_metrics_on_our_test_set`: the same model on our time-forward test "
                "window WITHOUT removing the rows it already trained on -- this is what happens if "
                "you evaluate a random-split model on a temporal holdout naively, and "
                f"it is inflated because a share of that window was in its own training set. "
                "(3) `honest_metrics_on_our_test_set`: the same model on the rows it genuinely never "
                "saw. The gap between (2) and (3) is a DIRECT MEASUREMENT of what a random split "
                "buys you, and the gap between (1) and (3) is what the whole protocol buys."
            ),
        }


def fit_baseline_replica(
    X: np.ndarray,
    feature_names: Sequence[str],
    *,
    y_matured: np.ndarray,
    test_mask_ours: np.ndarray,
    amounts: np.ndarray,
    alert_budget_k: int,
    random_test_share: float = 0.25,
    config: G1Config | None = None,
) -> BaselineReplica:
    """Fit the replica and compute both its flattering and its honest numbers.

    `y_matured` is the FULLY MATURED label vector — deliberately not point-in-time, because that is
    the baseline's methodology and reproducing it faithfully is the point.
    """
    from core.rng import stream

    names = tuple(feature_names)
    y = np.asarray(y_matured).astype(int)
    # (3) unlabelled treated as NEGATIVE. The whole point of the baseline.
    y_bin = np.where(y == 1, 1, 0).astype(int)

    # (1) RANDOM stratified split, ignoring time entirely.
    rng = stream("eval.splits")
    n = X.shape[0]
    idx = np.arange(n)
    pos_idx = idx[y_bin == 1]
    neg_idx = idx[y_bin == 0]
    rng.shuffle(pos_idx)
    rng.shuffle(neg_idx)
    n_pos_test = max(1, int(len(pos_idx) * random_test_share))
    n_neg_test = max(1, int(len(neg_idx) * random_test_share))
    test_idx = np.concatenate([pos_idx[:n_pos_test], neg_idx[:n_neg_test]])
    train_idx = np.concatenate([pos_idx[n_pos_test:], neg_idx[n_neg_test:]])
    rng.shuffle(train_idx)

    cfg = config or G1Config()
    model = fit_g1(
        X[train_idx],
        y_bin[train_idx],
        names,
        config=cfg,
        use_nnpu=False,          # (3) no PU correction
        pi_positive=None,
        version="baseline-replica",
    )

    # ---- what IT would report: ROC-AUC on its own random split ------------------------
    s_rand = model.predict(X[test_idx])
    y_rand = y_bin[test_idx]
    self_reported = {
        "split": "random stratified",
        "roc_auc": roc_auc(y_rand, s_rand),
        "accuracy_at_0_5": recall_precision_f1(y_rand, s_rand, 0.5)["accuracy"],
        "note": (
            "THIS is the headline a random-split submission puts on a slide. It is computed on a "
            "split where the same entities appear on both sides and against fully matured labels."
        ),
    }

    # ---- what it SHOULD report: our harness, our test set, MINUS its own training rows ----
    # A random split spans the whole timeline, so some of our time-forward test window WAS in the
    # replica's training set. Scoring it there measures memorisation, not generalisation, and would
    # make the replica look better than GATE for the wrong reason. We report BOTH: the contaminated
    # number (because it is what a naive comparison would print) and the clean one.
    tm = np.asarray(test_mask_ours, dtype=bool)
    trained_on = np.zeros(n, dtype=bool)
    trained_on[train_idx] = True
    clean = tm & ~trained_on
    contamination_share = float((tm & trained_on).sum() / max(1, tm.sum()))

    s_contam = model.predict(X[tm])
    y_contam = y_bin[tm]
    contaminated = {
        "evaluated_on": "our time-forward test window, INCLUDING rows the replica trained on",
        "contamination_share": contamination_share,
        "pr_auc": average_precision(y_contam, s_contam),
        "roc_auc": roc_auc(y_contam, s_contam),
        "why_reported": (
            "This is what a naive comparison would print, and it is INFLATED: a random split spans "
            "the whole timeline, so this share of our test window was in the replica's own training "
            "set. Reported so the inflation is visible rather than inherited."
        ),
    }

    if clean.sum() < 20 or int((y_bin[clean] == 1).sum()) == 0:
        honest = {
            "evaluated_on": "OUR time-forward test window, minus the replica's own training rows",
            "reportable": False,
            "why": (
                f"only {int(clean.sum())} of our test rows were outside the replica's training set "
                f"({int((y_bin[clean] == 1).sum())} positives), which is too few to estimate. At a "
                f"larger preset this becomes reportable; at this size we say so rather than quoting "
                f"a number from a handful of rows."
            ),
            "n_clean_rows": int(clean.sum()),
        }
        return BaselineReplica(
            model=model, feature_names=names, self_reported=self_reported,
            honest=honest, contaminated=contaminated,
            n_train=int(train_idx.size), n_test_random=int(test_idx.size),
            n_test_clean=int(clean.sum()), contamination_share=contamination_share,
            clean_within_test=clean[tm],
        )

    s_ours = model.predict(X[clean])
    y_ours = y_bin[clean]
    r = recall_at_fpr(y_ours, s_ours, 0.001)
    honest = {
        "evaluated_on": "OUR time-forward test window, minus the replica's own training rows",
        "reportable": True,
        "n_clean_rows": int(clean.sum()),
        "pr_auc": average_precision(y_ours, s_ours),
        "roc_auc": roc_auc(y_ours, s_ours),
        "recall_at_0_1pct_fpr": r,
        "precision_at_k": precision_at_k(
            y_ours, s_ours, k=alert_budget_k,
            k_provenance=(
                "derived from config/ops.yaml staffing (analysts x cases x shifts), scaled to this "
                "test population — the same k GATE is scored at"
            ),
        ),
        "at_round_quantile_threshold": recall_precision_f1(
            y_ours, s_ours, float(np.quantile(s_ours, 0.99)) if s_ours.size else 0.5
        ),
        "note": (
            "Same model, same features, same library. The only differences are the six methodology "
            "choices, and this is what they cost."
        ),
    }

    return BaselineReplica(
        model=model,
        feature_names=names,
        self_reported=self_reported,
        honest=honest,
        contaminated=contaminated,
        n_train=int(train_idx.size),
        n_test_random=int(test_idx.size),
        n_test_clean=int(clean.sum()),
        contamination_share=contamination_share,
        clean_within_test=clean[tm],
    )


def incumbent_scores_as_detector(incumbent_score: np.ndarray) -> np.ndarray:
    """The modelled incumbent's own score, used as the second comparison arm.

    Every detection metric is reported as a delta against BOTH the incumbent and the replica, because
    a good incumbent would flatter us and a straw man would be dishonest. The incumbent's score is
    normalised to [0,1] here so it lives on a comparable axis; its ORDERING is what the comparison
    uses, and a monotone rescale cannot change that.
    """
    s = np.asarray(incumbent_score, dtype=np.float64)
    valid = s > -1.0
    out = np.zeros_like(s)
    if valid.any():
        lo, hi = float(s[valid].min()), float(s[valid].max())
        span = max(hi - lo, 1e-9)
        out[valid] = (s[valid] - lo) / span
    return out
