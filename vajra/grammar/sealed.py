"""The sealed-family holdout: loading, membership, and the audit.

Membership is by COMPOSITION IDENTITY. That is what makes "one morpheme different" well
defined, and it is why a sibling can be withheld from a retrain batch by identity rather than
by row.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable, Sequence

import yaml

from core.paths import paths
from grammar.cell_of import Cell, admissible_depths, cell_of
from grammar.composition import SLOT_ORDER, Composition
from grammar.enumerate_space import legal_compositions
from grammar.seeds import Seed, load_seeds


@dataclass(frozen=True)
class SealedFamily:
    id: str
    label: str
    pattern: tuple[tuple[str, str], ...]     # sorted (slot, value) pairs; hashable
    depth: int
    rationale: str
    related_seed: str | None = None

    def pattern_dict(self) -> dict[str, str]:
        return dict(self.pattern)

    def matches(self, comp: Composition) -> bool:
        return all(comp.slot(slot) == value for slot, value in self.pattern)

    @lru_cache(maxsize=None)
    def members(self) -> tuple[Composition, ...]:  # type: ignore[misc]
        """Every type-legal composition matching the pattern at an admissible depth.

        Cached per family: `legal_compositions()` is itself cached, but the pattern filter and
        the depth check over ~15k compositions run for every membership query otherwise, and
        `is_sealed` is called once per campaign.
        """
        out = [
            c
            for c in legal_compositions()
            if self.matches(c) and self.depth in admissible_depths(c)
        ]
        return tuple(sorted(out, key=str))

    def cells(self) -> tuple[Cell, ...]:
        return tuple(sorted({cell_of(c, self.depth) for c in self.members()}, key=lambda x: x.id))


@dataclass(frozen=True)
class SealedManifest:
    version: int
    families: tuple[SealedFamily, ...]
    withheld_evasion_morpheme: str
    withheld_rationale: str
    content_hash: str
    frozen_across_evaluation: tuple[str, ...]
    retrained_per_tick: tuple[str, ...]

    def family(self, fid: str) -> SealedFamily:
        for f in self.families:
            if f.id == fid:
                return f
        raise KeyError(f"no sealed family {fid!r}")

    def family_ids(self) -> tuple[str, ...]:
        return tuple(f.id for f in self.families)

    # ---- membership predicates -------------------------------------------------
    @lru_cache(maxsize=1)
    def sealed_compositions(self) -> frozenset[str]:  # type: ignore[misc]
        """Every composition string withheld by family membership (NOT the LOO morpheme)."""
        out: set[str] = set()
        for f in self.families:
            out.update(str(c) for c in f.members())
        return frozenset(out)

    def is_withheld_morpheme(self, comp: Composition) -> bool:
        return comp.EVASION == self.withheld_evasion_morpheme

    def is_sealed(self, comp: Composition, *, include_morpheme_arm: bool = True) -> bool:
        """Is this composition withheld from training?

        `include_morpheme_arm=True` is the default because the leave-one-morpheme-out arm is a
        strictly stronger holdout: a training set that contains the withheld morpheme has
        invalidated that arm, and there is no version of the run where that is acceptable.
        """
        if include_morpheme_arm and self.is_withheld_morpheme(comp):
            return True
        return str(comp) in self.sealed_compositions()

    def family_of(self, comp: Composition) -> str | None:
        for f in self.families:
            if f.matches(comp):
                return f.id
        return None

    def holdout_reason(self, comp: Composition) -> str | None:
        if self.is_withheld_morpheme(comp):
            return f"leave-one-morpheme-out: EVASION={self.withheld_evasion_morpheme}"
        fid = self.family_of(comp)
        if fid and str(comp) in self.sealed_compositions():
            return f"sealed family {fid}"
        return None


def _one_line(s: str | None) -> str:
    return " ".join((s or "").split())


@lru_cache(maxsize=1)
def load_sealed_manifest() -> SealedManifest:
    path = paths.grammar / "sealed_manifest.yaml"
    raw = path.read_bytes()
    with path.open("r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    from grammar.composition import load_slots

    vocab = load_slots()
    families: list[SealedFamily] = []
    seen: set[str] = set()
    for entry in doc["families"]:
        fid = entry["id"]
        if fid in seen:
            raise ValueError(f"sealed_manifest.yaml: duplicate family id {fid!r}")
        seen.add(fid)
        pattern_raw = entry.get("pattern") or {}
        if not pattern_raw:
            raise ValueError(f"{fid}: an empty pattern would seal the entire grammar")
        bad = [k for k in pattern_raw if k not in SLOT_ORDER]
        if bad:
            raise ValueError(f"{fid}: unknown pattern slots {bad}; slots are {SLOT_ORDER}")
        for slot, value in pattern_raw.items():
            vocab.get(slot, value)
        families.append(
            SealedFamily(
                id=fid,
                label=_one_line(entry.get("label")),
                pattern=tuple(sorted((str(k), str(v)) for k, v in pattern_raw.items())),
                depth=int(entry["depth"]),
                rationale=_one_line(entry.get("rationale")),
                related_seed=entry.get("related_seed"),
            )
        )

    loo = doc["leave_one_evasion_morpheme_out"]
    morpheme = str(loo["morpheme"])
    vocab.get("EVASION", morpheme)

    return SealedManifest(
        version=int(doc.get("manifest_version", 1)),
        families=tuple(families),
        withheld_evasion_morpheme=morpheme,
        withheld_rationale=_one_line(loo.get("rationale")),
        content_hash=hashlib.sha256(raw).hexdigest(),
        frozen_across_evaluation=tuple(
            _one_line(x) for x in (doc.get("frozen_across_evaluation") or [])
        ),
        retrained_per_tick=tuple(_one_line(x) for x in (doc.get("retrained_per_tick") or [])),
    )


def sealed_audit(
    manifest: SealedManifest | None = None,
    seeds: Sequence[Seed] | None = None,
) -> dict[str, Any]:
    """The audit `make grammar` prints and writes to reports/sealed_audit.json."""
    m = manifest or load_sealed_manifest()
    seed_list = tuple(seeds if seeds is not None else load_seeds())

    problems: list[str] = []
    per_family: list[dict[str, Any]] = []
    all_members: set[str] = set()
    all_cells: set[str] = set()

    for f in m.families:
        members = f.members()
        if not members:
            problems.append(
                f"{f.id} has ZERO type-legal members at depth {f.depth}. A family that seals "
                f"nothing is a holdout claim with no holdout behind it: pattern="
                f"{f.pattern_dict()}."
            )
        cells = f.cells()
        # A family whose pattern does not pin EVASION spans several cells; that is allowed, but
        # it must be visible, because sibling construction depends on knowing the cell.
        all_members.update(str(c) for c in members)
        all_cells.update(c.id for c in cells)
        if f.related_seed and f.related_seed not in {s.id for s in seed_list}:
            problems.append(f"{f.id} names related_seed {f.related_seed!r}, which is not a seed id")
        per_family.append(
            {
                "id": f.id,
                "label": f.label,
                "pattern": f.pattern_dict(),
                "depth": f.depth,
                "n_members": len(members),
                "cells": [c.id for c in cells],
                "related_seed": f.related_seed,
                "rationale": f.rationale,
            }
        )

    # The withheld morpheme must actually be used by some seeds, or the arm is a free win.
    seeds_using_morpheme = [
        s.id for s in seed_list if s.composition.EVASION == m.withheld_evasion_morpheme
    ]
    if not seeds_using_morpheme:
        problems.append(
            f"the leave-one-morpheme-out arm withholds EVASION={m.withheld_evasion_morpheme}, "
            f"but NO shipped seed uses it. Withholding a morpheme nothing depends on costs us "
            f"no training signal and is therefore not a holdout -- it is a free win."
        )

    # Sealed seeds: which hand-authored rows fall inside a sealed family or the LOO arm.
    sealed_seeds = [s.id for s in seed_list if m.is_sealed(s.composition)]
    if not sealed_seeds:
        problems.append(
            "no hand-authored seed is sealed. If the holdout intersects none of the table, the "
            "sealed result cannot be read against any row a judge can see."
        )

    all_legal = legal_compositions()
    n_legal_total = len(all_legal)
    morpheme_withheld = {str(c) for c in all_legal if m.is_withheld_morpheme(c)}
    morpheme_withheld_count = len(morpheme_withheld)

    return {
        "manifest_version": m.version,
        "manifest_sha256": m.content_hash,
        "n_families": len(m.families),
        "n_compositions": len(all_members),
        "n_cells": len(all_cells),
        "families": per_family,
        "loo_evasion_morphemes": m.withheld_evasion_morpheme,
        "loo_seeds_affected": seeds_using_morpheme,
        "loo_compositions_withheld": morpheme_withheld_count,
        "sealed_seeds": sealed_seeds,
        "type_legal_total": n_legal_total,
        "share_of_space_withheld": (
            round(len(all_members | morpheme_withheld) / n_legal_total, 4)
            if n_legal_total
            else 0.0
        ),
        "problems": problems,
        "frozen_across_evaluation": list(m.frozen_across_evaluation),
        "retrained_per_tick": list(m.retrained_per_tick),
    }


def partition_training(comps: Iterable[Composition]) -> tuple[list[Composition], list[Composition]]:
    """Split compositions into (trainable, withheld). The one function training must call."""
    m = load_sealed_manifest()
    trainable: list[Composition] = []
    withheld: list[Composition] = []
    for c in comps:
        (withheld if m.is_sealed(c) else trainable).append(c)
    return trainable, withheld
