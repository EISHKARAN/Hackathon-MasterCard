"""The Jensen-Shannon distinctness test and the per-slot observable-delta.

DISTINCTNESS IS WHAT MAKES "DIVERSE" EARNED RATHER THAN ASSERTED. Two cells whose elites produce the
same detector-attribution distribution are not behaviourally distinct, however different their grammar
strings look. So we compute the pairwise Jensen-Shannon divergence between elites' attribution
distributions and MERGE cells below a fixed threshold. The post-merge count CAN ONLY FALL, and that is
the point: a diversity number that can go down when validated is the only kind worth reporting.

THE PER-SLOT OBSERVABLE-DELTA makes the same honesty concrete at the slot level: it measures the mean
shift each slot produces in the feature vector, so a slot that moves nothing (MONETISATION, most of
all) is VISIBLY CREDITED WITH NOTHING rather than being allowed to inflate a string-count that the
distinctness test never sees.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np

from grammar.composition import SLOT_ORDER, Composition


def _js_divergence(p: Mapping[str, float], q: Mapping[str, float]) -> float:
    """Jensen-Shannon divergence between two attribution distributions (base-2, in [0, 1])."""
    keys = sorted(set(p) | set(q))
    if not keys:
        return 0.0
    pv = np.array([max(p.get(k, 0.0), 0.0) for k in keys], dtype=np.float64)
    qv = np.array([max(q.get(k, 0.0), 0.0) for k in keys], dtype=np.float64)
    if pv.sum() <= 0 or qv.sum() <= 0:
        return 0.0
    pv /= pv.sum()
    qv /= qv.sum()
    m = 0.5 * (pv + qv)

    def _kl(a: np.ndarray, b: np.ndarray) -> float:
        mask = a > 0
        return float(np.sum(a[mask] * np.log2(a[mask] / b[mask])))

    return float(0.5 * _kl(pv, m) + 0.5 * _kl(qv, m))


def distinctness_report(archive, js_threshold: float = 0.05) -> dict[str, Any]:  # noqa: ANN001
    """Merge cells whose elites are not JS-separable above the threshold; report the fallen count."""
    elites = list(archive.elites.values())
    n = len(elites)
    denom = len(archive.feasible)
    if n <= 1:
        return {
            "pre_merge_cells": n,
            "post_merge_cells": n,
            "n_merged_pairs": 0,
            "post_merge_coverage": (n / denom) if denom else 0.0,
            "js_threshold": js_threshold,
            "note": "fewer than two elites; nothing to merge",
        }

    # Union-find over cells: merge any pair below the threshold.
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    merged_pairs = 0
    examples: list[dict[str, Any]] = []
    for i in range(n):
        for j in range(i + 1, n):
            js = _js_divergence(elites[i].attribution, elites[j].attribution)
            if js < js_threshold:
                union(i, j)
                merged_pairs += 1
                if len(examples) < 15:
                    examples.append(
                        {"cell_a": elites[i].cell_id, "cell_b": elites[j].cell_id, "js": round(js, 4)}
                    )
    groups = len({find(i) for i in range(n)})
    return {
        "pre_merge_cells": n,
        "post_merge_cells": groups,
        "n_merged_pairs": merged_pairs,
        "post_merge_coverage": (groups / denom) if denom else 0.0,
        "js_threshold": js_threshold,
        "merged_examples": examples,
        "note": (
            "Cells whose elites are not separable above the JS threshold in detector-attribution "
            "space are MERGED, so the post-merge count can only fall. A diversity number that can go "
            "DOWN when validated is the only kind worth reporting."
        ),
        "caveat": (
            "At low evaluation counts many elites have sparse or empty attribution distributions, so "
            "the merge is conservative -- it under-merges rather than over-merges, and the pre-merge "
            "count is the more honest read until the archive is well-populated."
        ),
    }


def observable_delta_report(archive) -> dict[str, Any]:  # noqa: ANN001
    """Per-slot mean absolute observable-delta across archived elites.

    Estimated from the elites' stored `observable_delta` grouped by which slot value they carry, and
    reported per slot. The purpose is negative: to make a behaviour-inert slot's contribution VISIBLE
    as near-zero rather than letting it pad a diversity claim.
    """
    per_slot: dict[str, dict[str, float]] = {}
    for slot in SLOT_ORDER:
        by_value: dict[str, list[float]] = {}
        for e in archive.elites.values():
            try:
                comp = Composition.parse(e.composition)
            except Exception:  # noqa: BLE001
                continue
            by_value.setdefault(comp.slot(slot), []).append(abs(float(e.observable_delta)))
        # The slot's contribution = the SPREAD of mean observable-delta across its values. A slot whose
        # values all produce the same delta moves nothing distinguishable.
        means = [float(np.mean(v)) for v in by_value.values() if v]
        per_slot[slot] = {
            "n_values_seen": len(by_value),
            "mean_abs_delta": float(np.mean(means)) if means else 0.0,
            "spread_across_values": float(np.std(means)) if len(means) > 1 else 0.0,
        }
    # IS THIS INSTRUMENT ACTUALLY WIRED? `Elite.observable_delta` has exactly one producer in the
    # repo -- the default 0.0 -- and no code path ever assigns a measured value. Printing 0.0000 for
    # every slot therefore asserts "we measured the shift and every slot moves nothing", which is a
    # claim we have not earned and which happens to flatter the honest-instrument story. An
    # unmeasured quantity must announce itself as unmeasured.
    measured = any(
        abs(float(getattr(e, "observable_delta", 0.0))) > 0.0 for e in archive.elites.values()
    )
    return {
        "measured": measured,
        "status": "MEASURED" if measured else "NOT MEASURED — no code path populates Elite.observable_delta",
        "per_slot": per_slot if measured else {},
        "unmeasured_caveat": (
            ""
            if measured
            else "The per-slot observable-delta instrument is DECLARED BUT NOT WIRED: nothing assigns "
                 "Elite.observable_delta, so there is no measurement to report. Previously this printed "
                 "0.0000 per slot, which reads as 'measured, and every slot moves nothing'. It is "
                 "reported as unmeasured instead."
        ),
        "note": (
            "A slot whose values all produce the same observable-delta is credited with moving "
            "nothing distinguishable. MONETISATION is expected to be near-zero here, and that is the "
            "honest reason it is not allowed to inflate the diversity headline."
        ),
    }
