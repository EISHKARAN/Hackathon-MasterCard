"""`make grammar` — enumerate, type-check, and print the machine-counted integers.

This target is the diversity criterion's audit surface. It:

1.  enumerates the raw Cartesian product and type-checks every string;
2.  prints the type-legal count -- **the size of the string space and nothing more**, never
    presented as a diversity claim;
3.  derives the feasible-cell denominator from grammar/feasible_cells.yaml;
4.  asserts every hand-authored row in grammar/seeds.yaml type-checks -- the ONLY proof that
    the attack table is compositions rather than prose;
5.  asserts the sealed manifest's families exist and are disjoint from nothing else;
6.  asserts `reachable_cells` is a subset of the pre-declared feasible set, and FAILS with the
    offending cells listed if not.

Exit code is non-zero on any assertion failure. The number that goes in the deck is whatever
this prints at freeze, and we accept that it may print something below target.
"""

from __future__ import annotations

import argparse
import sys

from core import paths
from core.io import write_json
from core.stagelog import stage
from grammar.enumerate_space import census, legal_cell_index
from grammar.seeds import load_seeds, seed_audit
from grammar.signatures import all_taxonomy_signatures, audit as signature_audit
from grammar.sealed import load_sealed_manifest, sealed_audit


def _fmt_pct(x: float) -> str:
    return f"{100.0 * x:.1f}%"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="make grammar", description=__doc__)
    ap.add_argument(
        "--write-index",
        action="store_true",
        help="also write the cell -> legal-compositions index (large; used by the UI)",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        default=True,
        help="fail on any assertion (default; --no-strict for exploration only)",
    )
    ap.add_argument("--no-strict", dest="strict", action="store_false")
    args = ap.parse_args(argv)

    paths.ensure_writable()
    failures: list[str] = []

    with stage("grammar", "enumerate + type-check + audit") as summary:
        c = census()

        print("\n=== VAJRA GRAMMAR CENSUS (every integer below is machine-counted) ===\n")
        print("Slot vocabularies:")
        for slot, n in c.slot_counts.items():
            print(f"  {slot:<13} {n}")
        print(f"\n  raw string space (Cartesian product)     : {c.raw_space:,}")
        print("    ^ NOT a diversity claim. It is the size of a product, most of it nonsense.")
        print(f"  type-legal compositions                  : {c.type_legal:,}")
        print(f"    pruning rate from the typing matrix    : {_fmt_pct(c.pruning_rate)}")
        print("    ^ This is the SIZE OF THE TYPE-LEGAL STRING SPACE and nothing more.")
        print("      It is subordinate to the post-merge occupied-cell integer and is kept")
        print("      out of the deck headline. See grammar/typing.yaml for why.")

        print(f"\n  nominal archive cells                    : {c.nominal_cells}")
        print(f"  pre-declared FEASIBLE cells (denominator) : {c.feasible_cells}")
        print(f"  cells the grammar can actually reach      : {c.reachable_cells}")
        print(f"  coverage CEILING (reachable / feasible)   : {_fmt_pct(c.coverage_ceiling)}")
        print("    ^ No archive run can exceed this. Printed so our coverage target is read")
        print("      against what the grammar can express, not against 100%.")

        # ---- consistency: reachable must be a subset of feasible ----------------
        cons = c.consistency
        if not cons["ok"]:
            failures.append(
                f"{len(cons['contradictions'])} cells are reachable by the grammar but "
                f"pre-marked INFEASIBLE. One of grammar/feasible_cells.yaml or "
                f"grammar/cell_of.py::admissible_depths is wrong."
            )
            print("\n  !! FEASIBILITY CONTRADICTIONS:")
            for row in cons["contradictions"][:25]:
                print(f"     {row['cell']}  blocked by {row['blocked_by']}")
            if len(cons["contradictions"]) > 25:
                print(f"     ... and {len(cons['contradictions']) - 25} more")
        else:
            print("\n  feasibility consistency                   : OK (reachable subset of feasible)")
        print(
            f"  feasible but NOT reachable                : {cons['feasible_but_unreachable_count']}"
        )
        print("    ^ Honest headroom: cells we believe are physically possible but the")
        print("      grammar cannot currently express. This is the slot-extension target list,")
        print("      reported rather than hidden.")

        # ---- constraint binding ------------------------------------------------
        dead = [cid for cid, n in c.constraint_bind_counts.items() if n == 0]
        print("\n  Constraints that reject nothing            :", dead or "none")
        if dead:
            failures.append(
                f"constraints {dead} reject zero raw strings. A constraint that binds nothing "
                f"is either stale or wrong, and it silently inflates confidence in the matrix."
            )

        # ---- seeds -------------------------------------------------------------
        seeds = load_seeds()
        sa = seed_audit(seeds)
        print(f"\n  hand-authored seed compositions           : {sa['n_seeds']}")
        print(f"    type-check                              : {sa['n_legal']}/{sa['n_seeds']} legal")
        print(f"    each carrying >=3 RESOLVED signatures    : "
              f"{sa['n_with_3_resolved_sigs']}/{sa['n_seeds']}")
        print(f"    distinct cells occupied by seeds         : {sa['n_cells']}")
        print(f"    ATK ids                                 : {sa['n_atk_ids']}")
        if sa["illegal"]:
            failures.append(
                f"{len(sa['illegal'])} seed rows do not type-check. `make grammar` asserts every "
                f"hand-authored row type-checks against the compatibility matrix -- that "
                f"assertion is the only proof the attack table is compositions and not prose."
            )
            for row in sa["illegal"][:20]:
                print(f"     !! {row['id']}: {row['why']}")
        unmarked = sa["under_signed_unmarked"]
        excluded_ok = sa["under_signed_but_correctly_excluded"]
        if excluded_ok:
            print(f"    rows with <3 resolved sigs, correctly marked excluded-from-scoring: "
                  f"{[u['id'] for u in excluded_ok]}")
        if unmarked:
            failures.append(
                f"{len(unmarked)} seed rows have fewer than 3 RESOLVED observable signatures AND are "
                f"not marked excluded-from-scoring: {[u['id'] for u in unmarked]}. A row we cannot "
                f"compute three observables for cannot be a scored family — mark it `double_dagger: "
                f"true` (it stays in the taxonomy for breadth) or give it resolvable signatures."
            )

        # ---- signature resolution: a BUILD GATE ----------------------------------
        sig = signature_audit(all_taxonomy_signatures())
        print(f"\n  taxonomy observables (distinct)           : {sig['n_distinct_signatures']}")
        print(f"    resolve to a schema field               : {sig['n_schema']}")
        print(f"    resolve to a registry feature           : {sig['n_feature']}")
        print(f"    DECLARED design-only (real, not built)  : {sig['n_design_only']}")
        for grp, n in sig["design_only_by_group"].items():
            print(f"      {grp:<22} {n}")
        print(f"    UNRESOLVED                              : {sig['n_unknown']}")
        if sig["n_unknown"]:
            failures.append(
                f"{sig['n_unknown']} taxonomy observables resolve to NOTHING. The taxonomy and the "
                f"implementation have drifted: either alias the name to the column that computes it, "
                f"or declare it design_only with a reason, in grammar/signatures.yaml."
            )
            for u in sig["unknown"][:15]:
                print(f"     !! {u['name']}: {u['reason'][:100]}")
        write_json(sig, paths.reports / "signature_audit.json")

        # ---- sealed manifest ----------------------------------------------------
        manifest = load_sealed_manifest()
        ma = sealed_audit(manifest, seeds)
        print(f"\n  sealed holdout families                   : {ma['n_families']}")
        print(f"    total sealed compositions               : {ma['n_compositions']}")
        print(f"    cells touched by sealed families        : {ma['n_cells']}")
        print(f"    sealed EVASION morphemes (leave-one-out): {ma['loo_evasion_morphemes']}")
        for problem in ma["problems"]:
            failures.append(f"sealed manifest: {problem}")
            print(f"     !! {problem}")

        # ---- artifacts ----------------------------------------------------------
        out = write_json(c.as_dict(), paths.reports / "grammar_census.json")
        print(f"\n  wrote {out.relative_to(paths.root)}")
        write_json(sa, paths.reports / "seed_audit.json")
        write_json(ma, paths.reports / "sealed_audit.json")
        if args.write_index:
            idx = legal_cell_index()
            write_json(idx, paths.artifacts / "legal_cell_index.json")
            print(f"  wrote data/artifacts/legal_cell_index.json ({len(idx)} cells)")

        summary.update(
            {
                "type_legal": c.type_legal,
                "feasible_cells": c.feasible_cells,
                "reachable_cells": c.reachable_cells,
                "seeds": sa["n_seeds"],
                "sealed_families": ma["n_families"],
                "unresolved_signatures": sig["n_unknown"],
                "design_only_signatures": sig["n_design_only"],
                "failures": len(failures),
            }
        )

    if failures:
        print("\n=== GRAMMAR GATE: FAILED ===")
        for f in failures:
            print(f"  - {f}")
        return 1 if args.strict else 0

    print("\n=== GRAMMAR GATE: PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
