"""`make report` — roll every stage's JSON into reports/report.md, the one-page evidence index.

Reads only what other stages already wrote, so it is cheap and cannot itself compute a number wrong.
Missing sections are reported as 'not generated (run the relevant target)' rather than fabricated.
"""
from __future__ import annotations
import sys
from core import paths
from core.io import read_json
from core.stagelog import stage


def _get(name):
    p = paths.reports / name
    return read_json(p) if p.exists() else None


def main() -> int:
    paths.ensure_writable()
    with stage("report") as summary:
        L = []
        A = L.append
        A("# VAJRA — evidence index\n")
        A("> Every number here is a MEASUREMENT from this run. Sections marked 'not generated' need "
          "their `make` target run first.\n")

        g = _get("grammar_census.json")
        if g:
            A(f"## Grammar (`make grammar`)\n")
            A(f"- type-legal compositions: **{g['type_legal']:,}** (of {g['raw_space']:,} raw, "
              f"{g['pruning_rate']*100:.1f}% pruned) — the string-space size, NOT the diversity headline")
            A(f"- feasible cells: **{g['feasible_cells']}** / {g['nominal_cells']} nominal; "
              f"reachable {g['reachable_cells']} (ceiling {g['coverage_ceiling']*100:.1f}%)\n")

        sim = _get("sim_report_vajra-sim.json")
        if sim:
            A(f"## Simulator (`make sim`)\n")
            A(f"- events: **{sim['n_events']:,}** over {sim['n_days']} days, {sim['n_attack_events']} attacks")
            A(f"- **F1 invariant gate: {sim['f1']['n_violations']} violations** across "
              f"{sim['f1']['n_invariants']} invariants — the never-cut gate")
            A(f"- events logical hash: `{sim['artifacts']['events_logical_hash']}`\n")

        fid = _get("fidelity.json")
        if fid:
            A(f"## Fidelity (`make fidelity`)\n")
            A(f"- provenance: T1={fid['provenance']['counts_by_tier']['T1']} (exactly the two "
              f"conditionals), T2={fid['provenance']['counts_by_tier']['T2']}, "
              f"T3={fid['provenance']['counts_by_tier']['T3']}")
            A(f"- F1: {fid['f1']['n_violations']} violations; F3/F5/F6 pass-rate "
              f"{fid['f3_f5_f6']['summary']['pass_rate_of_checked']*100:.0f}% "
              f"({fid['f3_f5_f6']['summary']['n_failed_shipped_visible']} failures SHIPPED VISIBLE)\n")

        m = _get("metrics_issuer.json")
        if m:
            rp = m.get("reportable", {})
            A(f"## Detection (`make eval`)\n")
            if not rp.get("is_reportable", True):
                A(f"> **NOT REPORTABLE at this scale** — {rp.get('n_positives_in_test_window')} test "
                  f"positives, below the {rp.get('minimum_for_headline')} floor. Numbers are wiring "
                  f"evidence. Run `make sim PRESET=full`.")
            h = m["headline"]
            A(f"- recall @ 0.1% FPR: {h['recall_at_fixed_fpr']['recall']:.3f}; "
              f"PR-AUC: {h['pr_auc_average_precision']:.3f}; ROC-AUC {h['roc_auc']['value']:.3f} (not the headline)")
            cc = m["controlled_comparison"]
            A(f"- vs baseline replica: {cc['delta_vs_baseline']['reported_as']}")
            A(f"- leakage suite: {'PASSED' if m['leakage']['passed'] else 'FAILED'} "
              f"({m['leakage']['n_skipped_unverifiable']} skipped-unverifiable)\n")

        ar = _get("archive_report.json")
        if ar:
            c = ar["coverage"]; d = ar["distinctness"]
            A(f"## Archive (`make archive-report`)\n")
            A(f"- pre-merge cells==elites: {c['occupied_cells']}; post-merge: {d['post_merge_cells']} "
              f"(coverage {d['post_merge_coverage']*100:.1f}%, can only fall)")
            A(f"- {c['search_claim']}\n")

        lp = _get("loop_report.json")
        if lp:
            A(f"## Loop (`make loop`)\n")
            for row in lp["loop_lift"]["comparisons"]:
                A(f"- {row['comparison']}: {row['verdict']}")
            A("")

        b = _get("bench.json")
        if b:
            A(f"## Latency (`make bench`)\n")
            A(f"- end-to-end p99: **{b['latency_ms']['p99']:.1f} ms** (target {b['target_p99_ms']}, "
              f"met={b['meets_target']}), predictor: {b['predictor']}")
            A(f"- sizing: {b['sizing_arithmetic']['cores_to_carry_reference']:.0f} cores for the "
              f"reference portfolio; NOT extrapolated to network scale\n")

        v = _get("verify_register.json")
        if v:
            A(f"## Honesty instruments\n")
            A(f"- [VERIFY] markers: {v['n_markers']} — verifiable claims we refused to fake")
        dl = _get("duallog.json")
        if dl:
            A(f"- dual-use lint: {dl['summary']['n_rules']} rules, {dl['summary']['n_rejected']} rejections logged\n")

        for name in ("grammar_census.json","sim_report_vajra-sim.json","fidelity.json",
                     "metrics_issuer.json","archive_report.json","loop_report.json","bench.json"):
            if not _get(name):
                A(f"- *{name}: not generated (run the relevant target)*")

        (paths.reports / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
        print("  wrote reports/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
