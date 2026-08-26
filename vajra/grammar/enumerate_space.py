"""Mechanical enumeration of the type-legal composition space.

This is leg (b) of the three-legged discovery story, and it is the leg where **no model is
involved at all**. The other two are (a) the hand-authored seed compositions carrying
provenance and [VERIFY] fields, and (c) the LLM Composer, which is invoked ONLY on a Gap Miner
escape-region report.

Named `enumerate_space` rather than `enumerate` so it cannot shadow the builtin.
"""

from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator

from grammar.cell_of import (
    Cell,
    admissible_depths,
    locus_of,
    nominal_cell_count,
    rail_class_of,
    reachable_cells,
)
from grammar.composition import SLOT_ORDER, Composition, load_slots
from grammar.feasibility import consistency_report, load_feasibility
from grammar.typecheck import load_typechecker


def iter_all() -> Iterator[Composition]:
    """Every string in the raw Cartesian product. 188,160 of them; most are nonsense."""
    vocab = load_slots()
    pools = [vocab.ids(slot) for slot in SLOT_ORDER]
    for combo in itertools.product(*pools):
        yield Composition(*combo)


@lru_cache(maxsize=1)
def legal_compositions() -> tuple[Composition, ...]:
    """The type-legal space, enumerated once per process and cached.

    The cache is not an optimisation detail. Without it, every consumer that needs the legal
    space (each of the 12 sealed families' member sets, the archive initialiser, the cell index)
    re-walks all 188,160 raw strings, and `make grammar` took over four minutes instead of
    seconds. Compositions are immutable, so sharing the tuple is safe.
    """
    tc = load_typechecker()
    return tuple(comp for comp in iter_all() if tc.is_legal(comp))


def iter_legal() -> Iterator[Composition]:
    yield from legal_compositions()


@dataclass(frozen=True)
class GrammarCensus:
    """Everything `make grammar` prints. Every field is machine-counted."""

    slot_counts: dict[str, int]
    raw_space: int
    type_legal: int
    pruning_rate: float
    nominal_cells: int
    feasible_cells: int
    reachable_cells: int
    coverage_ceiling: float
    per_slot_legal_marginals: dict[str, dict[str, int]]
    constraint_bind_counts: dict[str, int]
    consistency: dict[str, object]
    feasibility_audit: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "slot_counts": self.slot_counts,
            "raw_space": self.raw_space,
            "type_legal": self.type_legal,
            "pruning_rate": round(self.pruning_rate, 6),
            "nominal_cells": self.nominal_cells,
            "feasible_cells": self.feasible_cells,
            "reachable_cells": self.reachable_cells,
            "coverage_ceiling": round(self.coverage_ceiling, 6),
            "per_slot_legal_marginals": self.per_slot_legal_marginals,
            "constraint_bind_counts": self.constraint_bind_counts,
            "consistency": self.consistency,
            "feasibility_audit": self.feasibility_audit,
        }


def census() -> GrammarCensus:
    """Enumerate once and derive every published integer from that single pass."""
    vocab = load_slots()
    tc = load_typechecker()
    fmap = load_feasibility()

    raw = 0
    legal: list[Composition] = []
    marginals: dict[str, Counter[str]] = {slot: Counter() for slot in SLOT_ORDER}
    # How many raw strings each constraint actually rejects. A constraint that binds zero
    # strings is dead weight and a constraint that binds nearly everything is doing the whole
    # job alone -- both are worth seeing, and neither is visible from the total.
    binds: Counter[str] = Counter()

    for comp in iter_all():
        raw += 1
        verdict = tc.check(comp)
        if verdict.ok:
            legal.append(comp)
            for slot in SLOT_ORDER:
                marginals[slot][comp.slot(slot)] += 1
        else:
            for cid, _reason in verdict.violations:
                binds[cid] += 1

    reachable = reachable_cells(legal)
    feasible_n = fmap.denominator()

    return GrammarCensus(
        slot_counts=vocab.counts(),
        raw_space=raw,
        type_legal=len(legal),
        pruning_rate=1.0 - (len(legal) / raw if raw else 0.0),
        nominal_cells=nominal_cell_count(),
        feasible_cells=feasible_n,
        reachable_cells=len(reachable),
        coverage_ceiling=(len(reachable) / feasible_n) if feasible_n else 0.0,
        per_slot_legal_marginals={
            slot: dict(sorted(marginals[slot].items())) for slot in SLOT_ORDER
        },
        constraint_bind_counts=dict(sorted(binds.items())),
        consistency=consistency_report(reachable),
        feasibility_audit=fmap.audit(),
    )


def legal_cell_index() -> dict[str, list[str]]:
    """cell_id -> the type-legal composition strings that can occupy it.

    Consumed by the ARCHIVE screen (so a cell click can show what could live there, not only
    what does) and by the MAP-Elites initialiser (so selecting an under-filled cell can
    propose a composition that is actually able to occupy it, rather than mutating blindly and
    discarding).
    """
    index: dict[str, list[str]] = {}
    for comp in iter_legal():
        rc, loc, ev = rail_class_of(comp.RAIL), locus_of(comp.ACCESS), comp.EVASION
        for d in admissible_depths(comp):
            index.setdefault(Cell(rc, loc, ev, d).id, []).append(str(comp))
    return {k: sorted(v) for k, v in sorted(index.items())}
