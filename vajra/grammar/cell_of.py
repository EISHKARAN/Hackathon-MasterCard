"""The cell projection, published as executable code rather than left implied.

The archive's four axes are NOT the grammar's six slots, and getting this wrong is the
easiest way to overclaim the sibling metric. So the projection is code:

    RAIL (12 morphemes)  --many-to-one-->  RAIL-CLASS (6)
    ACCESS (8 morphemes) --many-to-one-->  AUTHORISATION-LOCUS (4)
    EVASION (8)          --identity----->  EVASION-MECHANISM (8)
    KILL-CHAIN DEPTH (3) <-- NOT A SLOT: derived from the plan's stage count

Because depth is not a slot, **a grammar string alone does not determine its cell**, and
`cell_of` takes the plan too. Anyone reading "a cell freezes rail, locus, evasion and depth"
would therefore be misled, and we do not write that.

What follows from the projections is a mutation taxonomy, computed by `mutation_effect()`
rather than asserted:

    always cell-preserving : MONETISATION, LABEL, TRUST
    always cell-crossing   : EVASION (the identity mapping), any depth change
    conditionally either   : ACCESS, RAIL — decided by the projection

So same-cell sibling recall is the EASY tier, and the number we quote is a **cross-cell
sibling whose EVASION morpheme is mutated** — the one slot guaranteed to cross a cell.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence

from grammar.composition import SLOT_ORDER, Composition, load_slots

#: The four axes, in canonical order. Nominal cell count is the product, computed never stated.
RAIL_CLASSES: tuple[str, ...] = (
    "card-auth",
    "card-post-auth",
    "card-token",
    "upi-realtime",
    "mandate-recurring",
    "a2a-assisted",
)

AUTHORISATION_LOCI: tuple[str, ...] = (
    "stolen-credential",
    "synthetic-identity",
    "authorised-but-deceived-victim",
    "delegated-agent-mandate",
)

DEPTHS: tuple[int, ...] = (1, 2, 3)

#: Slots that can never change the cell, by construction of the projection.
CELL_PRESERVING_SLOTS: frozenset[str] = frozenset({"TRUST", "MONETISATION", "LABEL"})
#: Slots that always change the cell.
CELL_CROSSING_SLOTS: frozenset[str] = frozenset({"EVASION"})
#: Slots whose effect depends on where the projection lands.
CONDITIONAL_SLOTS: frozenset[str] = frozenset({"ACCESS", "RAIL"})


def _assert_partition() -> None:
    covered = CELL_PRESERVING_SLOTS | CELL_CROSSING_SLOTS | CONDITIONAL_SLOTS
    if covered != set(SLOT_ORDER):
        raise AssertionError(
            f"the mutation taxonomy must partition the slots exactly; "
            f"missing={set(SLOT_ORDER) - covered}, extra={covered - set(SLOT_ORDER)}"
        )


_assert_partition()


@dataclass(frozen=True, order=True)
class Cell:
    """One archive cell: (rail_class, locus, evasion, depth)."""

    rail_class: str
    locus: str
    evasion: str
    depth: int

    @property
    def id(self) -> str:
        return f"{self.rail_class}|{self.locus}|{self.evasion}|d{self.depth}"

    @classmethod
    def from_id(cls, cell_id: str) -> "Cell":
        parts = cell_id.split("|")
        if len(parts) != 4 or not parts[3].startswith("d"):
            raise ValueError(f"malformed cell id {cell_id!r}; expected 'rail|locus|evasion|dN'")
        return cls(parts[0], parts[1], parts[2], int(parts[3][1:]))

    def as_dict(self) -> dict[str, object]:
        return {
            "rail_class": self.rail_class,
            "locus": self.locus,
            "evasion": self.evasion,
            "depth": self.depth,
            "id": self.id,
        }


@lru_cache(maxsize=1)
def _rail_class_map() -> dict[str, str]:
    vocab = load_slots()
    out: dict[str, str] = {}
    for v in vocab.values["RAIL"]:
        rc = v.get("rail_class")
        if rc not in RAIL_CLASSES:
            raise ValueError(
                f"RAIL morpheme {v.id!r} declares rail_class {rc!r}, which is not one of the "
                f"six declared classes {RAIL_CLASSES}"
            )
        out[v.id] = str(rc)
    return out


@lru_cache(maxsize=1)
def _locus_map() -> dict[str, str]:
    vocab = load_slots()
    out: dict[str, str] = {}
    for v in vocab.values["ACCESS"]:
        loc = v.get("locus")
        if loc not in AUTHORISATION_LOCI:
            raise ValueError(
                f"ACCESS morpheme {v.id!r} declares locus {loc!r}, which is not one of the "
                f"four declared loci {AUTHORISATION_LOCI}"
            )
        out[v.id] = str(loc)
    return out


def rail_class_of(rail: str) -> str:
    return _rail_class_map()[rail]


def locus_of(access: str) -> str:
    return _locus_map()[access]


def nominal_cell_count() -> int:
    """576, computed. Never written as a literal outside tests."""
    return len(RAIL_CLASSES) * len(AUTHORISATION_LOCI) * len(load_slots().values["EVASION"]) * len(DEPTHS)


def all_cells() -> list[Cell]:
    evasions = load_slots().ids("EVASION")
    return [
        Cell(rc, loc, ev, d)
        for rc in RAIL_CLASSES
        for loc in AUTHORISATION_LOCI
        for ev in evasions
        for d in DEPTHS
    ]


def depth_of(stages: Sequence[str] | int | None) -> int:
    """KILL-CHAIN DEPTH from the plan.

    1 = single-stage; 2 = a pre-stage then monetisation; 3 = three or more stages
    (laundering / cash-out choreography). Clamped, because a nine-stage plan is still
    "multi-stage" and adding axis values to chase it would inflate the denominator.
    """
    if stages is None:
        raise ValueError(
            "depth requires the plan's stages; a grammar string alone does not determine its "
            "cell. This is the whole point of cell_of taking a plan."
        )
    n = stages if isinstance(stages, int) else len(stages)
    if n < 1:
        raise ValueError(f"a kill chain has at least one stage, got {n}")
    return min(int(n), max(DEPTHS))


def cell_of(comp: Composition, stages: Sequence[str] | int | None) -> Cell:
    """Project a (composition, plan) pair onto its archive cell."""
    return Cell(
        rail_class=rail_class_of(comp.RAIL),
        locus=locus_of(comp.ACCESS),
        evasion=comp.EVASION,
        depth=depth_of(stages),
    )


def admissible_depths(comp: Composition) -> tuple[int, ...]:
    """Which kill-chain depths this composition can actually be realised at.

    Authored from MONETISATION and RAIL semantics — `min_depth` on the MONETISATION morpheme,
    plus two structural rails that are two-stage by nature — and DELIBERATELY INDEPENDENT of
    grammar/feasible_cells.yaml. That independence is what makes the CI consistency test
    between the two a real test rather than a tautology: if the reachable set and the feasible
    set disagree, one of the two artifacts is wrong and `make grammar` says which cells.
    """
    vocab = load_slots()
    min_depth = int(vocab.get("MONETISATION", comp.MONETISATION).get("min_depth", 1))

    # Rails that carry an antecedent by construction, so they cannot be single-stage:
    #   card-clearing-dispute   — every presentment resolves to an authorisation (F1 invariant)
    #   card-token-provisioning — provisioning then first use is two events, not one
    #   upi-autopay-mandate     — a mandate must be created before it can be debited
    #   agentic-commerce        — same argument: the mandate object precedes its exercise
    if comp.RAIL in (
        "card-clearing-dispute",
        "card-token-provisioning",
        "upi-autopay-mandate",
        "agentic-commerce",
    ):
        min_depth = max(min_depth, 2)

    # Access routes that require a preparatory stage before any money moves:
    #   synthetic-identity      — the identity must be manufactured and onboarded first
    #   delegated-agent-mandate — the mandate must be delegated before it is exercised
    if comp.ACCESS in ("synthetic-identity", "delegated-agent-mandate"):
        min_depth = max(min_depth, 2)

    # Graph camouflage needs at least two hops to camouflage.
    if comp.EVASION == "graph-camouflage":
        min_depth = max(min_depth, 2)

    return tuple(d for d in DEPTHS if d >= min_depth)


def reachable_cells(comps: Iterable[Composition]) -> set[Cell]:
    """Every cell some type-legal composition can occupy at some admissible depth."""
    out: set[Cell] = set()
    for c in comps:
        rc, loc, ev = rail_class_of(c.RAIL), locus_of(c.ACCESS), c.EVASION
        for d in admissible_depths(c):
            out.add(Cell(rc, loc, ev, d))
    return out


# ---------------------------------------------------------------------------------------
# The mutation taxonomy, computed rather than asserted.
# ---------------------------------------------------------------------------------------

@dataclass(frozen=True)
class MutationEffect:
    slot: str
    from_value: str
    to_value: str
    cell_preserving: bool
    category: str          # "always-preserving" | "always-crossing" | "conditional"

    def describe(self) -> str:
        verb = "preserves" if self.cell_preserving else "crosses"
        return f"{self.slot}: {self.from_value} -> {self.to_value} ({verb} the cell, {self.category})"


def mutation_effect(
    before: Composition,
    after: Composition,
    stages: Sequence[str] | int,
) -> MutationEffect:
    """Classify a single-slot mutation. Raises unless exactly one slot differs."""
    diff = before.differing_slots(after)
    if len(diff) != 1:
        raise ValueError(
            f"mutation_effect classifies SINGLE-slot mutations (a sibling is hamming==1); "
            f"got {len(diff)} differing slots: {diff}"
        )
    slot = diff[0]
    same_cell = cell_of(before, stages) == cell_of(after, stages)
    if slot in CELL_PRESERVING_SLOTS:
        category = "always-preserving"
    elif slot in CELL_CROSSING_SLOTS:
        category = "always-crossing"
    else:
        category = "conditional"
    return MutationEffect(
        slot=slot,
        from_value=before.slot(slot),
        to_value=after.slot(slot),
        cell_preserving=same_cell,
        category=category,
    )


def projection_tables() -> dict[str, object]:
    """The tables `make archive-report` prints, so the projection is auditable on paper."""
    rc_map, loc_map = _rail_class_map(), _locus_map()
    rc_inverse: dict[str, list[str]] = {c: [] for c in RAIL_CLASSES}
    for rail, cls in sorted(rc_map.items()):
        rc_inverse[cls].append(rail)
    loc_inverse: dict[str, list[str]] = {c: [] for c in AUTHORISATION_LOCI}
    for access, loc in sorted(loc_map.items()):
        loc_inverse[loc].append(access)
    return {
        "rail_to_rail_class": dict(sorted(rc_map.items())),
        "rail_class_members": rc_inverse,
        "access_to_locus": dict(sorted(loc_map.items())),
        "locus_members": loc_inverse,
        "evasion_axis": "identity mapping — an EVASION mutation is always cell-crossing",
        "depth_source": "derived from the plan's stage count, NOT a grammar slot",
        "mutation_taxonomy": {
            "always_cell_preserving": sorted(CELL_PRESERVING_SLOTS),
            "always_cell_crossing": sorted(CELL_CROSSING_SLOTS),
            "conditional": sorted(CONDITIONAL_SLOTS),
        },
        "nominal_cells": nominal_cell_count(),
    }
