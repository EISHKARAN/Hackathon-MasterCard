"""The multi-key velocity panel, vectorised.

This is the largest feature family (144 + 36 = 180 of ~388) and the most expensive to compute, so
it gets its own module and an explicit algorithm note.

ALGORITHM. For each entity key column and each trailing window:

  1. Group event indices by key value. Within a group the events are already in timestamp order,
     because the stream is sorted before features are built.
  2. For a group's timestamp array `t`, the count in the trailing window `w` at position `i` is
     `i - searchsorted(t, t[i] - w, side='left')`, computed for the whole group at once.
  3. The amount sum in the window is a cumulative-sum difference at the same indices.

That is O(n log n) per (key, window) and it is exact — no approximation, no decay. The APPROXIMATE
counters are a separate thing entirely (gate/sketches/, used inline at serving time where the full
history is not available); this module computes the exact training-time values.

THE DUAL ENCODING, which is the whole point:

  ratio = statistic(window) / (entity's own trailing 30d statistic, scaled to the window length)
  pct   = percentile of the raw statistic within the entity's PEER COHORT

A single absolute encoding is defeated by an attacker who keeps every per-key counter
sub-threshold. The ratio catches the self-relative spike; the percentile catches the
population-relative one. Neither alone is sufficient and that is why both ship.

CAUSALITY. Every window is TRAILING and STRICTLY PAST-INCLUSIVE at the current row: position `i`
sees events `[searchsorted(...), i)`, never `i` itself and never anything after it. A window that
included the current row would leak the row's own amount into its own baseline, which is a subtle
self-leak that produces implausibly good results and no test failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

#: Window lengths in seconds, keyed by the registry's window labels.
WINDOW_SECONDS: dict[str, float] = {
    "1h": 3_600.0,
    "24h": 86_400.0,
    "7d": 7 * 86_400.0,
    "30d": 30 * 86_400.0,
}

#: The window used as the entity's own trailing BASELINE for the ratio encoding.
BASELINE_WINDOW = "30d"

#: Sentinel for "this entity has no history yet". Kept distinct from 0.0, because
#: "no baseline" and "a baseline of zero" mean different things to a tree split.
NO_HISTORY = -1.0


@dataclass
class VelocityPanel:
    """Computed panel: name -> float array aligned to the event order."""

    columns: dict[str, np.ndarray]

    def merge(self, other: "VelocityPanel") -> "VelocityPanel":
        self.columns.update(other.columns)
        return self


def _group_indices(keys: np.ndarray) -> dict[str, np.ndarray]:
    """Map each non-empty key value to its event indices, in order.

    Uses a single argsort rather than a Python dict-append loop: at 500k events the loop
    dominates the whole feature build.
    """
    order = np.argsort(keys, kind="stable")
    sorted_keys = keys[order]
    # Boundaries where the key value changes.
    if sorted_keys.size == 0:
        return {}
    change = np.empty(sorted_keys.size, dtype=bool)
    change[0] = True
    change[1:] = sorted_keys[1:] != sorted_keys[:-1]
    starts = np.flatnonzero(change)
    ends = np.append(starts[1:], sorted_keys.size)
    out: dict[str, np.ndarray] = {}
    for s, e in zip(starts, ends):
        kv = sorted_keys[s]
        if kv == "":
            continue
        out[str(kv)] = np.sort(order[s:e])
    return out


def _trailing_count_and_sum(
    ts: np.ndarray, amounts: np.ndarray, window_s: float
) -> tuple[np.ndarray, np.ndarray]:
    """Exact trailing count and amount sum over a window, EXCLUDING the current row.

    `lo[i] = searchsorted(ts, ts[i] - window, 'left')`, so the window is
    `[ts[i]-window, ts[i])` in index terms `[lo[i], i)`.
    """
    n = ts.size
    if n == 0:
        return np.zeros(0), np.zeros(0)
    lo = np.searchsorted(ts, ts - window_s, side="left")
    idx = np.arange(n)
    counts = (idx - lo).astype(np.float64)
    csum = np.concatenate(([0.0], np.cumsum(amounts, dtype=np.float64)))
    sums = csum[idx] - csum[lo]
    return counts, sums


def _trailing_distinct(
    ts: np.ndarray, counterparties: np.ndarray, window_s: float
) -> np.ndarray:
    """Exact trailing distinct-counterparty count over a window, excluding the current row.

    Two-pointer over the group with a running multiset. O(m) per group amortised, which matters:
    a naive per-row set construction is O(m^2) and at a hub merchant with 50k events that is the
    single slowest thing in the pipeline.
    """
    n = ts.size
    out = np.zeros(n, dtype=np.float64)
    if n == 0:
        return out
    counts: dict[str, int] = {}
    left = 0
    distinct = 0
    for i in range(n):
        # Drop anything that has fallen out of the window relative to ts[i].
        cutoff = ts[i] - window_s
        while left < i and ts[left] < cutoff:
            cp = counterparties[left]
            if cp != "":
                c = counts.get(cp, 0) - 1
                if c <= 0:
                    counts.pop(cp, None)
                    distinct -= 1
                else:
                    counts[cp] = c
            left += 1
        out[i] = float(distinct)
        cp_i = counterparties[i]
        if cp_i != "":
            if cp_i not in counts:
                counts[cp_i] = 1
                distinct += 1
            else:
                counts[cp_i] += 1
    return out


def _percentile_within_cohort(values: np.ndarray, cohort: np.ndarray) -> np.ndarray:
    """Percentile rank of each value within its cohort, in [0, 1].

    Computed over the WHOLE column, which is legitimate here and worth being explicit about: the
    cohort percentile is a rank against the population, and the population it ranks against is the
    TRAINING window only. `eval/leakage/statistic_fit.py` asserts that the quantile edges used at
    serving time were fitted on the training window with holdout-family rows excluded — a cohort
    percentile fitted over a pool containing sealed rows would import holdout information into
    every percentile feature without a single entity id crossing the boundary.
    """
    out = np.zeros(values.size, dtype=np.float64)
    for cid in np.unique(cohort):
        mask = cohort == cid
        v = values[mask]
        if v.size <= 1:
            out[mask] = 0.5
            continue
        order = np.argsort(v, kind="stable")
        ranks = np.empty(v.size, dtype=np.float64)
        ranks[order] = np.arange(v.size, dtype=np.float64)
        # Average ties so identical values get identical percentiles. Without this, a mass point
        # (very common: thousands of entities with a count of exactly 0) would be spread across
        # the whole [0,1] range purely by argsort order, which is noise dressed as signal.
        uniq, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
        starts = np.concatenate(([0], np.cumsum(cnt)[:-1]))
        mean_rank = starts + (cnt - 1) / 2.0
        ranks = mean_rank[inv]
        out[mask] = ranks / max(1.0, v.size - 1)
    return out


def compute_panel(
    *,
    ts: np.ndarray,
    amounts: np.ndarray,
    key_columns: Mapping[str, np.ndarray],
    counterparty_for_key: Mapping[str, np.ndarray],
    cohort: np.ndarray,
    windows: Sequence[str],
    want_ratio: bool = True,
    want_pct: bool = True,
    want_distinct: bool = True,
) -> VelocityPanel:
    """Compute the whole velocity panel.

    `key_columns` maps an entity-key name to its per-event value array.
    `counterparty_for_key` maps the same names to the counterparty array used for the distinct
    count (merchant for card keys, payer/payee for account keys).
    """
    n = ts.size
    cols: dict[str, np.ndarray] = {}
    baseline_s = WINDOW_SECONDS[BASELINE_WINDOW]

    for key_name, key_vals in key_columns.items():
        groups = _group_indices(np.asarray(key_vals, dtype=object).astype(str))
        cp_vals = np.asarray(
            counterparty_for_key.get(key_name, np.full(n, "", dtype=object)), dtype=object
        ).astype(str)

        raw_count: dict[str, np.ndarray] = {w: np.zeros(n) for w in windows}
        raw_sum: dict[str, np.ndarray] = {w: np.zeros(n) for w in windows}
        raw_distinct: dict[str, np.ndarray] = {w: np.zeros(n) for w in windows}
        base_count = np.zeros(n)
        base_sum = np.zeros(n)
        has_history = np.zeros(n, dtype=bool)

        for idx in groups.values():
            g_ts = ts[idx]
            g_amt = amounts[idx]
            g_cp = cp_vals[idx]
            bc, bs = _trailing_count_and_sum(g_ts, g_amt, baseline_s)
            base_count[idx] = bc
            base_sum[idx] = bs
            has_history[idx] = bc > 0
            for w in windows:
                ws = WINDOW_SECONDS[w]
                c, s = _trailing_count_and_sum(g_ts, g_amt, ws)
                raw_count[w][idx] = c
                raw_sum[w][idx] = s
                if want_distinct:
                    raw_distinct[w][idx] = _trailing_distinct(g_ts, g_cp, ws)

        for w in windows:
            ws = WINDOW_SECONDS[w]
            scale = ws / baseline_s          # expected share of the baseline in this window
            if want_ratio:
                # ratio = observed / expected-from-own-baseline. NO_HISTORY where there is no
                # baseline at all, so a tree can split on "unknown" rather than being told 0.
                exp_c = np.maximum(base_count * scale, 1e-9)
                exp_s = np.maximum(base_sum * scale, 1e-9)
                rc = np.where(has_history, raw_count[w] / exp_c, NO_HISTORY)
                rs = np.where(has_history, raw_sum[w] / exp_s, NO_HISTORY)
                cols[f"vel_{key_name}_{w}_count_ratio"] = rc
                cols[f"vel_{key_name}_{w}_amount_sum_ratio"] = rs
            if want_pct:
                cols[f"vel_{key_name}_{w}_count_pct"] = _percentile_within_cohort(raw_count[w], cohort)
                cols[f"vel_{key_name}_{w}_amount_sum_pct"] = _percentile_within_cohort(
                    raw_sum[w], cohort
                )
            if want_distinct:
                cols[f"vel_{key_name}_{w}_distinct_counterparty"] = raw_distinct[w]

    return VelocityPanel(columns=cols)
