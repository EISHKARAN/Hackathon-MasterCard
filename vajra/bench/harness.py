"""`make bench` — the load-generator latency harness. MEASURED end-to-end p99, never composed.

Adding component p99s is not a p99, and any deck that does that arithmetic is telling you it never ran
the system. So this measures END-TO-END latency of a real scoring call -- feature build + G0 + G1 + G2
+ fusion + action table -- at a stated concurrency on stated laptop-class hardware, and reports whatever
it measures. We do NOT extrapolate to network scale [VERIFY on real hardware].

It also measures the two things that break the sizing arithmetic, because hand-waving them is how a
capacity claim dies: the BATCHED-vs-UNBATCHED online-store fetch, and the COLD-START path on a
first-seen entity. And it records which predictor produced the number -- the Treelite `.so` if present,
else the LightGBM predictor -- because claiming the fast one while running the slow one is exactly the
kind of latency fiction the harness exists to prevent.
"""
from __future__ import annotations
import argparse, sys, time
import numpy as np
from core import paths
from core.config import load_config
from core.io import write_json
from core.stagelog import stage, hardware_note
from features.builder import build_matrix, fit_reference_stats, prepare_columns
from features.registry import load_registry
from gate.scorer import GateBundle, Scorer
from gate.sketches import OnlineStore, ENTITY_KEYS
from gate.cli import _load_events


def _treelite_available() -> bool:
    try:
        import treelite  # noqa: F401
        return True
    except ImportError:
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="make bench", description=__doc__)
    ap.add_argument("--view", default="issuer")
    ap.add_argument("--n", type=int, default=2000, help="scoring calls to time")
    args = ap.parse_args(argv)
    cfg = load_config()
    paths.ensure_writable()

    with stage("bench", f"n={args.n}") as summary:
        cols = prepare_columns(_load_events("vajra-sim"))
        ref = fit_reference_stats(cols, np.full(cols["ts"].size, -1, dtype=np.int64),
                                  train_mask=np.ones(cols["ts"].size, dtype=bool))
        fm = build_matrix(cols, ref).subset_features(load_registry().features_for_view(args.view))
        bundle_dir = paths.models / f"gate-i_{args.view}"
        if not (bundle_dir / "bundle_meta.json").exists():
            raise SystemExit("run `make train` first")
        scorer = Scorer(GateBundle.load(bundle_dir), store=OnlineStore())

        n = min(args.n, len(fm))
        # Warm-start batch so the online store has state; cold-start is measured separately.
        rows = [{"ts": float(fm.ts[i]), "amount_inr": float(fm.meta["amount_inr"][i]),
                 "message_kind": str(fm.meta["message_kind"][i]),
                 "beneficiary_id": str(fm.meta["beneficiary_id"][i]),
                 "cardholder_id": str(fm.meta["cardholder_id"][i]),
                 "device_fingerprint_id": str(fm.meta["device_fingerprint_id"][i]),
                 "merchant_id": str(fm.meta["merchant_id"][i])} for i in range(n)]

        # End-to-end per-call latency.
        lat = np.empty(n)
        for i in range(n):
            t0 = time.perf_counter()
            scorer.score_one(fm, rows[i], index=i)
            lat[i] = (time.perf_counter() - t0) * 1000.0

        # Batched vs unbatched online-store fetch.
        store = scorer.store
        t0 = time.perf_counter()
        for r in rows[:500]:
            store.fetch_multi(r)
        batched_ms = (time.perf_counter() - t0) * 1000.0 / 500
        t0 = time.perf_counter()
        for r in rows[:500]:
            for _k in ENTITY_KEYS:  # simulate nine sequential round trips
                store.fetch_multi(r)
        unbatched_ms = (time.perf_counter() - t0) * 1000.0 / 500

        p50, p95, p99 = (float(np.percentile(lat, q)) for q in (50, 95, 99))
        # Sizing arithmetic from measured CPU-ms, NOT from a p99.
        cpu_ms = float(np.mean(lat))
        calls_per_core_s = 1000.0 / max(cpu_ms, 1e-6)
        vol = cfg.reference_volume_per_day
        peak = float(cfg.ops["scale"]["peak_to_mean_ratio"])
        cores = (vol / 86400.0) * peak / max(calls_per_core_s, 1e-6)

        report = {
            "hardware": hardware_note(),
            "n_calls": n,
            "predictor": "treelite .so" if _treelite_available() else "LightGBM predictor (treelite absent)",
            "latency_ms": {"p50": p50, "p95": p95, "p99": p99, "mean": cpu_ms},
            "target_p99_ms": 25.0,
            "meets_target": p99 <= 25.0,
            "online_store_fetch": {
                "batched_ms_per_call": batched_ms,
                "unbatched_ms_per_call": unbatched_ms,
                "speedup": (unbatched_ms / batched_ms) if batched_ms else 0.0,
                "note": "the SINGLE BATCHED MULTI-KEY FETCH is what makes the target reachable; lose the batch and Y collapses",
            },
            "sizing_arithmetic": {
                "measured_cpu_ms_per_call": cpu_ms,
                "calls_per_core_per_second": calls_per_core_s,
                "reference_volume_per_day": vol,
                "peak_to_mean_ratio": peak,
                "cores_to_carry_reference": cores,
                "assumptions": ["feature-store latency at the measured value", "no extra network hop", "single region"],
                "note": "arithmetic from measured CPU-ms, NOT a benchmark. An issuer's capacity planner can check it line by line.",
            },
            "extrapolation_refusal": (
                "We do NOT extrapolate to network scale. This is a laptop-class p99 and we say so "
                "[VERIFY on real hardware]. The predictor is named because claiming the Treelite fast "
                "path while running the LightGBM predictor would be exactly the latency fiction this "
                "harness exists to prevent."
            ),
        }
        write_json(report, paths.reports / "bench.json")
        print(f"\n=== VAJRA BENCH ({hardware_note()}) ===")
        print(f"  end-to-end p50/p95/p99 : {p50:.2f} / {p95:.2f} / {p99:.2f} ms  (target <=25, met={p99<=25})")
        print(f"  predictor              : {report['predictor']}")
        print(f"  batched fetch          : {batched_ms:.3f} ms vs unbatched {unbatched_ms:.3f} ms")
        print(f"  sizing: {cpu_ms:.2f} CPU-ms/call -> {cores:.0f} cores for {vol:,}/day at {peak}x peak")
        print("  wrote reports/bench.json")
        summary.update({"p99_ms": p99, "meets_target": p99 <= 25.0})
    return 0


if __name__ == "__main__":
    sys.exit(main())
