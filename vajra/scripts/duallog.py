"""`make duallog` — render the dual-use lint's reject log.

A filter whose output you cannot see is an assertion. This renders what was PROPOSED and REFUSED, which
is the evidence that the boundary was enforced during the build and lets a reviewer disagree with a
specific decision rather than with our self-description.
"""
from __future__ import annotations
import sys
from attack.dual_use_lint import RejectLog, RULES, rule_count
from core import paths
from core.io import write_json
from core.stagelog import stage


def main() -> int:
    paths.ensure_writable()
    with stage("duallog") as summary:
        log = RejectLog().load()
        s = log.summary()
        print("\n=== VAJRA DUAL-USE REJECT LOG ===")
        print(f"  lint rules (machine-counted) : {rule_count()}")
        print(f"  proposals recorded           : {s['n_entries']}")
        print(f"  rejected                     : {s['n_rejected']}")
        for rid, n in s["rejections_per_rule"].items():
            print(f"    {rid}: {n}")
        # Ensure the committed artifact reflects the current rule set even with no proposals yet.
        log.save()
        write_json({"rules": [{"id": r.id, "rationale": r.rationale} for r in RULES], "summary": s},
                   paths.reports / "duallog.json")
        print(f"\n  reject log: {log.path.relative_to(paths.root)}")
        print("  wrote reports/duallog.json")
        summary.update({"n_rules": rule_count(), "n_rejected": s["n_rejected"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
