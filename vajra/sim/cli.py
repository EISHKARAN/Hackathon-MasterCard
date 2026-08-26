"""`make sim` — generate the world, write Parquet, and RUN THE F1 GATE.

Exit code is non-zero on any F1 violation. That is the never-cut gate: without it, nothing
downstream means anything, because the data could be structurally impossible and no test would
notice.
"""

from __future__ import annotations

import argparse
import sys

from attack.campaigns import campaign_summary, campaigns_from_seeds
from core import paths
from core.config import load_config
from core.io import table_hash, to_table, write_json, write_parquet
from core.stagelog import stage
from fidelity.f1_invariants import check_events, invariant_catalogue, invariant_count
from sim.engine import run_sim
from sim.labels import LabelRecord
from sim.schema import canonical_field_order, field_count


def _labels_table(records: list[LabelRecord]):
    order = ("event_id", "channel", "as_of_ts", "label", "poisoned")
    cols = {
        "event_id": [r.event_id for r in records],
        "channel": [r.channel for r in records],
        "as_of_ts": [float(r.as_of_ts) for r in records],
        "label": [int(r.label) for r in records],
        "poisoned": [bool(r.poisoned) for r in records],
    }
    return to_table(cols, order)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="make sim", description=__doc__)
    ap.add_argument("--preset", default=None, help="smoke | small | full (default from config)")
    ap.add_argument("--generator", default="vajra-sim", help="vajra-sim | generator-b")
    ap.add_argument(
        "--no-attacks", action="store_true",
        help="benign-only world. Used by the Sentinel's benign-drift NULL MODEL: the same world "
             "replayed without attack campaigns, seasonal terms included.",
    )
    ap.add_argument(
        "--max-violation-report", type=int, default=200,
        help="how many individual violations to include in the report",
    )
    args = ap.parse_args(argv)

    cfg = load_config()
    paths.ensure_writable()
    preset = cfg.preset(args.preset)

    with stage("sim", f"preset={preset['name']} generator={args.generator}") as summary:
        print(f"\n=== VAJRA SIM ({preset['name']}) ===")
        print(f"  {preset['label']}")
        print(f"  canonical schema fields (machine-counted): {field_count()}")
        print(f"  F1 invariants (machine-counted)          : {invariant_count()}")

        campaigns = [] if args.no_attacks else campaigns_from_seeds(preset["name"], cfg)
        csum = campaign_summary(campaigns)
        print(f"\n  campaigns: {csum['n_campaigns']} across {csum['n_families']} families, "
              f"{csum['n_cells']} cells ({csum['n_sealed_campaigns']} sealed)")

        result = run_sim(preset["name"], campaigns, cfg, generator=args.generator)
        rep = result.report
        print(f"\n  events generated : {rep['n_events']:,} over {rep['n_days']} days "
              f"({rep['wall_clock_seconds']}s)")
        print(f"  attack events    : {rep['n_attack_events']:,} "
              f"(realised share {rep['realised_attack_share']:.4%} vs configured "
              f"{rep['configured_base_rate']:.4%})")
        print(f"  approval rate    : {rep['approval_rate']:.3%}")
        print(f"  label records    : {rep['labels']['table']['n_records']:,}")
        print("  events by rail:")
        for rail, n in rep["events_by_rail"].items():
            print(f"    {rail:<26} {n:>9,}")

        # ---- F1 GATE ------------------------------------------------------------------
        print("\n  --- F1 INVARIANT GATE ---")
        f1 = check_events(result.events, max_report=args.max_violation_report)
        print(f"  invariants checked : {f1['n_invariants']}")
        print(f"  violations         : {f1['n_violations']:,}")
        if not f1["passed"]:
            print("\n  !! F1 VIOLATIONS BY INVARIANT:")
            for iid, n in f1["violations_by_invariant"].items():
                print(f"     {iid:<24} {n:>9,}")
            print("\n  !! SAMPLE VIOLATIONS:")
            for v in f1["sample_violations"][:25]:
                print(f"     {v['invariant_id']} [{v['rail']}/{v['message_kind']}] "
                      f"{v['event_id']}: {v['detail']}")

        # ---- write artifacts -----------------------------------------------------------
        order = canonical_field_order()
        rows = [ev.as_row() for ev in result.events]
        cols = {name: [r[name] for r in rows] for name in order}
        table = to_table(cols, order)
        ev_path = write_parquet(table, paths.events / f"events_{args.generator}.parquet")
        ev_hash = table_hash(table)

        lab_records = result.labels.table.all_records()
        lab_path = write_parquet(
            _labels_table(lab_records), paths.labels / f"labels_{args.generator}.parquet"
        )

        rep["artifacts"] = {
            "events_parquet": str(ev_path.relative_to(paths.root)),
            "labels_parquet": str(lab_path.relative_to(paths.root)),
            "events_logical_hash": ev_hash,
            "n_label_records": len(lab_records),
        }
        rep["f1"] = f1
        rep["campaigns"] = csum
        rep["schema_field_count"] = field_count()
        write_json(rep, paths.reports / f"sim_report_{args.generator}.json")
        write_json(invariant_catalogue(), paths.reports / "f1_invariant_catalogue.json")

        print(f"\n  wrote {ev_path.relative_to(paths.root)}")
        print(f"  wrote {lab_path.relative_to(paths.root)}")
        print(f"  events logical hash: {ev_hash}")
        print(f"  wrote reports/sim_report_{args.generator}.json")

        summary.update(
            {
                "n_events": rep["n_events"],
                "n_attack_events": rep["n_attack_events"],
                "f1_violations": f1["n_violations"],
                "events_hash": ev_hash,
            }
        )

    if not f1["passed"]:
        print("\n=== F1 GATE: FAILED — no data ships ===")
        return 1
    print("\n=== F1 GATE: PASSED (0 violations) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
