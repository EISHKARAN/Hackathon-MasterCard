"""`make generator-b` — generate the independently-authored cross-generator evaluation stream.

Writes data/events/events_generator-b.parquet through the SAME schema contract as the main sim, and
runs the F1 gate on it: an independent generator that produced structurally illegal messages would be
worthless as an artifact-independence check, so it must clear the same invariants.
"""
from __future__ import annotations
import argparse, sys
from core import paths
from core.config import load_config
from core.io import to_table, write_parquet, table_hash, write_json
from core.stagelog import stage
from fidelity.f1_invariants import check_events
from generator_b.emitter import GeneratorB
from sim.schema import canonical_field_order


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="make generator-b", description=__doc__)
    ap.add_argument("--preset", default=None)
    args = ap.parse_args(argv)
    cfg = load_config()
    paths.ensure_writable()
    with stage("generator-b", "cross-generator evaluation stream") as summary:
        gb = GeneratorB.build(args.preset, cfg)
        events = gb.run()
        f1 = check_events(events)
        order = canonical_field_order()
        rows = [e.as_row() for e in events]
        cols = {n: [r[n] for r in rows] for n in order}
        table = to_table(cols, order)
        path = write_parquet(table, paths.events / "events_generator-b.parquet")
        rep = gb.report(events)
        rep["f1"] = {"violations": f1["n_violations"], "passed": f1["passed"]}
        rep["events_logical_hash"] = table_hash(table)
        write_json(rep, paths.reports / "generator_b_report.json")
        print(f"\n=== GENERATOR B (independent, card-CNP + UPI-PAY) ===")
        print(f"  events: {rep['n_events']:,} ({rep['n_attack']} attacks)")
        print(f"  F1 on the independent stream: {f1['n_violations']} violations "
              f"({'PASS' if f1['passed'] else 'FAIL'})")
        print(f"  wrote {path.relative_to(paths.root)}")
        summary.update({"n_events": rep["n_events"], "f1_violations": f1["n_violations"]})
    if not f1["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
