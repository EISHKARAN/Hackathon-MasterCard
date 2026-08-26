"""Temporal forward splits with purge and embargo, entity-disjoint folds, label-maturity weighting.

TIME-FORWARD ONLY. NO RANDOM SPLITS, ANYWHERE, EVER. A random split on payment data leaks the future
through entity aggregates — the same card, device, merchant and campaign appear on both sides of the
boundary — so it measures interpolation WITHIN a campaign rather than detection OF a campaign. It is
the single mechanism by which a 0.99 AUC is manufactured.

FIVE WINDOWS, and the fifth is the one most designs omit:

    TRAIN        the model window
    PURGE        dropped entirely, so an event whose label matures inside the boundary cannot be in
                 both windows through its own label
    STATS        the fifth holdout channel, for STATISTICS ONLY: cohort baselines, quantile edges,
                 scalers, the isotonic calibrator and the conformal calibration set
    EMBARGO      dropped, so a trailing 30d aggregate computed on a test row cannot reach back into
                 the training window
    TEST         evaluated, never fitted on

Without the STATS channel, the calibrator and the conformal calibration set are fitted on the
training window and every threshold inherits the training window's prevalence. Without the EMBARGO,
a test row's own 30-day velocity baseline is computed from training rows, which is a leak no entity-id
audit can see because no id crosses the boundary — only a window does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

#: Default window shares. Sum to 1.0; the purge and embargo are real cost, paid deliberately.
DEFAULT_SHARES: dict[str, float] = {
    "train": 0.55,
    "purge": 0.04,
    "stats": 0.10,
    "embargo": 0.04,
    "test": 0.27,
}


@dataclass
class TemporalSplit:
    """Boolean masks over the event stream, plus the boundary timestamps for the report."""

    train: np.ndarray
    purge: np.ndarray
    stats: np.ndarray
    embargo: np.ndarray
    test: np.ndarray
    boundaries: dict[str, float]
    n_total: int
    purge_days: float
    embargo_days: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_total": self.n_total,
            "counts": {
                "train": int(self.train.sum()),
                "purge_dropped": int(self.purge.sum()),
                "stats": int(self.stats.sum()),
                "embargo_dropped": int(self.embargo.sum()),
                "test": int(self.test.sum()),
            },
            "shares": {
                k: float(getattr(self, k).sum()) / max(1, self.n_total)
                for k in ("train", "purge", "stats", "embargo", "test")
            },
            "boundaries_ts": self.boundaries,
            "purge_days": self.purge_days,
            "embargo_days": self.embargo_days,
            "policy": (
                "TIME-FORWARD ONLY. No random splits anywhere. The STATS window is a fifth holdout "
                "channel used only for reference statistics, the calibrator and the conformal "
                "calibration set, so no threshold inherits the training window's prevalence."
            ),
        }

    def assert_disjoint(self) -> None:
        stack = np.vstack([self.train, self.purge, self.stats, self.embargo, self.test])
        overlaps = stack.sum(axis=0)
        if (overlaps > 1).any():
            raise AssertionError(
                f"{int((overlaps > 1).sum())} rows are in more than one window. The windows must "
                f"partition the stream, or 'never fitted on' is not a property of the test set."
            )
        if (overlaps == 0).any():
            raise AssertionError(
                f"{int((overlaps == 0).sum())} rows are in no window. Silently dropping rows would "
                f"change every denominator in the metrics table without appearing anywhere."
            )


def temporal_split(
    ts: np.ndarray,
    *,
    shares: Mapping[str, float] | None = None,
) -> TemporalSplit:
    """Split by TIME, in the fixed order train / purge / stats / embargo / test."""
    t = np.asarray(ts, dtype=np.float64)
    n = t.size
    sh = dict(shares or DEFAULT_SHARES)
    total = sum(sh.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"split shares must sum to 1.0, got {total:.6f}")

    order = ("train", "purge", "stats", "embargo", "test")
    qs: dict[str, float] = {}
    acc = 0.0
    for k in order:
        acc += sh[k]
        qs[k] = float(np.quantile(t, min(acc, 1.0))) if n else 0.0

    masks: dict[str, np.ndarray] = {}
    lo = -np.inf
    for k in order:
        hi = qs[k]
        # The LAST window is closed on the right so the maximum timestamp is included; every other
        # window is half-open. Otherwise the single latest event belongs to no window.
        masks[k] = (t > lo) & (t <= hi) if k == "test" else (t > lo) & (t <= hi)
        lo = hi
    # Everything below the first boundary belongs to train.
    masks["train"] = masks["train"] | (t <= qs["train"])
    # Resolve any residual by assigning to the earliest window that claims it.
    assigned = np.zeros(n, dtype=bool)
    for k in order:
        masks[k] = masks[k] & ~assigned
        assigned |= masks[k]
    masks["test"] = masks["test"] | ~assigned

    day = 86_400.0
    return TemporalSplit(
        train=masks["train"],
        purge=masks["purge"],
        stats=masks["stats"],
        embargo=masks["embargo"],
        test=masks["test"],
        boundaries={k: qs[k] for k in order},
        n_total=n,
        purge_days=float((qs["purge"] - qs["train"]) / day) if n else 0.0,
        embargo_days=float((qs["embargo"] - qs["stats"]) / day) if n else 0.0,
    )


def entity_disjoint_folds(
    entity_ids: Sequence[str],
    ts: np.ndarray,
    n_folds: int = 4,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Time-forward folds that are ALSO entity-disjoint.

    Two constraints at once, and both are necessary:
      * TIME-FORWARD, so a fold never trains on the future;
      * ENTITY-DISJOINT, so an entity's aggregate history cannot appear on both sides.

    Where they conflict — an entity spans the boundary — the ENTITY constraint wins and the entity's
    rows are removed from the validation side. Letting time win would put the same card's velocity
    history on both sides, which is the leak the folds exist to prevent, and we would rather lose
    rows than lose the property.
    """
    ids = np.asarray(entity_ids, dtype=object).astype(str)
    t = np.asarray(ts, dtype=np.float64)
    n = t.size
    if n == 0 or n_folds < 2:
        return []
    order = np.argsort(t, kind="stable")
    bounds = [int(round(n * (i + 1) / (n_folds + 1))) for i in range(n_folds)]
    folds: list[tuple[np.ndarray, np.ndarray]] = []
    for b in bounds:
        tr_idx = order[:b]
        va_idx = order[b : min(n, b + max(1, n // (n_folds + 1)))]
        tr_mask = np.zeros(n, dtype=bool)
        va_mask = np.zeros(n, dtype=bool)
        tr_mask[tr_idx] = True
        va_mask[va_idx] = True
        # Remove from validation any entity that appears in training.
        train_entities = set(ids[tr_mask].tolist())
        overlap = np.asarray([i in train_entities for i in ids], dtype=bool)
        va_mask = va_mask & ~overlap
        if va_mask.sum() == 0:
            continue
        folds.append((tr_mask, va_mask))
    return folds


def label_maturity_weights(
    ts: np.ndarray,
    label_as_of_ts: np.ndarray,
    *,
    window_end_ts: float,
    full_maturity_days: float = 120.0,
) -> np.ndarray:
    """Weight each labelled row by how MATURED its label is at the window end.

    An immature label must not carry the weight of a matured one. A row whose only visible label is
    a fast analyst disposition — noisy, and poisonable by design in this system — is weaker evidence
    than a row with a settled chargeback, and training them equally imports the analyst's error rate
    into the model as if it were ground truth.

    Rows with no visible label get weight 0 here; the PU estimator handles them instead, because
    "no label" is not "legitimate".
    """
    t = np.asarray(ts, dtype=np.float64)
    a = np.asarray(label_as_of_ts, dtype=np.float64)
    w = np.zeros_like(t)
    has = a > 0
    elapsed_days = (float(window_end_ts) - t[has]) / 86_400.0
    matured = np.clip(elapsed_days / max(full_maturity_days, 1e-9), 0.0, 1.0)
    # Floor at 0.25 so a fresh label still contributes: dropping it entirely would bias the model
    # toward the slow channel's attack mix, which is a different distortion.
    w[has] = 0.25 + 0.75 * matured
    return w


def maturity_report(
    ts: np.ndarray,
    label_as_of_ts: np.ndarray,
    labels: np.ndarray,
    *,
    window_end_ts: float,
) -> dict[str, Any]:
    """Label maturity for a window. REPORTED WITH EVERY WINDOW, without exception.

    Recall against 30% matured labels and recall against 100% are not the same metric, so a report
    that omits maturity is comparing two different quantities and calling them one.
    """
    t = np.asarray(ts, dtype=np.float64)
    a = np.asarray(label_as_of_ts, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    n = t.size
    visible = a > 0
    pos = y == 1
    return {
        "n_rows": int(n),
        "share_with_any_visible_label": float(visible.mean()) if n else 0.0,
        "n_visible_positives": int((visible & pos).sum()),
        "n_unlabelled": int((~visible).sum()),
        "share_unlabelled": float((~visible).mean()) if n else 0.0,
        "window_end_ts": float(window_end_ts),
        "median_days_to_label": (
            float(np.median((a[visible] - t[visible]) / 86_400.0)) if visible.any() else -1.0
        ),
        "note": (
            "Reported with EVERY window. Recall against 30% matured labels and recall against 100% "
            "are not the same metric; the unlabelled share is what the nnPU / Elkan-Noto correction "
            "is applied to, because absence of a label is not evidence of legitimacy."
        ),
    }
