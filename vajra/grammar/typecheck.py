"""The type checker over grammar/typing.yaml.

A verdict is never a bare boolean. It carries the id and the human-readable reason of every
violated constraint, because:

*   the ARCHIVE and AUTHOR-AN-ATTACK screens render the reason when a judge's composition is
    rejected, so a rejection is an explanation rather than a red cross;
*   `make grammar` asserts every hand-authored row in grammar/seeds.yaml type-checks, and a
    failure has to say WHICH constraint the seed violates or the assertion is useless.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, Sequence

import yaml

from core.paths import paths
from grammar.composition import SLOT_ORDER, Composition, load_slots


@dataclass(frozen=True)
class Constraint:
    id: str
    kind: str          # "requires" | "forbids"
    when_slot: str
    when_value: str
    then_slot: str
    then_values: frozenset[str]
    reason: str

    def applies_to(self, comp: Composition) -> bool:
        return comp.slot(self.when_slot) == self.when_value

    def satisfied_by(self, comp: Composition) -> bool:
        if not self.applies_to(comp):
            return True
        actual = comp.slot(self.then_slot)
        if self.kind == "requires":
            return actual in self.then_values
        return actual not in self.then_values


@dataclass(frozen=True)
class TypeVerdict:
    ok: bool
    violations: tuple[tuple[str, str], ...] = field(default=())   # (constraint_id, reason)

    def explain(self) -> str:
        if self.ok:
            return "type-legal"
        return "; ".join(f"{cid}: {reason}" for cid, reason in self.violations)


class TypeChecker:
    def __init__(self, constraints: Sequence[Constraint]) -> None:
        self.constraints = tuple(constraints)
        # Index by the slot the antecedent tests, so checking a composition touches only the
        # constraints that could possibly apply. With ~40 constraints this is not a
        # performance need at one composition, but the enumerator evaluates 188,160 of them.
        self._by_when: dict[tuple[str, str], list[Constraint]] = {}
        for c in self.constraints:
            self._by_when.setdefault((c.when_slot, c.when_value), []).append(c)

    def check(self, comp: Composition) -> TypeVerdict:
        violations: list[tuple[str, str]] = []
        for slot in SLOT_ORDER:
            for c in self._by_when.get((slot, comp.slot(slot)), ()):
                if not c.satisfied_by(comp):
                    violations.append((c.id, c.reason))
        # Sort so a verdict is order-independent: tests/test_typecheck.py permutes the
        # constraint list and requires an identical verdict, which only holds if the
        # violation tuple is canonically ordered.
        violations.sort()
        return TypeVerdict(ok=not violations, violations=tuple(violations))

    def is_legal(self, comp: Composition) -> bool:
        return self.check(comp).ok

    def constraint(self, cid: str) -> Constraint:
        for c in self.constraints:
            if c.id == cid:
                return c
        raise KeyError(f"no constraint {cid!r}")

    def legal_values(self, comp: Composition, slot: str) -> tuple[str, ...]:
        """Which morphemes for `slot` keep `comp` type-legal.

        This is what drives the Author-an-Attack guided picker: the picker is constrained to
        type-valid combinations, so what a judge authors is a novel COMPOSITION within our
        grammar rather than an unbounded new idea — and the screen says exactly that bound,
        because overclaiming it is how the screen would backfire.
        """
        vocab = load_slots()
        return tuple(v for v in vocab.ids(slot) if self.is_legal(comp.with_slot(slot, v)))


def _parse_constraints(doc: dict) -> list[Constraint]:
    declared_order = tuple(doc.get("slot_order") or ())
    if declared_order and declared_order != SLOT_ORDER:
        raise ValueError(
            f"grammar/typing.yaml slot_order {declared_order} disagrees with the canonical "
            f"order {SLOT_ORDER}. The canonical order is fixed; a disagreement means every "
            f"grammar string in the repo parses differently than the matrix expects."
        )
    vocab = load_slots()
    out: list[Constraint] = []
    seen: set[str] = set()
    for entry in doc["constraints"]:
        cid = entry["id"]
        if cid in seen:
            raise ValueError(f"grammar/typing.yaml: duplicate constraint id {cid!r}")
        seen.add(cid)
        kind = entry["kind"]
        if kind not in ("requires", "forbids"):
            raise ValueError(f"{cid}: kind must be 'requires' or 'forbids', got {kind!r}")
        when, then = entry["when"], entry["then"]
        w_slot, w_val = when["slot"], when["value"]
        t_slot = then["slot"]
        t_vals = then.get("values")
        if t_vals is None:
            raise ValueError(f"{cid}: then.values is required")
        if w_slot == t_slot:
            raise ValueError(
                f"{cid}: antecedent and consequent are the same slot ({w_slot}). A constraint "
                f"within one slot is not a compatibility rule; remove the morpheme instead."
            )
        # Fail loudly on a stale morpheme reference. A silently-ignored constraint is worse
        # than a missing one: the count changes and no test notices.
        vocab.get(w_slot, w_val)
        for v in t_vals:
            vocab.get(t_slot, v)
        reason = " ".join((entry.get("reason") or "").split())
        if not reason:
            raise ValueError(
                f"{cid}: a constraint with no reason cannot be rendered to a judge and cannot "
                f"be audited. Every constraint must state its mechanism."
            )
        out.append(
            Constraint(
                id=cid,
                kind=kind,
                when_slot=w_slot,
                when_value=w_val,
                then_slot=t_slot,
                then_values=frozenset(t_vals),
                reason=reason,
            )
        )
    return out


@lru_cache(maxsize=1)
def load_typechecker() -> TypeChecker:
    with (paths.grammar / "typing.yaml").open("r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    return TypeChecker(_parse_constraints(doc))


def filter_legal(comps: Iterable[Composition]) -> list[Composition]:
    tc = load_typechecker()
    return [c for c in comps if tc.is_legal(c)]
