"""Grammar invariants: type-check determinism, cell projection, feasibility consistency, seed legality."""

from __future__ import annotations

import random

import pytest

from grammar.cell_of import (
    CELL_CROSSING_SLOTS,
    CELL_PRESERVING_SLOTS,
    CONDITIONAL_SLOTS,
    admissible_depths,
    cell_of,
    mutation_effect,
    nominal_cell_count,
)
from grammar.composition import SLOT_ORDER, Composition, load_slots
from grammar.enumerate_space import census, legal_compositions
from grammar.feasibility import consistency_report, load_feasibility
from grammar.seeds import load_seeds, seed_audit
from grammar.typecheck import load_typechecker


def test_slot_counts_match_declared():
    counts = load_slots().counts()
    assert counts == {"ACCESS": 8, "TRUST": 7, "RAIL": 12, "EVASION": 8, "MONETISATION": 7, "LABEL": 5}


def test_typecheck_is_order_independent():
    """Permuting the constraint list must not change any verdict — the checker must be a set operation."""
    tc = load_typechecker()
    comps = legal_compositions()[:200] + tuple(
        Composition(*c) for c in [("stolen-credential", "kyc-passed", "card-cnp-keyed",
                                    "oracle-probing", "goods-resale", "label-delayed")]
    )
    baseline = {str(c): tc.check(c).ok for c in comps}
    shuffled = list(tc.constraints)
    random.Random(7).shuffle(shuffled)
    from grammar.typecheck import TypeChecker

    tc2 = TypeChecker(shuffled)
    for c in comps:
        assert tc2.check(c).ok == baseline[str(c)]


def test_reachable_subset_of_feasible():
    """The grammar must never reach a cell pre-marked infeasible — the two artifacts are independent."""
    from grammar.cell_of import reachable_cells

    reachable = reachable_cells(legal_compositions())
    rep = consistency_report(reachable)
    assert rep["ok"], f"grammar reaches infeasible cells: {rep['contradictions'][:5]}"


def test_every_constraint_binds_something():
    """A constraint that rejects zero raw strings is stale or wrong."""
    c = census()
    dead = [cid for cid, n in c.constraint_bind_counts.items() if n == 0]
    assert not dead, f"constraints reject nothing: {dead}"


def test_all_seeds_typecheck():
    sa = seed_audit()
    assert sa["n_legal"] == sa["n_seeds"], f"illegal seeds: {sa['illegal']}"


def test_seed_scoreability_invariant():
    """Every seed either has >=3 resolved signatures or is marked excluded-from-scoring."""
    sa = seed_audit()
    assert not sa["under_signed_unmarked"], (
        f"seeds with <3 resolved sigs and not marked excluded: {sa['under_signed_unmarked']}"
    )


def test_evasion_mutation_always_crosses_cell():
    """EVASION has an identity mapping onto a cell axis, so mutating it must cross a cell."""
    seeds = load_seeds()
    vocab = load_slots()
    tc = load_typechecker()
    checked = 0
    for sd in seeds:
        for ev in vocab.ids("EVASION"):
            if ev == sd.composition.EVASION:
                continue
            cand = sd.composition.with_slot("EVASION", ev)
            if not tc.is_legal(cand):
                continue
            eff = mutation_effect(sd.composition, cand, sd.stages)
            assert not eff.cell_preserving, f"EVASION mutation preserved cell: {sd.id} -> {ev}"
            checked += 1
            break
    assert checked > 0


def test_mutation_taxonomy_partitions_slots():
    covered = CELL_PRESERVING_SLOTS | CELL_CROSSING_SLOTS | CONDITIONAL_SLOTS
    assert covered == set(SLOT_ORDER)


def test_monetisation_label_trust_preserve_cell():
    seeds = load_seeds()
    vocab = load_slots()
    tc = load_typechecker()
    for slot in ("MONETISATION", "LABEL", "TRUST"):
        for sd in seeds[:20]:
            for val in vocab.ids(slot):
                if val == sd.composition.slot(slot):
                    continue
                cand = sd.composition.with_slot(slot, val)
                if not tc.is_legal(cand):
                    continue
                if len(cand.differing_slots(sd.composition)) != 1:
                    continue
                eff = mutation_effect(sd.composition, cand, sd.stages)
                assert eff.cell_preserving, f"{slot} mutation crossed a cell: {sd.id}"
                break


def test_signature_resolution_no_unknowns():
    """Every taxonomy observable must resolve or be declared design-only — no unknowns."""
    from grammar.signatures import all_taxonomy_signatures, audit

    a = audit(all_taxonomy_signatures())
    assert a["n_unknown"] == 0, f"unresolved signatures: {[u['name'] for u in a['unknown']]}"
