"""Build the full feature matrix from a CanonicalEvent stream.

Vectorised over numpy columns. The contract:

    build_matrix(events) -> FeatureMatrix(names, X, event_ids, ts, meta)

and `names` is EXACTLY `features/registry.py::model_feature_names()`, in the registry's order.
A mismatch raises rather than silently reindexing, because a feature-order mismatch between train
and serve is a silent accuracy loss that no metric attributes correctly.

THREE CAUSALITY RULES, all enforced here rather than by convention:

1.  **Every trailing statistic excludes the current row.** A window that included the row would
    leak the row's own amount into its own baseline.
2.  **Every reference statistic is fitted on a TRAINING window and applied forward.** Cohort
    baselines, quantile edges and the three cold-start prior rates are computed by
    `fit_reference_stats()` on the training slice and passed into `build_matrix()`. Computing them
    inside the build over the whole stream is the statistic-level leak that an entity-id audit
    cannot see.
3.  **No feature reads an oracle field.** Enforced structurally: `build_matrix` receives the event
    columns with `ORACLE_FIELDS` stripped, so a feature that tried to read one would raise a
    KeyError rather than quietly work.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

from features.registry import load_registry, model_feature_names
from features.rolling import (
    trailing_distinct_multi as _fast_distinct_multi,
    trailing_max as _fast_max,
    trailing_mean_std as _fast_mean_std,
    trailing_median_approx as _fast_median,
    trailing_sum_count as _fast_sum_count,
)
from features.velocity import NO_HISTORY, WINDOW_SECONDS, compute_panel
from sim.schema import ORACLE_FIELDS, CanonicalEvent, canonical_field_order

#: Entry modes in risk order (low -> high). An ordinal beats a one-hot here because a tree can
#: then split "at or above fallback" in one node instead of learning a disjunction.
_ENTRY_MODE_ORDER: tuple[str, ...] = (
    "chip", "contactless", "biometric_assisted", "secure_intent", "intent", "in_app",
    "qr_dynamic", "collect", "file_upload", "agent", "on_device_ledger", "ecommerce",
    "qr_static", "contactless_no_cvm", "keyed", "magstripe_fallback",
)
_CVM_ORDER: tuple[str, ...] = ("none", "signature", "offline_pin", "online_pin", "cdcvm", "biometric")
_TOKEN_ASSURANCE_ORDER: tuple[str, ...] = ("none", "low", "medium", "high")
_KYC_ORDER: tuple[str, ...] = ("none", "min_kyc", "full_kyc", "video_kyc")
_ATTESTATION_ORDER: tuple[str, ...] = ("not_applicable", "unattested", "self_attested", "attested")
_INITIATION_ORDER: tuple[str, ...] = (
    "not_applicable", "in_app", "intent", "secure_intent", "qr_dynamic", "mandate", "collect",
    "qr_static", "ivr",
)
#: Beneficiary categories in cash-out-risk order.
_BEN_CATEGORY_ORDER: tuple[str, ...] = (
    "payroll", "biller", "corporate_vendor", "small_merchant", "p2p_individual", "unknown",
    "wallet_load", "giftcard", "quasi_cash", "crypto_onramp",
)

_AGE_BANDS: tuple[float, ...] = (1.0, 7.0, 30.0)

_SENTINEL = -1.0


@dataclass
class ReferenceStats:
    """Statistics fitted CAUSALLY on the training window and applied forward.

    Every field here is a leakage surface that an entity-id audit does not cover: a cohort
    baseline or a quantile edge fitted over a pool containing sealed-family rows imports holdout
    information into EVERY training feature without a single id crossing the boundary. So these
    are fitted once, on the training slice, with holdout rows excluded, and then frozen.
    """

    mcc_median_auth_to_presentment: dict[str, float] = field(default_factory=dict)
    bin_prior_rate: dict[str, float] = field(default_factory=dict)
    cohort_prior_rate: dict[str, float] = field(default_factory=dict)
    geo_prior_rate: dict[str, float] = field(default_factory=dict)
    global_prior_rate: float = 0.0
    modal_inter_arrival_log: float = 0.0
    #: Provenance, carried into the report so a judge can see WHAT window they were fitted on.
    fitted_on_n_rows: int = 0
    fitted_window_end_ts: float = 0.0
    holdout_rows_excluded: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_mcc_medians": len(self.mcc_median_auth_to_presentment),
            "n_bin_priors": len(self.bin_prior_rate),
            "n_cohort_priors": len(self.cohort_prior_rate),
            "n_geo_priors": len(self.geo_prior_rate),
            "global_prior_rate": self.global_prior_rate,
            "modal_inter_arrival_log": self.modal_inter_arrival_log,
            "fitted_on_n_rows": self.fitted_on_n_rows,
            "fitted_window_end_ts": self.fitted_window_end_ts,
            "holdout_rows_excluded": self.holdout_rows_excluded,
            "causality_note": (
                "Fitted on the TRAINING WINDOW ONLY with holdout-family rows excluded, then "
                "frozen and applied forward. eval/leakage/statistic_fit.py asserts it."
            ),
        }


@dataclass
class FeatureMatrix:
    names: tuple[str, ...]
    X: np.ndarray                       # shape (n_events, n_features), float32
    event_ids: np.ndarray
    ts: np.ndarray
    #: Non-feature columns the harness needs: oracle truth, cohort tags, rails, audit fields.
    meta: dict[str, np.ndarray] = field(default_factory=dict)

    def __len__(self) -> int:
        return int(self.X.shape[0])

    def column(self, name: str) -> np.ndarray:
        return self.X[:, self.names.index(name)]

    def subset_rows(self, mask: np.ndarray) -> "FeatureMatrix":
        return FeatureMatrix(
            names=self.names,
            X=self.X[mask],
            event_ids=self.event_ids[mask],
            ts=self.ts[mask],
            meta={k: v[mask] for k, v in self.meta.items()},
        )

    def subset_features(self, keep: Sequence[str]) -> "FeatureMatrix":
        """Restrict to a deployment view's feature set. ABSENT, not zeroed.

        Zeroing would tell the model "this entity has no token fan-out", which is a different and
        false statement from "this institution cannot see token fan-out".
        """
        keep_set = [n for n in self.names if n in set(keep)]
        idx = [self.names.index(n) for n in keep_set]
        return FeatureMatrix(
            names=tuple(keep_set),
            X=self.X[:, idx],
            event_ids=self.event_ids,
            ts=self.ts,
            meta=dict(self.meta),
        )


# ---------------------------------------------------------------------------------------
# Column extraction
# ---------------------------------------------------------------------------------------

def events_to_columns(events: Sequence[CanonicalEvent]) -> dict[str, np.ndarray]:
    """Columnar view of the event stream, with a fixed dtype per field."""
    order = canonical_field_order()
    n = len(events)
    out: dict[str, np.ndarray] = {}
    for name in order:
        vals = [getattr(ev, name) for ev in events]
        if n and isinstance(vals[0], bool):
            out[name] = np.asarray(vals, dtype=bool)
        elif n and isinstance(vals[0], (int, np.integer)) and not isinstance(vals[0], bool):
            out[name] = np.asarray(vals, dtype=np.int64)
        elif n and isinstance(vals[0], float):
            out[name] = np.asarray(vals, dtype=np.float64)
        else:
            out[name] = np.asarray(vals, dtype=object).astype(str)
    return out


def strip_oracle(cols: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Remove oracle fields, so a feature that tried to read one raises rather than working."""
    return {k: v for k, v in cols.items() if k not in ORACLE_FIELDS}


# ---------------------------------------------------------------------------------------
# Reference-statistic fitting
# ---------------------------------------------------------------------------------------

def fit_reference_stats(
    cols: Mapping[str, np.ndarray],
    labels: np.ndarray,
    *,
    train_mask: np.ndarray,
    holdout_mask: np.ndarray | None = None,
) -> ReferenceStats:
    """Fit the reference statistics on the training window with holdout rows excluded."""
    fit_mask = np.asarray(train_mask, dtype=bool).copy()
    n_holdout_removed = 0
    if holdout_mask is not None:
        hm = np.asarray(holdout_mask, dtype=bool)
        n_holdout_removed = int((fit_mask & hm).sum())
        fit_mask &= ~hm

    y = np.asarray(labels, dtype=np.float64)
    known = np.isfinite(y) & (y >= 0.0)
    usable = fit_mask & known
    global_rate = float(y[usable].mean()) if usable.any() else 0.0

    def _grouped_rate(key_col: np.ndarray, min_n: int = 30) -> dict[str, float]:
        out: dict[str, float] = {}
        keys = key_col[usable]
        vals = y[usable]
        for k in np.unique(keys):
            if k == "":
                continue
            m = keys == k
            n = int(m.sum())
            if n < min_n:
                continue
            # Shrink toward the global rate: a 30-row group's raw rate is noise, and an
            # unshrunk prior would make the cold-start feature a memorisation channel.
            raw = float(vals[m].mean())
            w = n / (n + float(min_n))
            out[str(k)] = w * raw + (1.0 - w) * global_rate
        return out

    ratio = cols.get("auth_to_presentment_ratio")
    mcc = cols.get("mcc")
    mcc_median: dict[str, float] = {}
    if ratio is not None and mcc is not None:
        valid = fit_mask & (ratio > 0)
        for k in np.unique(mcc[valid]):
            if k == "":
                continue
            m = valid & (mcc == k)
            if m.sum() >= 10:
                mcc_median[str(k)] = float(np.median(ratio[m]))

    ia = cols.get("_inter_arrival_log")
    modal_ia = float(np.median(ia[fit_mask])) if ia is not None and fit_mask.any() else 0.0

    return ReferenceStats(
        mcc_median_auth_to_presentment=mcc_median,
        bin_prior_rate=_grouped_rate(cols["bin_prefix"]),
        cohort_prior_rate=_grouped_rate(cols["_cohort"]),
        geo_prior_rate=_grouped_rate(cols["geo_cell"]),
        global_prior_rate=global_rate,
        modal_inter_arrival_log=modal_ia,
        fitted_on_n_rows=int(fit_mask.sum()),
        fitted_window_end_ts=float(cols["ts"][fit_mask].max()) if fit_mask.any() else 0.0,
        holdout_rows_excluded=n_holdout_removed,
    )


# ---------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------

def _ordinal(col: np.ndarray, order: Sequence[str]) -> np.ndarray:
    lookup = {v: float(i) for i, v in enumerate(order)}
    return np.asarray([lookup.get(str(v), _SENTINEL) for v in col], dtype=np.float64)


def _band(values: np.ndarray, edges: Sequence[float]) -> np.ndarray:
    out = np.full(values.shape, float(len(edges)), dtype=np.float64)
    for i, e in enumerate(reversed(edges)):
        out = np.where(values < e, float(len(edges) - 1 - i), out)
    return np.where(values < 0, _SENTINEL, out)


def _safe_div(a: np.ndarray, b: np.ndarray, fill: float = _SENTINEL) -> np.ndarray:
    b = np.asarray(b, dtype=np.float64)
    return np.where(np.abs(b) > 1e-12, np.asarray(a, dtype=np.float64) / b, fill)


def _prev_by_key(keys: np.ndarray, values: np.ndarray, fill: float = _SENTINEL) -> np.ndarray:
    """For each row, the previous value for the same key. Trailing, excludes the current row."""
    out = np.full(values.shape, fill, dtype=np.float64)
    last: dict[str, float] = {}
    for i in range(keys.size):
        k = keys[i]
        if k == "":
            continue
        if k in last:
            out[i] = last[k]
        last[k] = float(values[i])
    return out


def _prev_str_by_key(keys: np.ndarray, values: np.ndarray) -> np.ndarray:
    out = np.full(keys.shape, "", dtype=object)
    last: dict[str, str] = {}
    for i in range(keys.size):
        k = keys[i]
        if k == "":
            continue
        if k in last:
            out[i] = last[k]
        last[k] = str(values[i])
    return out.astype(str)


def _rolling_cv_by_key(keys: np.ndarray, values: np.ndarray, window: int = 8) -> np.ndarray:
    """Coefficient of variation of an entity's last `window` values, excluding the current row.

    Returns SENTINEL until there are at least 3 prior values: a CV over two points is not a
    dispersion estimate and would put structure where there is none.
    """
    out = np.full(values.shape, _SENTINEL, dtype=np.float64)
    buf: dict[str, list[float]] = {}
    for i in range(keys.size):
        k = keys[i]
        if k == "":
            continue
        hist = buf.get(k)
        if hist and len(hist) >= 3:
            arr = np.asarray(hist[-window:], dtype=np.float64)
            m = float(arr.mean())
            out[i] = float(arr.std() / m) if abs(m) > 1e-12 else _SENTINEL
        buf.setdefault(k, []).append(float(values[i]))
        if len(buf[k]) > window * 2:
            buf[k] = buf[k][-window:]
    return out


def _trailing_mean_by_key(keys, ts, values, window_s):  # noqa: ANN001, ANN201
    """EXACT trailing mean, O(1) per row via prefix sums. See features/rolling.py."""
    return _fast_mean_std(keys, ts, values, window_s)[0]


def _trailing_sum_by_key(keys, ts, values, window_s):  # noqa: ANN001, ANN201
    """EXACT trailing sum, O(1) per row via prefix sums."""
    return _fast_sum_count(keys, ts, values, window_s)[0]


def _count_matching_in_window(
    keys: np.ndarray,
    ts: np.ndarray,
    window_s: float,
    *,
    only_where: np.ndarray | None = None,
) -> np.ndarray:
    """Count of prior rows sharing this key within the trailing window.

    `only_where` restricts BOTH the counted population and the rows that receive a value, which is
    how "mandate creations for this payee in 24h" is expressed without counting debits.
    """
    n = keys.size
    out = np.full(n, _SENTINEL, dtype=np.float64)
    mask = np.ones(n, dtype=bool) if only_where is None else np.asarray(only_where, dtype=bool)
    groups: dict[str, list[int]] = {}
    for i in range(n):
        if not mask[i]:
            continue
        k = keys[i]
        if k != "":
            groups.setdefault(k, []).append(i)
    for idx_list in groups.values():
        idx = np.asarray(idx_list, dtype=np.int64)
        g_ts = ts[idx]
        lo = np.searchsorted(g_ts, g_ts - window_s, side="left")
        out[idx] = (np.arange(idx.size) - lo).astype(np.float64)
    if only_where is None:
        out = np.where(out < 0, 0.0, out)
    return out


# These three delegate to features/rolling.py. The naive per-row implementations were O(m log m) per
# row for a window of size m -- QUADRATIC in the group size -- and at the `full` preset a hub merchant
# with 100k events made the build appear to HANG rather than fail. See that module for which are exact
# and which one is a documented approximation.
def _trailing_median_by_key(keys, ts, values, window_s):  # noqa: ANN001, ANN201
    """APPROXIMATE: bounded 64-observation trailing buffer. See features/rolling.py."""
    return _fast_median(keys, ts, values, window_s)


def _trailing_std_by_key(keys, ts, values, window_s):  # noqa: ANN001, ANN201
    """EXACT, via prefix sums."""
    return _fast_mean_std(keys, ts, values, window_s)[1]


def _trailing_max_by_key(keys, ts, values, window_s):  # noqa: ANN001, ANN201
    """EXACT, via a monotone deque."""
    return _fast_max(keys, ts, values, window_s)


def _trailing_distinct_by_key(keys, ts, values, window_s):  # noqa: ANN001, ANN201
    """EXACT trailing distinct count, amortised O(1) per row."""
    return _fast_distinct_multi(keys, ts, values, [float(window_s)])[float(window_s)]


def _modal_str_by_key(keys: np.ndarray, values: np.ndarray) -> np.ndarray:
    """The modal value of `values` per key, assigned to every row of that key.

    Not point-in-time: it is a property of the key's whole history. Used only for STRUCTURAL
    comparisons (does this event's descriptor / geo cell / note match this merchant's usual one?),
    and listed in the strict-causality exclusions in eval/leakage/statistic_fit.py for that reason.
    """
    counts: dict[str, dict[str, int]] = {}
    for i in range(keys.size):
        k = keys[i]
        if k == "":
            continue
        d = counts.setdefault(k, {})
        v = str(values[i])
        d[v] = d.get(v, 0) + 1
    modal: dict[str, str] = {k: max(d.items(), key=lambda kv: kv[1])[0] for k, d in counts.items()}
    return np.asarray([modal.get(keys[i], "") for i in range(keys.size)], dtype=object).astype(str)


def _last_true_ts_by_key(keys: np.ndarray, ts: np.ndarray, flag: np.ndarray) -> np.ndarray:
    """Timestamp of this key's most recent event where `flag` was true, before the current row."""
    out = np.full(keys.shape, _SENTINEL, dtype=np.float64)
    last: dict[str, float] = {}
    fl = np.asarray(flag, dtype=bool)
    for i in range(keys.size):
        k = keys[i]
        if k == "":
            continue
        if k in last:
            out[i] = last[k]
        if fl[i]:
            last[k] = float(ts[i])
    return out


def _percentile_within_cohort_local(values: np.ndarray, cohort: np.ndarray) -> np.ndarray:
    """Percentile of a value within its cohort, ties averaged. Same semantics as the velocity
    module's version; duplicated here rather than imported so the two can diverge if the
    velocity panel ever needs a different tie rule, and so this module has no import cycle."""
    out = np.zeros(values.shape, dtype=np.float64)
    for cid in np.unique(cohort):
        mask = cohort == cid
        v = np.asarray(values[mask], dtype=np.float64)
        if v.size <= 1:
            out[mask] = 0.5
            continue
        uniq, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
        starts = np.concatenate(([0], np.cumsum(cnt)[:-1]))
        mean_rank = starts + (cnt - 1) / 2.0
        out[mask] = mean_rank[inv] / max(1.0, v.size - 1)
    return out



def _div(num: np.ndarray, den: np.ndarray, cond: np.ndarray, fill: float = _SENTINEL) -> np.ndarray:
    """Divide only where `cond`, writing `fill` elsewhere.

    `np.where(cond, a/b, fill)` evaluates a/b EVERYWHERE and then discards the bad half, which
    emits a divide-by-zero warning for every sentinel row. Suppressing the warning globally would
    also hide a real division bug, so we do the arithmetic only where it is defined.
    """
    out = np.full(np.broadcast(num, den).shape, float(fill), dtype=np.float64)
    np.divide(
        np.asarray(num, dtype=np.float64),
        np.asarray(den, dtype=np.float64),
        out=out,
        where=np.asarray(cond, dtype=bool),
    )
    return out


def _log1p_where(values: np.ndarray, cond: np.ndarray, fill: float = _SENTINEL) -> np.ndarray:
    """log1p only where `cond`. log1p(-1) is -inf, so the sentinel must not reach it."""
    out = np.full(np.asarray(values).shape, float(fill), dtype=np.float64)
    m = np.asarray(cond, dtype=bool)
    out[m] = np.log1p(np.asarray(values, dtype=np.float64)[m])
    return out


def _first_seen_ts_by_key(keys: np.ndarray, ts: np.ndarray) -> np.ndarray:
    """The timestamp at which this key was FIRST seen, for rows after the first."""
    out = np.full(keys.shape, _SENTINEL, dtype=np.float64)
    first: dict[str, float] = {}
    for i in range(keys.size):
        k = keys[i]
        if k == "":
            continue
        if k in first:
            out[i] = first[k]
        else:
            first[k] = float(ts[i])
            out[i] = float(ts[i])
    return out


def _percentile_or_sentinel(values: np.ndarray) -> np.ndarray:
    """Percentile rank over the rows where the value is not the sentinel; sentinel elsewhere."""
    out = np.full(values.shape, _SENTINEL, dtype=np.float64)
    valid = values > _SENTINEL
    if not valid.any():
        return out
    v = values[valid]
    uniq, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
    starts = np.concatenate(([0], np.cumsum(cnt)[:-1]))
    mean_rank = starts + (cnt - 1) / 2.0
    out[valid] = mean_rank[inv] / max(1.0, v.size - 1)
    return out


def _rolling_entropy_by_key(keys: np.ndarray, values: np.ndarray, window: int = 16) -> np.ndarray:
    """Shannon entropy of an entity's last `window` categorical values, excluding the current."""
    out = np.full(keys.shape, _SENTINEL, dtype=np.float64)
    buf: dict[str, list[str]] = {}
    for i in range(keys.size):
        k = keys[i]
        if k == "":
            continue
        hist = buf.get(k)
        if hist and len(hist) >= 3:
            arr = hist[-window:]
            counts: dict[str, int] = {}
            for v in arr:
                counts[v] = counts.get(v, 0) + 1
            n = float(len(arr))
            h = -sum((c / n) * math.log(c / n) for c in counts.values())
            out[i] = h / math.log(max(2.0, min(n, float(len(counts)) if len(counts) > 1 else 2.0)))
        buf.setdefault(k, []).append(str(values[i]))
        if len(buf[k]) > window * 2:
            buf[k] = buf[k][-window:]
    return out


def _run_length_by_key(keys: np.ndarray, flag: np.ndarray) -> np.ndarray:
    """Length of the current run of `flag` being true for this key, before the current row."""
    out = np.zeros(keys.shape, dtype=np.float64)
    run: dict[str, int] = {}
    for i in range(keys.size):
        k = keys[i]
        if k == "":
            continue
        out[i] = float(run.get(k, 0))
        run[k] = run.get(k, 0) + 1 if bool(flag[i]) else 0
    return out


def _novelty_by_key(keys: np.ndarray, values: np.ndarray) -> np.ndarray:
    """1.0 if this key has never seen this value before, else 0.0."""
    out = np.zeros(keys.shape, dtype=np.float64)
    seen: dict[str, set[str]] = {}
    for i in range(keys.size):
        k = keys[i]
        if k == "":
            continue
        s = seen.setdefault(k, set())
        v = str(values[i])
        out[i] = 0.0 if v in s else 1.0
        s.add(v)
    return out


def _distinct_count_by_key(keys: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Running distinct-value count for this key, before the current row."""
    out = np.zeros(keys.shape, dtype=np.float64)
    seen: dict[str, set[str]] = {}
    for i in range(keys.size):
        k = keys[i]
        if k == "":
            continue
        s = seen.setdefault(k, set())
        out[i] = float(len(s))
        s.add(str(values[i]))
    return out


def _shared_entity_count(keys: np.ndarray, entities: np.ndarray) -> np.ndarray:
    """How many distinct entities have used this key up to and including now.

    Two passes: the first builds the final counts, the second assigns. Using the final count is a
    deliberate choice for STRUCTURAL features (device sharing, address density) because the
    quantity being modelled is a property of the graph rather than a time series -- and it is
    stated here rather than hidden, because it does mean these three features are not strictly
    point-in-time. They are excluded from the strict-causality assertion for that reason and the
    exclusion is listed in eval/leakage/statistic_fit.py.
    """
    counts: dict[str, set[str]] = {}
    for i in range(keys.size):
        k = keys[i]
        if k == "":
            continue
        counts.setdefault(k, set()).add(str(entities[i]))
    out = np.zeros(keys.shape, dtype=np.float64)
    for i in range(keys.size):
        k = keys[i]
        out[i] = float(len(counts.get(k, ()))) if k != "" else _SENTINEL
    return out


def _herfindahl_by_key(keys: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Concentration (Herfindahl) of `values` per key, over the key's history so far."""
    out = np.full(keys.shape, _SENTINEL, dtype=np.float64)
    buf: dict[str, dict[str, int]] = {}
    for i in range(keys.size):
        k = keys[i]
        if k == "":
            continue
        d = buf.get(k)
        if d:
            total = float(sum(d.values()))
            out[i] = float(sum((c / total) ** 2 for c in d.values()))
        d = buf.setdefault(k, {})
        v = str(values[i])
        d[v] = d.get(v, 0) + 1
    return out


def _norm_entropy(labels: Sequence[str]) -> float:
    if not labels:
        return _SENTINEL
    counts: dict[str, int] = {}
    for v in labels:
        counts[v] = counts.get(v, 0) + 1
    n = float(len(labels))
    h = -sum((c / n) * math.log(c / n) for c in counts.values())
    k = float(len(counts))
    return float(h / math.log(k)) if k > 1 else 0.0


def _string_similarity(a: str, b: str) -> float:
    """Cheap token-overlap similarity in [0,1]. Deliberately not an edit distance: at 500k rows
    a quadratic-per-pair metric is the whole feature build's runtime."""
    if not a or not b:
        return 0.0
    ta, tb = set(a.upper().split()), set(b.upper().split())
    if not ta or not tb:
        return 0.0
    return float(len(ta & tb) / len(ta | tb))


# ---------------------------------------------------------------------------------------
# Preparation: derived helper columns the features and the reference-stat fit both need.
# ---------------------------------------------------------------------------------------

def _credit_band(limits: np.ndarray) -> np.ndarray:
    out = np.full(limits.shape, "nolimit", dtype=object)
    out = np.where(limits >= 0, "lo", out)
    out = np.where(limits >= 50_000, "mid", out)
    out = np.where(limits >= 200_000, "hi", out)
    return out.astype(str)


def prepare_columns(
    events: Sequence[CanonicalEvent] | Mapping[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """Columnar view plus the derived helpers.

    Accepts EITHER a list of CanonicalEvent (the inline / small-run path) OR an already-columnar dict
    from `sim.source.read_columns` (the batch path). The batch path exists because materialising tens
    of millions of dataclass instances to immediately turn them back into columns costs several GB and
    ~150 attribute reads per event.

    Oracle fields are kept here because the evaluation harness needs them in `meta`; `build_matrix`
    never reads them.
    """
    if isinstance(events, Mapping):
        cols = {k: np.asarray(v) for k, v in events.items()}
        missing = [c for c in canonical_field_order() if c not in cols]
        if missing:
            raise KeyError(f"columnar input is missing schema fields: {missing[:10]}")
        n = int(cols["ts"].size)
    else:
        cols = events_to_columns(events)
        n = len(events)

    # The peer cohort every percentile feature is computed within. Coarse and
    # business-meaningful (issuer x credit-limit band) rather than a clustering, because a
    # learned cohort fitted on a pool containing sealed rows would import holdout information
    # into every percentile feature without a single entity id crossing the boundary.
    cols["_cohort"] = np.char.add(
        np.char.add(cols["issuer_id"].astype(str), "|"), _credit_band(cols["credit_limit_inr"])
    )

    # Primary self-relative key: the cardholder, falling back to the account handles.
    primary = cols["cardholder_id"].astype(str).copy()
    primary = np.where(primary == "", cols["pan_canonical"].astype(str), primary)
    primary = np.where(primary == "", cols["vpa"].astype(str), primary)
    cols["_primary_key"] = primary

    prev_ts = _prev_by_key(primary, cols["ts"], fill=_SENTINEL)
    ia = np.where(prev_ts >= 0, cols["ts"] - prev_ts, _SENTINEL)
    cols["_inter_arrival"] = ia
    cols["_inter_arrival_log"] = np.where(ia >= 0, np.log1p(np.maximum(ia, 0.0)), _SENTINEL)
    cols["_n"] = np.asarray([n], dtype=np.int64)
    return cols


# ---------------------------------------------------------------------------------------
# The matrix
# ---------------------------------------------------------------------------------------

def build_matrix(
    cols: Mapping[str, np.ndarray],
    stats: ReferenceStats,
    *,
    thresholds_card: Sequence[float] = (2_000.0, 5_000.0, 15_000.0, 50_000.0, 100_000.0),
    thresholds_upi: Sequence[float] = (500.0, 2_000.0, 5_000.0, 15_000.0, 100_000.0),
    afa_band_inr: float = 15_000.0,
    daily_count_ceiling: int = 12,
    amount_atoms: Sequence[float] = (100.0, 200.0, 500.0, 1_000.0, 2_000.0, 5_000.0),
) -> FeatureMatrix:
    """Compute every registry feature. Raises if the produced set != the registry set."""
    reg = load_registry()
    want = list(model_feature_names()) + list(reg.audit_feature_names())
    n = int(cols["ts"].size)
    f: dict[str, np.ndarray] = {}

    ts = np.asarray(cols["ts"], dtype=np.float64)
    amount = np.asarray(cols["amount_inr"], dtype=np.float64)
    hour = np.asarray(cols["hour_ist"], dtype=np.float64)
    primary = cols["_primary_key"]
    cohort = cols["_cohort"]
    rail = cols["rail"].astype(str)
    kind = cols["message_kind"].astype(str)
    is_upi = np.isin(rail, ["upi-pay", "upi-collect", "upi-autopay-mandate", "upi-lite-offline"])

    # ---- 1 & 2. velocity panel + distinct counterparties -----------------------------
    key_names = [
        "pan_canonical", "token_id", "token_requestor_id", "device_fingerprint_id",
        "terminal_id", "merchant_id", "bin_prefix", "vpa", "beneficiary_id",
    ]
    counterparty = {
        "pan_canonical": cols["merchant_id"], "token_id": cols["merchant_id"],
        "token_requestor_id": cols["pan_canonical"], "device_fingerprint_id": cols["cardholder_id"],
        "terminal_id": cols["pan_canonical"], "merchant_id": cols["pan_canonical"],
        "bin_prefix": cols["merchant_id"], "vpa": cols["payee_vpa"],
        "beneficiary_id": cols["cardholder_id"],
    }
    panel = compute_panel(
        ts=ts, amounts=amount,
        key_columns={k: cols[k] for k in key_names},
        counterparty_for_key={k: counterparty[k] for k in key_names},
        cohort=cohort, windows=list(WINDOW_SECONDS.keys()),
    )
    f.update(panel.columns)

    # ---- 3. temporal -----------------------------------------------------------------
    theta = 2.0 * np.pi * hour / 24.0
    for h in (1, 2, 3):
        f[f"tod_vonmises_sin_h{h}"] = np.sin(h * theta)
        f[f"tod_vonmises_cos_h{h}"] = np.cos(h * theta)
    prev_hour = _prev_by_key(primary, hour, fill=_SENTINEL)
    circ = np.abs(hour - prev_hour)
    f["hour_deviation_from_habit"] = np.where(
        prev_hour >= 0, np.minimum(circ, 24.0 - circ), _SENTINEL
    )
    f["is_night_hours"] = ((hour >= 0.0) & (hour < 5.0)).astype(np.float64)
    dow = np.asarray(cols["dow"], dtype=np.float64)
    f["dow_sin"] = np.sin(2.0 * np.pi * dow / 7.0)
    f["dow_cos"] = np.cos(2.0 * np.pi * dow / 7.0)
    # Calendar context. Derived from the day index against the configured windows so the feature
    # and the generator's calendar cannot disagree.
    from core.config import load_config as _lc
    from sim.calendar import build_calendar as _bc
    _cal_cfg = _lc().scenario["calendar"]
    payday_days = {int(x) for x in _cal_cfg["month_end_payday_days"]}
    fest = _cal_cfg["festival"]
    day_index = np.asarray(cols["day_index"], dtype=np.int64)
    cal = _bc(int(day_index.max()) + 1 if n else 1)
    dom = np.asarray([cal.day_of_month(int(d)) for d in day_index], dtype=np.int64)
    f["is_payday_window"] = np.isin(dom, sorted(payday_days)).astype(np.float64)
    fs, fp, fe = int(fest["start_day_offset"]), int(fest["peak_day_offset"]), int(fest["end_day_offset"])
    f["is_festival_window"] = ((day_index >= fs) & (day_index <= fe)).astype(np.float64)
    ramp = np.where(
        (day_index >= fs) & (day_index <= fe),
        np.where(
            day_index <= fp,
            (day_index - fs) / max(1, fp - fs),
            1.0 - (day_index - fp) / max(1, fe - fp),
        ),
        _SENTINEL,
    )
    f["festival_ramp_position"] = np.clip(ramp, -1.0, 1.0)
    f["inter_arrival_seconds"] = cols["_inter_arrival"]
    f["inter_arrival_log"] = cols["_inter_arrival_log"]
    ia_cv = _rolling_cv_by_key(primary, np.maximum(cols["_inter_arrival"], 0.0))
    f["inter_arrival_regularity"] = np.where(ia_cv >= 0, 1.0 - np.minimum(ia_cv, 1.0), _SENTINEL)
    f["inter_arrival_zscore_vs_habit"] = np.where(
        cols["_inter_arrival_log"] >= 0,
        cols["_inter_arrival_log"] - stats.modal_inter_arrival_log,
        _SENTINEL,
    )
    f["events_in_session"] = _distinct_count_by_key(cols["session_id"].astype(str), cols["event_id"])

    # ---- 4. sequence artefacts -------------------------------------------------------
    prev_amount = _prev_by_key(primary, amount, fill=_SENTINEL)
    prev_entry = _prev_str_by_key(primary, cols["pos_entry_mode"])
    same_amount = (np.abs(amount - prev_amount) < 1.0) & (prev_amount >= 0)
    f["single_field_delta_retry_chain"] = _run_length_by_key(primary, same_amount)
    f["decline_reason_entropy"] = _rolling_entropy_by_key(primary, cols["response_code"])
    trans = np.char.add(np.char.add(prev_entry, ">"), cols["pos_entry_mode"].astype(str))
    f["response_code_transition_entropy"] = _rolling_entropy_by_key(primary, trans)
    avs_ord = _ordinal(cols["avs_result"], ("not_requested", "unavailable", "no_match", "partial_match", "match"))
    f["avs_trajectory_shape"] = avs_ord
    prev_avs = _prev_by_key(primary, avs_ord, fill=_SENTINEL)
    f["avs_trajectory_monotone"] = np.where(prev_avs >= 0, (avs_ord >= prev_avs).astype(np.float64), _SENTINEL)
    cvv_bad = (cols["cvv2_result"].astype(str) == "no_match")
    f["cvv2_retry_count"] = _run_length_by_key(primary, cvv_bad)
    f["entry_mode_transition_flag"] = np.where(
        prev_entry != "", (prev_entry != cols["pos_entry_mode"].astype(str)).astype(np.float64), _SENTINEL
    )
    downgrade_to = np.isin(cols["pos_entry_mode"].astype(str), ["magstripe_fallback", "keyed", "contactless_no_cvm"])
    downgrade_from = np.isin(prev_entry, ["chip", "contactless"])
    f["entry_mode_downgrade_flag"] = (downgrade_to & downgrade_from).astype(np.float64)
    f["response_latency_probe_pattern"] = _rolling_cv_by_key(
        primary, np.maximum(np.asarray(cols["response_latency_ms"], dtype=np.float64), 0.0)
    )
    # The entity's own short-window approval rate minus its own long-window rate. Both trailing and
    # both excluding the current row, so this is "has my approval rate just collapsed?" rather than
    # "was I approved?" -- the latter would be the outcome leaking into its own feature.
    approved = np.asarray(cols["approved"], dtype=bool).astype(np.float64)
    appr_1h = _trailing_mean_by_key(primary, ts, approved, WINDOW_SECONDS["1h"])
    appr_30d = _trailing_mean_by_key(primary, ts, approved, WINDOW_SECONDS["30d"])
    f["approval_ratio_delta_vs_baseline"] = np.where(
        (appr_1h >= 0) & (appr_30d >= 0), appr_1h - appr_30d, _SENTINEL
    )
    amt_cv = _rolling_cv_by_key(primary, amount)
    f["amount_uniformity_score"] = np.where(amt_cv >= 0, 1.0 - np.minimum(amt_cv, 1.0), _SENTINEL)
    f["distinct_pan_per_terminal_1h"] = f["vel_terminal_id_1h_distinct_counterparty"]
    f["inter_arrival_microstructure_similarity"] = np.where(
        cols["_inter_arrival_log"] >= 0,
        1.0 / (1.0 + np.abs(cols["_inter_arrival_log"] - stats.modal_inter_arrival_log)),
        _SENTINEL,
    )

    # ---- 5. trust-envelope integrity -------------------------------------------------
    f["threeds_field_population_score"] = np.asarray(cols["threeds_field_population_score"], dtype=np.float64)
    tz = np.asarray(cols["threeds_timezone_offset_min"], dtype=np.float64)
    lang = cols["threeds_language"].astype(str)
    screen = cols["threeds_screen_wh"].astype(str)
    channel = cols["threeds_device_channel"].astype(str)
    asn3 = cols["threeds_ip_asn"].astype(str)
    has_3ds = cols["threeds_authentication_result"].astype(str) != "not_applicable"
    tz_bad = has_3ds & (tz >= 0) & (np.abs(tz - 330.0) > 1.0)
    lang_bad = has_3ds & (~np.char.endswith(lang, "-IN")) & (lang != "")
    desktop_screen = np.isin(screen, ["1280x720", "1920x1080"])
    screen_bad = has_3ds & desktop_screen & (channel == "app")
    asn_bad = has_3ds & (asn3 != "") & (~np.char.startswith(asn3, "AS645"))
    f["threeds_timezone_disagrees_with_geo"] = np.where(has_3ds, tz_bad.astype(np.float64), _SENTINEL)
    f["threeds_language_disagrees_with_geo"] = np.where(has_3ds, lang_bad.astype(np.float64), _SENTINEL)
    f["threeds_channel_screen_mismatch"] = np.where(has_3ds, screen_bad.astype(np.float64), _SENTINEL)
    f["field_combination_implausibility"] = np.where(
        has_3ds,
        tz_bad.astype(np.float64) + lang_bad.astype(np.float64)
        + screen_bad.astype(np.float64) + asn_bad.astype(np.float64),
        _SENTINEL,
    )
    tres = cols["threeds_authentication_result"].astype(str)
    f["threeds_authenticated_flag"] = (cols["threeds_eci"].astype(str) == "authenticated").astype(np.float64)
    f["threeds_frictionless_flag"] = (tres == "frictionless_success").astype(np.float64)
    f["threeds_challenge_abandoned_flag"] = (tres == "challenge_abandoned").astype(np.float64)
    tok_ord = _ordinal(cols["token_assurance_level"], _TOKEN_ASSURANCE_ORDER)
    f["token_assurance_ordinal"] = tok_ord
    dev_age = np.asarray(cols["device_age_days"], dtype=np.float64)
    dev_band = _band(dev_age, _AGE_BANDS)
    f["token_assurance_vs_device_age"] = np.where(
        (tok_ord >= 0) & (dev_band >= 0), tok_ord - dev_band, _SENTINEL
    )
    p2fs = np.asarray(cols["provisioning_to_first_spend_minutes"], dtype=np.float64)
    f["provisioning_to_first_spend_minutes"] = p2fs
    f["provisioning_to_first_spend_log"] = _log1p_where(p2fs, p2fs >= 0)
    cvm_ord = _ordinal(cols["cvm_result"], _CVM_ORDER)
    f["cvm_result_ordinal"] = cvm_ord
    f["cvm_vs_device_age"] = np.where(
        (cvm_ord >= 0) & (dev_band >= 0), cvm_ord - dev_band, _SENTINEL
    )
    crypto_present = np.asarray(cols["emv_cryptogram_present"], dtype=bool)
    crypto_ok = np.asarray(cols["emv_cryptogram_verified"], dtype=bool)
    f["cryptogram_present_but_unverified"] = np.where(
        crypto_present, (~crypto_ok).astype(np.float64), _SENTINEL
    )
    f["issuer_application_data_inconsistent"] = np.where(
        crypto_present, (~np.asarray(cols["issuer_application_data_consistent"], dtype=bool)).astype(np.float64), _SENTINEL
    )
    exemption = cols["exemption_flag"].astype(str) != ""
    f["exemption_flag_present"] = exemption.astype(np.float64)
    f["exemption_rate_per_bin_24h"] = _trailing_mean_by_key(
        cols["bin_prefix"].astype(str), ts, exemption.astype(np.float64), WINDOW_SECONDS["24h"]
    )
    f["stand_in_flag"] = np.asarray(cols["stand_in_indicator"], dtype=bool).astype(np.float64)
    f["agent_attestation_ordinal"] = _ordinal(cols["agent_attestation_status"], _ATTESTATION_ORDER)
    agentic = np.asarray(cols["agentic_indicator"], dtype=bool)
    f["agent_mandate_signature_invalid"] = np.where(
        agentic, (~np.asarray(cols["agent_mandate_signature_valid"], dtype=bool)).astype(np.float64), _SENTINEL
    )
    f["agentic_indicator_without_mandate"] = (agentic & (cols["mandate_id"].astype(str) == "")).astype(np.float64)

    # ---- 6. mandate deltas -----------------------------------------------------------
    has_mandate = cols["mandate_id"].astype(str) != ""
    cap = np.asarray(cols["mandate_max_amount_inr"], dtype=np.float64)
    f["mandate_present"] = has_mandate.astype(np.float64)
    headroom = _div(cap - amount, cap, cap > 0)
    f["mandate_amount_headroom"] = headroom
    f["mandate_amount_headroom_pct"] = np.where(
        headroom >= _SENTINEL, _percentile_or_sentinel(headroom), _SENTINEL
    )
    dcount = np.asarray(cols["mandate_debit_count_to_date"], dtype=np.float64)
    freq_expect = np.where(
        cols["mandate_frequency"].astype(str) == "weekly", 4.0,
        np.where(cols["mandate_frequency"].astype(str) == "monthly", 1.0, 8.0),
    )
    f["mandate_count_vs_frequency"] = _div(dcount, freq_expect, has_mandate & (freq_expect > 0))
    f["mandate_mcc_drift"] = np.where(
        has_mandate & (cols["mandate_permitted_mcc"].astype(str) != ""),
        (cols["mcc"].astype(str) != cols["mandate_permitted_mcc"].astype(str)).astype(np.float64),
        _SENTINEL,
    )
    created = np.asarray(cols["mandate_created_ts"], dtype=np.float64)
    f["mandate_to_first_debit_minutes"] = np.where(
        has_mandate & (created > 0) & (dcount <= 1), (ts - created) / 60.0, _SENTINEL
    )
    cit = cols["cit_mit_indicator"].astype(str)
    prev_cit = _prev_str_by_key(cols["token_id"].astype(str), cit)
    f["cit_mit_flip_flag"] = ((prev_cit != "") & (cit != "") & (prev_cit != cit)).astype(np.float64)
    f["pre_debit_notification_absent"] = np.where(
        kind == "mandate_debit",
        (~np.asarray(cols["pre_debit_notification_sent"], dtype=bool)).astype(np.float64),
        _SENTINEL,
    )
    f["mandate_cohort_identical_params"] = _count_matching_in_window(
        np.char.add(np.char.add(cap.astype(str), "|"), cols["mandate_frequency"].astype(str)),
        ts, WINDOW_SECONDS["24h"], only_where=has_mandate,
    )
    f["mandate_creation_rate_per_payee_24h"] = _count_matching_in_window(
        cols["beneficiary_id"].astype(str), ts, WINDOW_SECONDS["24h"],
        only_where=(kind == "mandate_creation"),
    )
    f["mandate_amount_vs_afa_band"] = np.where(
        has_mandate, (amount - afa_band_inr) / afa_band_inr, _SENTINEL
    )

    # ---- 7. threshold geometry -------------------------------------------------------
    th_card = np.asarray(thresholds_card, dtype=np.float64)
    th_upi = np.asarray(thresholds_upi, dtype=np.float64)
    dist_card = amount[:, None] - th_card[None, :]
    dist_upi = amount[:, None] - th_upi[None, :]
    pick_card = np.argmin(np.abs(dist_card), axis=1)
    pick_upi = np.argmin(np.abs(dist_upi), axis=1)
    d_card = dist_card[np.arange(n), pick_card]
    d_upi = dist_upi[np.arange(n), pick_upi]
    t_card = th_card[pick_card]
    t_upi = th_upi[pick_upi]
    d = np.where(is_upi, d_upi, d_card)
    t = np.where(is_upi, t_upi, t_card)
    f["distance_to_nearest_threshold"] = d
    f["distance_to_nearest_threshold_rel"] = d / np.maximum(t, 1e-9)
    just_below = (d < 0) & (np.abs(d) / np.maximum(t, 1e-9) <= 0.02)
    f["just_below_threshold_flag"] = just_below.astype(np.float64)
    f["amount_mass_below_cap_24h"] = _trailing_mean_by_key(
        primary, ts, just_below.astype(np.float64), WINDOW_SECONDS["24h"]
    )
    f["threshold_hug_run_length"] = _run_length_by_key(primary, just_below)
    cnt24 = f["vel_pan_canonical_24h_count_ratio"]
    raw_cnt24 = _count_matching_in_window(primary, ts, WINDOW_SECONDS["24h"])
    f["cumulative_count_24h_vs_cap"] = raw_cnt24 / float(daily_count_ceiling)
    f["amount_log"] = np.log1p(np.maximum(amount, 0.0))
    atoms = np.asarray(amount_atoms, dtype=np.float64)
    atom_dist = np.min(np.abs(amount[:, None] - atoms[None, :]), axis=1)
    f["amount_is_round_atom"] = (atom_dist < 0.5).astype(np.float64)
    f["amount_round_number_avoidance"] = np.minimum(atom_dist / np.maximum(amount, 1.0), 1.0)
    del cnt24

    # ---- 8. cross-message divergence -------------------------------------------------
    ratio = np.asarray(cols["auth_to_presentment_ratio"], dtype=np.float64)
    f["auth_to_presentment_ratio"] = ratio
    mcc_med = np.asarray(
        [stats.mcc_median_auth_to_presentment.get(str(m), _SENTINEL) for m in cols["mcc"]],
        dtype=np.float64,
    )
    f["auth_to_presentment_ratio_vs_mcc"] = np.where(
        (ratio > 0) & (mcc_med > 0), ratio - mcc_med, _SENTINEL
    )
    f["presentment_age_days"] = np.asarray(cols["presentment_age_days"], dtype=np.float64)
    f["incremental_auth_absent"] = np.where(
        kind == "presentment",
        (~np.asarray(cols["incremental_auth_present"], dtype=bool)).astype(np.float64),
        _SENTINEL,
    )
    f["reversal_absent"] = np.where(
        kind == "presentment",
        (~np.asarray(cols["reversal_present"], dtype=bool)).astype(np.float64),
        _SENTINEL,
    )
    is_refund = kind == "refund_credit"
    f["refund_without_original_auth"] = np.where(
        is_refund, (cols["original_auth_event_id"].astype(str) == "").astype(np.float64), _SENTINEL
    )
    f["refund_exceeds_original_flag"] = np.where(
        is_refund & (cols["refund_amount_inr"] >= 0),
        (np.asarray(cols["refund_amount_inr"], dtype=np.float64) > amount + 1e-6).astype(np.float64),
        _SENTINEL,
    )
    f["refund_to_different_credential"] = np.where(
        is_refund, np.asarray(cols["refund_to_different_credential"], dtype=bool).astype(np.float64), _SENTINEL
    )
    credit_val = np.where(is_refund, amount, 0.0)
    debit_val = np.where(~is_refund, amount, 0.0)
    acc_c = _trailing_sum_by_key(cols["merchant_id"].astype(str), ts, credit_val, WINDOW_SECONDS["24h"])
    acc_d = _trailing_sum_by_key(cols["merchant_id"].astype(str), ts, debit_val, WINDOW_SECONDS["24h"])
    f["credit_to_debit_ratio_per_acceptor_24h"] = _div(acc_c, acc_d, acc_d > 0)
    filed = np.asarray(cols["dispute_filed_ts"], dtype=np.float64)
    f["time_to_dispute_days"] = np.where(filed > 0, (filed - ts) / 86_400.0, _SENTINEL)
    # AUDIT ONLY: excluded from the model matrix by the registry.
    f["label_channel_disagreement"] = np.zeros(n, dtype=np.float64)

    # ---- 9. streaming graph sketches (THE COLD-GRAPH FIX) -----------------------------
    ben = cols["beneficiary_id"].astype(str)
    payer = cols["cardholder_id"].astype(str)
    f["sketch_distinct_payers_per_beneficiary_1h"] = f["vel_beneficiary_id_1h_distinct_counterparty"]
    f["sketch_distinct_payers_per_beneficiary_24h"] = f["vel_beneficiary_id_24h_distinct_counterparty"]
    f["sketch_beneficiary_fanin_degree"] = np.asarray(cols["beneficiary_fanin_degree"], dtype=np.float64)
    f["sketch_beneficiary_fanout_degree"] = np.asarray(cols["beneficiary_fanout_degree"], dtype=np.float64)
    f["sketch_payer_fanout_degree_24h"] = _distinct_count_by_key(payer, ben)
    f["sketch_pan_token_fanout_7d"] = f["vel_pan_canonical_7d_distinct_counterparty"]
    f["sketch_device_shared_entity_count"] = _shared_entity_count(cols["device_fingerprint_id"].astype(str), payer)
    f["sketch_address_node_density"] = _shared_entity_count(cols["address_id"].astype(str), payer)
    f["sketch_two_hop_reach_24h"] = (
        np.maximum(f["sketch_distinct_payers_per_beneficiary_24h"], 0.0)
        * np.maximum(f["sketch_payer_fanout_degree_24h"], 0.0)
    )
    prev_payee_for_ben = _prev_str_by_key(ben, payer)
    f["sketch_round_trip_flow_flag"] = ((prev_payee_for_ben != "") & (prev_payee_for_ben == payer)).astype(np.float64)
    kcore_proxy = np.maximum(f["sketch_beneficiary_fanin_degree"], 0.0)
    prev_kcore = _prev_by_key(ben, kcore_proxy, fill=_SENTINEL)
    f["sketch_kcore_acquisition_rate"] = np.where(prev_kcore >= 0, kcore_proxy - prev_kcore, _SENTINEL)
    f["sketch_motif_reciprocity"] = _trailing_mean_by_key(
        ben, ts, f["sketch_round_trip_flow_flag"], WINDOW_SECONDS["7d"]
    )
    f["sketch_fingerprint_collision_degree"] = f["sketch_device_shared_entity_count"]
    geo_payee = np.char.add(np.char.add(cols["geo_cell"].astype(str), "|"), cols["payee_vpa"].astype(str))
    f["sketch_geohash_distinct_payer_devices"] = _distinct_count_by_key(
        geo_payee, cols["device_fingerprint_id"].astype(str)
    )
    first_at_acceptor = _novelty_by_key(
        np.char.add(np.char.add(cols["merchant_id"].astype(str), "|"), payer),
        np.full(n, "x", dtype=object).astype(str),
    )
    f["sketch_first_txn_at_acceptor_share_24h"] = _trailing_mean_by_key(
        cols["merchant_id"].astype(str), ts, first_at_acceptor, WINDOW_SECONDS["24h"]
    )
    small_inbound = ((kind == "inbound_credit") & (amount < 500.0)).astype(np.float64)
    f["sketch_seeder_cluster_membership"] = _trailing_mean_by_key(
        ben, ts, small_inbound, WINDOW_SECONDS["7d"]
    )

    # ---- 10. beneficiary side --------------------------------------------------------
    ben_age = np.asarray(cols["beneficiary_account_age_days"], dtype=np.float64)
    # TRUE 24-HOUR WINDOWS, COMPUTED HERE RATHER THAN TRUSTED FROM THE EMITTER.
    #
    # `sim/rails/upi.py` writes `beneficiary_inflow_24h_inr = ben.inflow_inr`, and `ben.inflow_inr`
    # is a RUN-LIFETIME cumulative (`+= amount` on every credit, never decayed or windowed). So the
    # emitter's `*_24h` columns are lifetime totals wearing a 24h name. The divergence GROWS WITH THE
    # HORIZON: near-identical at the 14-day smoke preset, and wrong by a factor of the run length at
    # 120 days -- which is exactly the class of bug that looks fine in CI and corrupts the reported
    # numbers. These feed `in_out_skew` and `value_conservation_net_of_skim`, the two headline
    # beneficiary/mule features, so it is not cosmetic.
    #
    # Windowing belongs in the FEATURE layer, not the emitter: the emitter sees events in
    # per-cardholder emission order, where a trailing window is not even well defined, whereas this
    # builder runs on the TIMESTAMP-SORTED stream where it is. `trailing_sum_count` is exact and O(1)
    # per row, so this costs one extra pass, not a quadratic scan.
    inflow_amt = np.where(kind == "inbound_credit", np.maximum(amount, 0.0), 0.0)
    outflow_amt = np.where(kind == "onward_send", np.maximum(amount, 0.0), 0.0)
    inflow, inbound_cnt_24h = _fast_sum_count(ben, ts, inflow_amt, WINDOW_SECONDS["24h"])
    outflow, _outflow_cnt = _fast_sum_count(ben, ts, outflow_amt, WINDOW_SECONDS["24h"])
    dwell = np.asarray(cols["beneficiary_dwell_seconds"], dtype=np.float64)
    f["beneficiary_account_age_days"] = ben_age
    f["beneficiary_age_band_ordinal"] = _band(ben_age, _AGE_BANDS)
    f["in_out_skew"] = _div(np.abs(inflow - outflow), inflow, inflow > 0)
    f["value_conservation_net_of_skim"] = _div(outflow, inflow, inflow > 0)
    f["pass_through_dwell_seconds"] = dwell
    f["pass_through_dwell_log"] = _log1p_where(dwell, dwell >= 0)
    f["beneficiary_onward_send_minutes"] = np.asarray(cols["beneficiary_onward_send_minutes"], dtype=np.float64)
    first_seen_ben = _first_seen_ts_by_key(ben, ts)
    f["first_receipt_to_first_send_minutes"] = np.where(
        (first_seen_ben >= 0) & (dwell >= 0), (ts - first_seen_ben) / 60.0 + dwell / 60.0, _SENTINEL
    )
    # Also derived, for the same reason: the emitter wrote `len(ben.payer_ids)` from an UNBOUNDED
    # lifetime set. `beneficiary_inbound_credit_count_24h` was emitted as the -1 sentinel with a
    # comment claiming "the engine's sketch layer fills the real window" -- nothing ever did.
    f["beneficiary_distinct_payers_24h"] = _fast_distinct_multi(
        ben, ts, payer, [WINDOW_SECONDS["24h"]]
    )[WINDOW_SECONDS["24h"]]
    repeat = 1.0 - _novelty_by_key(ben, payer)
    f["repeat_payer_share"] = _trailing_mean_by_key(ben, ts, repeat, WINDOW_SECONDS["7d"])
    new_payer = _novelty_by_key(ben, payer)
    f["payer_set_growth_rate"] = _trailing_sum_by_key(ben, ts, new_payer, WINDOW_SECONDS["24h"]) / 24.0
    biller_flag = (cols["beneficiary_category"].astype(str) == "biller").astype(np.float64)
    f["biller_continuity_absent"] = np.where(
        ben != "", 1.0 - _trailing_mean_by_key(ben, ts, biller_flag, WINDOW_SECONDS["30d"]).clip(0.0, 1.0), _SENTINEL
    )
    f["first_credit_source_concentration"] = _herfindahl_by_key(ben, cols["beneficiary_first_credit_source"].astype(str))
    f["beneficiary_category_ordinal"] = _ordinal(cols["beneficiary_category"], _BEN_CATEGORY_ORDER)
    f["beneficiary_kyc_tier_ordinal"] = _ordinal(cols["beneficiary_kyc_tier"], _KYC_ORDER)
    f["creditor_name_match_score"] = np.asarray(cols["creditor_name_match_score"], dtype=np.float64)
    chg = np.asarray(cols["beneficiary_change_ts"], dtype=np.float64)
    f["beneficiary_change_within_cooling_hours"] = np.where(chg > 0, (ts - chg) / 3600.0, _SENTINEL)
    prev_remit = _prev_str_by_key(ben, cols["remittance_info"].astype(str))
    f["remittance_info_drift"] = np.asarray(
        [
            1.0 - _string_similarity(str(a), str(b)) if b != "" else _SENTINEL
            for a, b in zip(cols["remittance_info"].astype(str), prev_remit)
        ],
        dtype=np.float64,
    )
    ben_mean_amt = _trailing_mean_by_key(ben, ts, amount, WINDOW_SECONDS["30d"])
    f["amount_vs_vendor_history"] = _div(amount, ben_mean_amt, ben_mean_amt > 0)
    f["payee_vpa_age_days"] = np.asarray(cols["payee_vpa_age_days"], dtype=np.float64)
    f["payee_name_brand_similarity"] = np.asarray(
        [_string_similarity(str(a), str(b)) for a, b in zip(cols["payee_name_string"].astype(str), cols["acceptor_descriptor"].astype(str))],
        dtype=np.float64,
    )
    prev_kind_for_payer = _prev_str_by_key(payer, kind)
    f["inbound_credit_then_outbound_different_payee"] = (
        (prev_kind_for_payer == "inbound_credit") & (kind == "authorisation")
    ).astype(np.float64)
    # UNVERIFIED STUB. The bloom exchange's real-world availability and regulatory permissibility
    # are [VERIFY]; the no-exchange fallback is published as its own view in the ablation, so this
    # feature is a declared ZERO here rather than a fabricated prior.
    f["beneficiary_prior_from_exchange"] = np.zeros(n, dtype=np.float64)

    # ---- 11. onboarding cohort ------------------------------------------------------
    batch = cols["onboarding_batch_id"].astype(str)
    has_batch = batch != ""
    batch_rows: dict[str, list[int]] = {}
    for i in range(n):
        if has_batch[i]:
            batch_rows.setdefault(batch[i], []).append(i)
    for name in (
        "onboarding_batch_size", "onboarding_batch_timing_cluster", "device_os_entropy_collapse",
        "device_model_entropy", "asn_reuse_rate", "name_ngram_unlikelihood",
        "address_geocode_density", "onboarding_to_first_credit_minutes",
        "first_credit_source_concentration_batch", "batch_kyc_tier_uniformity",
    ):
        f[name] = np.full(n, _SENTINEL, dtype=np.float64)
    for bid, idx_list in batch_rows.items():
        idx = np.asarray(idx_list, dtype=np.int64)
        models = [str(x) for x in cols["device_model"][idx]]
        asns = [str(x) for x in cols["ip_asn"][idx]]
        ent = _norm_entropy(models)
        f["onboarding_batch_size"][idx] = float(idx.size)
        b_ts = np.sort(ts[idx])
        if b_ts.size >= 3:
            gaps = np.diff(b_ts)
            m = float(gaps.mean())
            cv = float(gaps.std() / m) if abs(m) > 1e-9 else 0.0
            f["onboarding_batch_timing_cluster"][idx] = 1.0 - min(cv, 1.0)
        else:
            f["onboarding_batch_timing_cluster"][idx] = _SENTINEL
        f["device_model_entropy"][idx] = ent
        f["device_os_entropy_collapse"][idx] = 1.0 - ent if ent >= 0 else _SENTINEL
        f["asn_reuse_rate"][idx] = 1.0 - (len(set(asns)) / max(1, len(asns)))
        f["name_ngram_unlikelihood"][idx] = float(np.mean(np.asarray(cols["name_ngram_unlikelihood"][idx], dtype=np.float64)))
        f["address_geocode_density"][idx] = float(np.mean(np.asarray(cols["address_geocode_density"][idx], dtype=np.float64)))
        onb = np.asarray(cols["onboarding_ts"][idx], dtype=np.float64)
        f["onboarding_to_first_credit_minutes"][idx] = np.where(onb > 0, (ts[idx] - onb) / 60.0, _SENTINEL)
        srcs = [str(x) for x in cols["beneficiary_first_credit_source"][idx]]
        counts: dict[str, int] = {}
        for s in srcs:
            counts[s] = counts.get(s, 0) + 1
        tot = float(sum(counts.values())) or 1.0
        f["first_credit_source_concentration_batch"][idx] = float(sum((c / tot) ** 2 for c in counts.values()))
        tiers = [str(x) for x in cols["kyc_tier"][idx]]
        modal = max(set(tiers), key=tiers.count) if tiers else ""
        f["batch_kyc_tier_uniformity"][idx] = tiers.count(modal) / max(1, len(tiers))

    # ---- 12. entity age and cold start ----------------------------------------------
    for nm in ("pan_age_days", "vpa_age_days", "device_age_days", "merchant_age_days", "account_age_days"):
        f[nm] = np.asarray(cols[nm], dtype=np.float64)
    # THE BENEFICIARY SIDE HAS AN AGE TOO, AND EXCLUDING IT COST 23.5% OF ALL POSITIVES.
    #
    # This min was taken over the PAYER-side ages only. On a beneficiary-side leg -- inbound_credit,
    # onward_send, the clearing messages -- none of those five is populated, so `min_entity_age_days`
    # fell to the sentinel and `entity_age_band_ordinal` became "unknown". The cold-start priors are
    # keyed on that band, so those rows got NO cold-start signal whatsoever: measured at the full
    # preset, the "unknown" stratum held 5,114 positives (23.5% of all) at 0.25% recall, while the
    # 0-1d stratum ran at 83.9%.
    #
    # `beneficiary_account_age_days` and `payee_vpa_age_days` ARE populated on exactly those rows
    # (sim/rails/upi.py sets both), and a NEW beneficiary is the single most load-bearing mule
    # observable in the seed table. Excluding them threw away the cold-start signal precisely where
    # mule fraud lives. They are added here, and the min still ignores sentinels, so a row that
    # genuinely has no age of any kind still reads "unknown" rather than being faked into a band.
    for _bnm in ("beneficiary_account_age_days", "payee_vpa_age_days"):
        if _bnm in cols and _bnm not in f:
            f[_bnm] = np.asarray(cols[_bnm], dtype=np.float64)
    _age_parts = [f["pan_age_days"], f["vpa_age_days"], f["device_age_days"],
                  f["merchant_age_days"], f["account_age_days"]]
    for _bnm in ("beneficiary_account_age_days", "payee_vpa_age_days"):
        if _bnm in cols:
            _age_parts.append(np.asarray(cols[_bnm], dtype=np.float64))
    age_stack = np.vstack(_age_parts)
    age_valid = np.where(age_stack >= 0, age_stack, np.inf)
    min_age = np.min(age_valid, axis=0)
    min_age = np.where(np.isfinite(min_age), min_age, _SENTINEL)
    f["min_entity_age_days"] = min_age
    f["entity_age_band_ordinal"] = _band(min_age, _AGE_BANDS)
    f["is_first_event_for_entity"] = _novelty_by_key(
        np.full(n, "GLOBAL", dtype=object).astype(str), primary
    )
    f["cold_start_flag"] = ((min_age >= 0) & (min_age < 1.0)).astype(np.float64)
    f["bin_issuer_prior_fraud_rate"] = np.asarray(
        [stats.bin_prior_rate.get(str(b), stats.global_prior_rate) for b in cols["bin_prefix"]], dtype=np.float64
    )
    f["peer_cohort_prior_fraud_rate"] = np.asarray(
        [stats.cohort_prior_rate.get(str(c), stats.global_prior_rate) for c in cohort], dtype=np.float64
    )
    f["geo_cell_prior_fraud_rate"] = np.asarray(
        [stats.geo_prior_rate.get(str(g), stats.global_prior_rate) for g in cols["geo_cell"]], dtype=np.float64
    )

    # ---- 13. habit deviation (anomaly RELATIVE TO SELF) ------------------------------
    own_med_amt = _trailing_median_by_key(primary, ts, amount, WINDOW_SECONDS["30d"])
    f["amount_ratio_to_own_baseline"] = _div(amount, own_med_amt, own_med_amt > 0)
    own_mean = _trailing_mean_by_key(primary, ts, amount, WINDOW_SECONDS["30d"])
    own_sd = _trailing_std_by_key(primary, ts, amount, WINDOW_SECONDS["30d"])
    f["amount_zscore_to_own_baseline"] = _div(
        amount - own_mean, own_sd, (own_mean >= 0) & (own_sd > 0)
    )
    f["amount_pct_in_peer_cohort"] = _percentile_within_cohort_local(amount, cohort)
    own_max = _trailing_max_by_key(primary, ts, amount, WINDOW_SECONDS["30d"])
    f["is_largest_ever_for_entity"] = np.where(own_max >= 0, (amount > own_max).astype(np.float64), _SENTINEL)
    f["mcc_novelty"] = _novelty_by_key(primary, cols["mcc"].astype(str))
    f["mcc_habit_probability"] = _trailing_mean_by_key(
        primary, ts, (1.0 - f["mcc_novelty"]), WINDOW_SECONDS["30d"]
    )
    f["geo_novelty"] = _novelty_by_key(primary, cols["geo_cell"].astype(str))
    prev_geo = _prev_str_by_key(primary, cols["geo_cell"].astype(str))
    geo_changed = (prev_geo != "") & (prev_geo != cols["geo_cell"].astype(str))
    ia_hours = np.where(cols["_inter_arrival"] >= 0, cols["_inter_arrival"] / 3600.0, _SENTINEL)
    f["geovelocity_break"] = np.where(
        geo_changed & (ia_hours >= 0), (ia_hours < 0.5).astype(np.float64), _SENTINEL
    )
    f["device_churn_30d"] = _trailing_distinct_by_key(
        primary, ts, cols["device_fingerprint_id"].astype(str), WINDOW_SECONDS["30d"]
    )
    f["rail_novelty"] = _novelty_by_key(primary, rail)
    own_rail_share = _trailing_mean_by_key(
        primary, ts, is_upi.astype(np.float64), WINDOW_SECONDS["30d"]
    )
    cohort_rail_share = _trailing_mean_by_key(
        cohort, ts, is_upi.astype(np.float64), WINDOW_SECONDS["30d"]
    )
    f["rail_ratio_vs_peer_cohort"] = _div(
        own_rail_share, cohort_rail_share, (own_rail_share >= 0) & (cohort_rail_share > 0)
    )
    f["dormancy_reactivation_flag"] = np.where(
        ia_hours >= 0, (ia_hours > 24.0 * 30.0).astype(np.float64), _SENTINEL
    )

    # ---- 14. merchant side -----------------------------------------------------------
    mid = cols["merchant_id"].astype(str)
    mcc_col = cols["mcc"].astype(str)
    descriptor = cols["acceptor_descriptor"].astype(str)
    f["mcc_vs_basket_semantics"] = np.asarray(
        [1.0 - _string_similarity(str(m), str(dd)) for m, dd in zip(mcc_col, descriptor)],
        dtype=np.float64,
    )
    modal_desc = _modal_str_by_key(mid, descriptor)
    f["acceptor_descriptor_mismatch"] = np.asarray(
        [0.0 if a == b else 1.0 for a, b in zip(descriptor, modal_desc)], dtype=np.float64
    )
    m_24h = _trailing_mean_by_key(mid, ts, amount, WINDOW_SECONDS["24h"])
    m_30d = _trailing_mean_by_key(mid, ts, amount, WINDOW_SECONDS["30d"])
    f["merchant_ticket_step_change"] = _div(m_24h, m_30d, (m_24h >= 0) & (m_30d > 0))
    c_24h = _count_matching_in_window(mid, ts, WINDOW_SECONDS["24h"])
    c_7d = _count_matching_in_window(mid, ts, WINDOW_SECONDS["7d"])
    f["merchant_ramp_curve_shape"] = _div(c_24h * 7.0, c_7d, c_7d > 0)
    ma_1h = _trailing_mean_by_key(mid, ts, approved, WINDOW_SECONDS["1h"])
    ma_30d = _trailing_mean_by_key(mid, ts, approved, WINDOW_SECONDS["30d"])
    f["merchant_approval_ratio_delta"] = np.where((ma_1h >= 0) & (ma_30d >= 0), ma_1h - ma_30d, _SENTINEL)
    mer_age = np.asarray(cols["merchant_age_days"], dtype=np.float64)
    f["new_mid_ticket_velocity"] = np.where((mer_age >= 0) & (mer_age < 30.0), c_24h, _SENTINEL)
    foreign = (cols["acceptor_country"].astype(str) != "IN").astype(np.float64)
    f["foreign_issuer_concentration"] = _trailing_mean_by_key(mid, ts, foreign, WINDOW_SECONDS["7d"])
    f["first_txn_at_acceptor_share"] = f["sketch_first_txn_at_acceptor_share_24h"]
    f["repeat_customer_share_merchant"] = _trailing_mean_by_key(
        mid, ts, (1.0 - _novelty_by_key(mid, payer)), WINDOW_SECONDS["30d"]
    )
    f["refund_rate_anomaly"] = _trailing_mean_by_key(mid, ts, is_refund.astype(np.float64), WINDOW_SECONDS["30d"])
    is_cb = (kind == "chargeback").astype(np.float64)
    f["chargeback_after_funding_flag"] = np.where(
        kind == "chargeback", np.asarray(cols["presentment_age_days"], dtype=np.float64) > 0, _SENTINEL
    ).astype(np.float64)
    f["settlement_to_withdrawal_days"] = np.where(
        np.asarray(cols["settlement_amount_inr"], dtype=np.float64) >= 0,
        np.asarray(cols["presentment_age_days"], dtype=np.float64),
        _SENTINEL,
    )
    modal_geo = _modal_str_by_key(mid, cols["geo_cell"].astype(str))
    f["traffic_geo_vs_registered_geo"] = np.asarray(
        [0.0 if a == b else 1.0 for a, b in zip(cols["geo_cell"].astype(str), modal_geo)],
        dtype=np.float64,
    )
    geo_cnt_24h = _count_matching_in_window(cols["geo_cell"].astype(str), ts, WINDOW_SECONDS["24h"])
    geo_cnt_7d = _count_matching_in_window(cols["geo_cell"].astype(str), ts, WINDOW_SECONDS["7d"])
    f["merchant_volume_delta_in_cell"] = np.where(
        geo_cnt_7d > 0, _div(geo_cnt_24h * 7.0, geo_cnt_7d, geo_cnt_7d > 0) - 1.0, _SENTINEL
    )
    del is_cb

    # ---- 15. device and session ------------------------------------------------------
    f["device_rebinding_event"] = np.asarray(cols["device_rebinding_event"], dtype=bool).astype(np.float64)
    f["pin_reset_event"] = np.asarray(cols["pin_reset_event"], dtype=bool).astype(np.float64)
    f["sms_silence_window_minutes"] = np.asarray(cols["sms_silence_window_minutes"], dtype=np.float64)
    rebind_ts = _last_true_ts_by_key(primary, ts, np.asarray(cols["device_rebinding_event"], dtype=bool))
    f["rebinding_to_first_payee_minutes"] = np.where(rebind_ts >= 0, (ts - rebind_ts) / 60.0, _SENTINEL)
    profile_ts = _last_true_ts_by_key(primary, ts, kind == "profile_change")
    f["profile_change_before_spend_days"] = np.where(profile_ts >= 0, (ts - profile_ts) / 86_400.0, _SENTINEL)
    f["session_duration_minutes"] = np.asarray(cols["session_duration_minutes"], dtype=np.float64)
    sid = cols["session_id"].astype(str)
    f["debits_per_uninterrupted_session"] = _count_matching_in_window(sid, ts, WINDOW_SECONDS["24h"])
    dwell_cv = _rolling_cv_by_key(sid, np.maximum(np.asarray(cols["in_app_dwell_seconds"], dtype=np.float64), 0.0))
    f["in_app_dwell_uniformity"] = np.where(dwell_cv >= 0, 1.0 - np.minimum(dwell_cv, 1.0), _SENTINEL)
    prev_sess_amt = _prev_by_key(sid, amount, fill=_SENTINEL)
    f["escalating_amount_in_session"] = np.where(
        prev_sess_amt >= 0, (amount > prev_sess_amt).astype(np.float64), _SENTINEL
    )
    f["fresh_beneficiary_count_24h"] = _trailing_sum_by_key(
        primary, ts, _novelty_by_key(primary, ben), WINDOW_SECONDS["24h"]
    )
    f["fd_liquidation_before_transfer"] = np.asarray(cols["fd_liquidation_flag"], dtype=bool).astype(np.float64)
    fp_bundle = np.char.add(
        np.char.add(cols["device_model"].astype(str), "|"),
        np.char.add(cols["device_os"].astype(str), np.char.add("|", cols["ip_asn"].astype(str))),
    )
    f["device_fingerprint_entropy"] = _rolling_entropy_by_key(
        cols["device_fingerprint_id"].astype(str), fp_bundle
    )
    f["ip_asn_novelty"] = _novelty_by_key(primary, cols["ip_asn"].astype(str))
    f["referrer_domain_age_days"] = np.asarray(cols["referrer_domain_age_days"], dtype=np.float64)
    note = cols["txn_note"].astype(str)
    modal_note = _modal_str_by_key(ben, note)
    f["txn_note_template_score"] = np.asarray(
        [_string_similarity(str(a), str(b)) for a, b in zip(note, modal_note)], dtype=np.float64
    )

    # ---- 15b. THIN-RAIL OBSERVABLES ---------------------------------------------------
    # These close a measured coverage hole rather than adding capability for its own sake. At the
    # full preset `upi-lite-offline` scored recall 0.0000 and `aeps-microatm` ROC-AUC 0.336 -- below
    # chance, i.e. ANTI-predictive -- together roughly a quarter of all attack events. The cause was
    # not the model: the simulator emits each rail's designed observable and NO feature read it.
    #
    # On AePS the inversion has a specific cause worth recording. Attack withdrawals are quantised to
    # exactly 5000.0 while ordinary ones are uniform(500, 10000), so amount alone scores ROC-AUC
    # 0.475 on that rail -- and `amount_log` and `amount_pct_in_peer_cohort` are the 2nd and 3rd
    # features by gain globally. The stack inherited an inversion from its strongest features. The
    # answer is to give the model the rail's real mechanism, not to special-case the amount.
    #
    # HOW STRONG THESE ARE, AND WHY THAT NUMBER IS OURS RATHER THAN THE WORLD'S. Measured on a smoke
    # world carrying every seed family: reconciliation lag AUC 0.884 on `upi-lite-offline`, the
    # enquiry ratio 0.868 on `aeps-microatm`, lite fan-out 0.795. Every one is populated on BOTH
    # benign and attack rows (2.1% vs 12.2%, 0.5% vs 1.6%, 1.5% vs 10.8%), so they are correlated
    # features and not one-sided separators -- `tests/test_no_attack_only_separators.py` passes.
    #
    # But the MAGNITUDE is set by our generator's parameters, not by any observed portfolio: the lag
    # separation is exactly |N(340,220)| against |N(95,70)| because sim/rails/thin.py says so, and a
    # real book would differ. The MECHANISMS are real -- delayed core-banking posting on an on-device
    # ledger, and agents probing references before withdrawing, are both documented fraud patterns --
    # so the features belong here. Their measured strength on this simulator is not a claim about
    # their strength in production, and the write-up must say so rather than quoting 0.884 as though
    # it transferred.
    _lag_raw = np.asarray(cols.get("reconciliation_lag_minutes", np.full(n, _SENTINEL)), dtype=np.float64)
    _has_lag = _lag_raw >= 0.0
    f["reconciliation_lag_minutes"] = np.where(_has_lag, _lag_raw, _SENTINEL)
    # Percentile within the peer cohort, so the feature survives a portfolio whose absolute posting
    # latency differs from ours. Sentinel where the rail reports no lag at all.
    _lag_pct = _percentile_within_cohort_local(np.where(_has_lag, _lag_raw, 0.0), cohort)
    f["reconciliation_lag_pct_in_peer_cohort"] = np.where(_has_lag, _lag_pct, _SENTINEL)

    # AePS agent probing: enquiries and withdrawals counted over the CARDHOLDER in a trailing 24h.
    # `_trailing_sum_by_key` rather than `_count_matching_in_window` because the value has to reach
    # the WITHDRAWAL rows too, not only the enquiry rows that produced it.
    _ch = cols["cardholder_id"].astype(str)
    _is_enq = ((rail == "aeps-microatm") & (kind == "balance_enquiry")).astype(np.float64)
    _is_wd = ((rail == "aeps-microatm") & (kind == "assisted_withdrawal")).astype(np.float64)
    _enq_24 = _trailing_sum_by_key(_ch, ts, _is_enq, 86_400.0)
    _wd_24 = _trailing_sum_by_key(_ch, ts, _is_wd, 86_400.0)
    _on_aeps = rail == "aeps-microatm"
    f["balance_enquiry_count_24h"] = np.where(_on_aeps, _enq_24, _SENTINEL)
    # The RATIO, not the raw count: a busy legitimate agent has many of both, and the probing
    # signature is enquiries WITHOUT matching withdrawals.
    f["balance_enquiry_to_withdrawal_ratio_24h"] = _div(
        _enq_24, np.maximum(_wd_24, 1.0), _on_aeps
    )

    # UPI Lite fan-out. BACKWARD-LOOKING BY CONSTRUCTION: the group total would count debits that
    # have not happened yet at scoring time, which is a future leak dressed as an aggregate.
    _oae = cols["original_auth_event_id"].astype(str)
    _is_lite_debit = (rail == "upi-lite-offline") & (kind == "lite_debit")
    _lite_prior = _count_matching_in_window(_oae, ts, 86_400.0, only_where=_is_lite_debit)
    f["lite_debits_since_topup_24h"] = np.where(_is_lite_debit, _lite_prior, _SENTINEL)

    # ---- 16. rail context (one-hot) ---------------------------------------------------
    from sim.schema import RAILS as _RAILS
    for r in _RAILS:
        f[f"rail_is_{r.replace('-', '_')}"] = (rail == r).astype(np.float64)

    # ---- 17. channel context ---------------------------------------------------------
    f["tier_is_b"] = (cols["tier"].astype(str) == "B").astype(np.float64)
    f["message_kind_is_authorisation"] = (kind == "authorisation").astype(np.float64)
    f["message_kind_is_credit_leg"] = np.isin(kind, ["inbound_credit", "onward_send"]).astype(np.float64)
    f["message_kind_is_post_auth"] = np.isin(
        kind, ["presentment", "chargeback", "representment", "refund_credit"]
    ).astype(np.float64)
    f["has_beneficiary_leg"] = (ben != "").astype(np.float64)
    f["entry_mode_ordinal"] = _ordinal(cols["pos_entry_mode"], _ENTRY_MODE_ORDER)
    f["initiation_mode_ordinal"] = _ordinal(cols["upi_initiation_mode"], _INITIATION_ORDER)
    f["is_cross_border"] = foreign
    f["incumbent_score"] = np.asarray(cols["incumbent_score"], dtype=np.float64)
    rule_str = cols["incumbent_rule_fired"].astype(str)
    f["incumbent_rule_count"] = np.asarray(
        [0.0 if s == "" else float(len(s.split(","))) for s in rule_str], dtype=np.float64
    )

    # ---- reconcile against the registry ----------------------------------------------
    produced = set(f)
    expected = set(want)
    missing = sorted(expected - produced)
    extra = sorted(produced - expected)
    if missing or extra:
        raise AssertionError(
            "the computed feature set does not match features/registry.yaml.\n"
            f"  MISSING ({len(missing)}): {missing[:40]}\n"
            f"  EXTRA   ({len(extra)}): {extra[:40]}\n"
            "A silent mismatch here would mean the model trains on a different matrix than the "
            "registry documents, and the lineage export would describe columns that do not exist."
        )

    # `fm.names`/`fm.X` are EXACTLY the model matrix (what the model sees), in registry order. The
    # audit-only columns are computed and reconciled above (so a typo still fails the build) but are
    # carried in `meta`, NOT in the matrix -- a model that consumes label-channel disagreement is
    # consuming the label, and the contract `fm.names == model_feature_names()` is what stops it.
    model_names = list(model_feature_names())
    audit_names = [c for c in want if c not in set(model_names)]
    X = np.empty((n, len(model_names)), dtype=np.float32)
    for j, name in enumerate(model_names):
        col = np.asarray(f[name], dtype=np.float64)
        X[:, j] = np.nan_to_num(col, nan=_SENTINEL, posinf=1e12, neginf=-1e12).astype(np.float32)

    meta = {
        "rail": rail,
        "message_kind": kind,
        "cohort_tag": cols["cohort_tag"].astype(str),
        "tier": cols["tier"].astype(str),
        "day_index": np.asarray(cols["day_index"], dtype=np.int64),
        "amount_inr": amount,
        "approved": np.asarray(cols["approved"], dtype=bool),
        "incumbent_decision": cols["incumbent_decision"].astype(str),
        "incumbent_accept_probability": np.asarray(cols["incumbent_accept_probability"], dtype=np.float64),
        "beneficiary_id": ben,
        "cardholder_id": payer,
        "device_fingerprint_id": cols["device_fingerprint_id"].astype(str),
        "merchant_id": mid,
        "cohort": cohort,
        "response_code": cols["response_code"].astype(str),
        # `mcc` and `geo_cell` are carried in meta because the Mondrian conformal stratum is
        # channel x MCC band x region. Without them, serve-time stratification silently degrades to
        # rail-only while FIT used the full stratum -- the p-values would then be computed in a
        # different stratum than they were calibrated in, which is a train/serve skew with no
        # visible symptom.
        "mcc": mcc_col,
        "geo_cell": cols["geo_cell"].astype(str),
    }
    for name in ORACLE_FIELDS:
        if name in cols:
            meta[name] = cols[name]
    # Audit-only columns (computed, reconciled, but never model inputs) live in meta.
    for name in audit_names:
        meta[name] = np.asarray(f[name], dtype=np.float64)

    return FeatureMatrix(
        names=tuple(model_names),
        X=X,
        event_ids=cols["event_id"].astype(str),
        ts=ts,
        meta=meta,
    )
