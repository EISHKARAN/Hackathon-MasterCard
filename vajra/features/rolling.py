"""Fast exact (and one documented-approximate) trailing reducers over per-key time windows.

WHY THIS MODULE EXISTS: the obvious implementations do not scale, and the failure mode is a build that
appears to hang rather than one that errors. Two specific blowups, both real:

*   **Per-row `np.median` over a window slice is O(m log m) per row.** For a hub merchant with 100k
    events and a 30-day window, that is a 50k-element sort per row — quadratic in the group size. At
    the `full` preset it does not finish.
*   **Per-row `np.max` over a slice** has the same shape.

So: mean and standard deviation use prefix sums (exact, O(1) per row); max uses a monotone deque
(exact, O(1) amortised); and the trailing median uses a BOUNDED trailing buffer, which is an
approximation and is documented as one rather than presented as exact.

Every reducer here EXCLUDES THE CURRENT ROW. A window that included it would leak the row's own value
into its own baseline, which is a self-leak that produces implausibly good results and no test failure.
"""

from __future__ import annotations

from collections import deque
from typing import Mapping, Sequence

import numpy as np

SENTINEL = -1.0

#: Size of the bounded buffer backing the approximate trailing median. Chosen so the estimate is over
#: the most recent 64 in-window observations, which is where an entity's current behaviour lives.
MEDIAN_BUFFER = 64


def group_indices(keys: np.ndarray) -> dict[str, np.ndarray]:
    """key value -> ascending event indices. One argsort rather than a per-row dict append."""
    k = np.asarray(keys, dtype=object).astype(str)
    if k.size == 0:
        return {}
    order = np.argsort(k, kind="stable")
    sk = k[order]
    change = np.empty(sk.size, dtype=bool)
    change[0] = True
    change[1:] = sk[1:] != sk[:-1]
    starts = np.flatnonzero(change)
    ends = np.append(starts[1:], sk.size)
    out: dict[str, np.ndarray] = {}
    for s, e in zip(starts, ends):
        if sk[s] == "":
            continue
        out[str(sk[s])] = np.sort(order[s:e])
    return out


def trailing_mean_std(
    keys: np.ndarray, ts: np.ndarray, values: np.ndarray, window_s: float
) -> tuple[np.ndarray, np.ndarray]:
    """EXACT trailing mean and standard deviation, O(1) per row via prefix sums.

    Variance from `E[x^2] - E[x]^2` with a clamp at zero: catastrophic cancellation can make that
    expression very slightly negative, and `sqrt` of a negative would produce NaN in a feature column
    that every downstream consumer assumes is finite.
    """
    v = np.asarray(values, dtype=np.float64)
    t = np.asarray(ts, dtype=np.float64)
    mean = np.full(v.shape, SENTINEL, dtype=np.float64)
    std = np.full(v.shape, SENTINEL, dtype=np.float64)
    for idx in group_indices(keys).values():
        g_t, g_v = t[idx], v[idx]
        lo = np.searchsorted(g_t, g_t - window_s, side="left")
        pos = np.arange(idx.size)
        c1 = np.concatenate(([0.0], np.cumsum(g_v)))
        c2 = np.concatenate(([0.0], np.cumsum(g_v * g_v)))
        cnt = (pos - lo).astype(np.float64)
        s1 = c1[pos] - c1[lo]
        s2 = c2[pos] - c2[lo]
        ok = cnt > 0
        m = np.where(ok, s1 / np.maximum(cnt, 1.0), SENTINEL)
        var = np.where(ok, np.maximum(s2 / np.maximum(cnt, 1.0) - m * m, 0.0), -1.0)
        mean[idx] = m
        std[idx] = np.where(cnt >= 2, np.sqrt(np.maximum(var, 0.0)), SENTINEL)
    return mean, std


def trailing_sum_count(
    keys: np.ndarray, ts: np.ndarray, values: np.ndarray, window_s: float
) -> tuple[np.ndarray, np.ndarray]:
    """EXACT trailing sum and count, O(1) per row."""
    v = np.asarray(values, dtype=np.float64)
    t = np.asarray(ts, dtype=np.float64)
    total = np.zeros(v.shape, dtype=np.float64)
    count = np.zeros(v.shape, dtype=np.float64)
    for idx in group_indices(keys).values():
        g_t, g_v = t[idx], v[idx]
        lo = np.searchsorted(g_t, g_t - window_s, side="left")
        pos = np.arange(idx.size)
        c = np.concatenate(([0.0], np.cumsum(g_v)))
        total[idx] = c[pos] - c[lo]
        count[idx] = (pos - lo).astype(np.float64)
    return total, count


def trailing_max(keys: np.ndarray, ts: np.ndarray, values: np.ndarray, window_s: float) -> np.ndarray:
    """EXACT trailing maximum via a monotone deque. O(1) amortised per row.

    The deque holds indices whose values are strictly decreasing, so the front is always the maximum of
    the current window. Popping from the back on insert is what keeps it that way, and it is why this
    is amortised constant rather than a per-row scan.
    """
    v = np.asarray(values, dtype=np.float64)
    t = np.asarray(ts, dtype=np.float64)
    out = np.full(v.shape, SENTINEL, dtype=np.float64)
    for idx in group_indices(keys).values():
        g_t, g_v = t[idx], v[idx]
        dq: deque[int] = deque()
        left = 0
        for p in range(idx.size):
            cutoff = g_t[p] - window_s
            while left < p and g_t[left] < cutoff:
                if dq and dq[0] == left:
                    dq.popleft()
                left += 1
            out[idx[p]] = g_v[dq[0]] if dq else SENTINEL
            while dq and g_v[dq[-1]] <= g_v[p]:
                dq.pop()
            dq.append(p)
    return out


def trailing_median_approx(
    keys: np.ndarray, ts: np.ndarray, values: np.ndarray, window_s: float,
    buffer_size: int = MEDIAN_BUFFER,
) -> np.ndarray:
    """APPROXIMATE trailing median over the most recent `buffer_size` in-window observations.

    THIS IS AN APPROXIMATION AND IT IS LABELLED ONE. An exact windowed median needs an order statistic
    over the whole window, which is O(m log m) per row and does not finish at the `full` preset. The
    estimate is over the most recent 64 in-window values, which is where an entity's current behaviour
    lives; for an entity with fewer than 64 events in the window it is EXACT.

    `features/registry.yaml` records this in the lineage of `amount_ratio_to_own_baseline`, so the
    approximation travels with the feature rather than living only here.
    """
    v = np.asarray(values, dtype=np.float64)
    t = np.asarray(ts, dtype=np.float64)
    out = np.full(v.shape, SENTINEL, dtype=np.float64)
    for idx in group_indices(keys).values():
        g_t, g_v = t[idx], v[idx]
        buf: deque[tuple[float, float]] = deque()
        for p in range(idx.size):
            cutoff = g_t[p] - window_s
            while buf and buf[0][0] < cutoff:
                buf.popleft()
            if buf:
                arr = np.fromiter((x for _ts, x in buf), dtype=np.float64, count=len(buf))
                out[idx[p]] = float(np.median(arr))
            buf.append((float(g_t[p]), float(g_v[p])))
            if len(buf) > buffer_size:
                buf.popleft()
    return out


def trailing_distinct_multi(
    keys: np.ndarray,
    ts: np.ndarray,
    counterparties: np.ndarray,
    windows: Sequence[float],
) -> dict[float, np.ndarray]:
    """EXACT trailing distinct-counterparty counts for SEVERAL windows in ONE pass per key group.

    One pass rather than one pass per window: the per-row Python overhead dominates this computation,
    and with nine entity keys times four windows the naive version is thirty-six full passes over the
    stream. Maintaining four independent left pointers and four multisets inside a single traversal
    cuts that to nine.

    Amortised O(1) per row per window: each element is added once and removed at most once from each
    window's multiset.
    """
    t = np.asarray(ts, dtype=np.float64)
    cp = np.asarray(counterparties, dtype=object).astype(str)
    wins = [float(w) for w in windows]
    out = {w: np.zeros(t.shape, dtype=np.float64) for w in wins}

    for idx in group_indices(keys).values():
        g_t = t[idx]
        g_c = cp[idx]
        lefts = [0] * len(wins)
        counts: list[dict[str, int]] = [dict() for _ in wins]
        distinct = [0] * len(wins)
        for p in range(idx.size):
            for wi, w in enumerate(wins):
                cutoff = g_t[p] - w
                lp = lefts[wi]
                cmap = counts[wi]
                d = distinct[wi]
                while lp < p and g_t[lp] < cutoff:
                    c = g_c[lp]
                    if c != "":
                        nc = cmap.get(c, 0) - 1
                        if nc <= 0:
                            cmap.pop(c, None)
                            d -= 1
                        else:
                            cmap[c] = nc
                    lp += 1
                lefts[wi] = lp
                distinct[wi] = d
                out[w][idx[p]] = float(d)
            c_now = g_c[p]
            if c_now != "":
                for wi in range(len(wins)):
                    cmap = counts[wi]
                    if c_now in cmap:
                        cmap[c_now] += 1
                    else:
                        cmap[c_now] = 1
                        distinct[wi] += 1
    return out


def prev_value(keys: np.ndarray, values: np.ndarray, fill: float = SENTINEL) -> np.ndarray:
    """Previous value for the same key. Trailing, excludes the current row."""
    k = np.asarray(keys, dtype=object).astype(str)
    v = np.asarray(values, dtype=np.float64)
    out = np.full(v.shape, fill, dtype=np.float64)
    last: dict[str, float] = {}
    for i in range(k.size):
        kk = k[i]
        if kk == "":
            continue
        if kk in last:
            out[i] = last[kk]
        last[kk] = float(v[i])
    return out
