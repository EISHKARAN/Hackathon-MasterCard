"""Composition parsing and the slot vocabularies.

`Composition.parse()` is the ONLY parser for a grammar string. Nothing else in the repo may
split on "/" — a second parser is how a UI and a backend end up disagreeing about what a
judge typed, and Author-an-Attack is the one screen where that failure is visible on stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterator, Mapping

import yaml

from core.paths import paths

#: Canonical slot order. Fixed, and asserted against grammar/typing.yaml at load time.
SLOT_ORDER: tuple[str, ...] = ("ACCESS", "TRUST", "RAIL", "EVASION", "MONETISATION", "LABEL")

_SLOT_FILES: dict[str, str] = {
    "ACCESS": "access.yaml",
    "TRUST": "trust.yaml",
    "RAIL": "rail.yaml",
    "EVASION": "evasion.yaml",
    "MONETISATION": "monetisation.yaml",
    "LABEL": "label.yaml",
}


class CompositionError(ValueError):
    """Raised when a string is not a well-formed composition.

    Distinct from a type-check failure: a malformed string is a syntax error, a
    type-check failure is a semantic verdict with a reason a judge can read.
    """


@dataclass(frozen=True)
class SlotValue:
    """One morpheme, with the metadata the archive and the UI need."""

    slot: str
    id: str
    label: str
    description: str
    meta: Mapping[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        return self.meta.get(key, default)


@dataclass(frozen=True)
class SlotVocabulary:
    """All six slot vocabularies, loaded once from grammar/slots/*.yaml."""

    values: Mapping[str, tuple[SlotValue, ...]]

    def ids(self, slot: str) -> tuple[str, ...]:
        return tuple(v.id for v in self.values[slot])

    def get(self, slot: str, value_id: str) -> SlotValue:
        for v in self.values[slot]:
            if v.id == value_id:
                return v
        raise KeyError(
            f"{value_id!r} is not a declared {slot} morpheme; "
            f"declared: {sorted(self.ids(slot))}"
        )

    def counts(self) -> dict[str, int]:
        return {slot: len(vals) for slot, vals in self.values.items()}

    def raw_space_size(self) -> int:
        """The Cartesian product size. NOT a diversity claim; see grammar/typing.yaml."""
        n = 1
        for slot in SLOT_ORDER:
            n *= len(self.values[slot])
        return n


@lru_cache(maxsize=1)
def load_slots() -> SlotVocabulary:
    out: dict[str, tuple[SlotValue, ...]] = {}
    for slot, filename in _SLOT_FILES.items():
        path = paths.grammar / "slots" / filename
        with path.open("r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        if doc.get("slot") != slot:
            raise CompositionError(
                f"{path} declares slot {doc.get('slot')!r} but is loaded as {slot!r}"
            )
        parsed: list[SlotValue] = []
        seen: set[str] = set()
        for entry in doc["values"]:
            vid = entry["id"]
            if vid in seen:
                raise CompositionError(f"{path}: duplicate morpheme id {vid!r}")
            seen.add(vid)
            meta = {k: v for k, v in entry.items() if k not in ("id", "label", "description")}
            parsed.append(
                SlotValue(
                    slot=slot,
                    id=vid,
                    label=entry.get("label", vid),
                    description=(entry.get("description") or "").strip(),
                    meta=meta,
                )
            )
        declared = doc.get("count")
        if declared is not None and int(declared) != len(parsed):
            raise CompositionError(
                f"{path}: declares count {declared} but lists {len(parsed)} morphemes. "
                "The declared count is documentation; a mismatch means one of them is stale "
                "and every downstream arithmetic claim inherits the error."
            )
        out[slot] = tuple(parsed)
    return SlotVocabulary(values=out)


@dataclass(frozen=True, order=True)
class Composition:
    """A six-slot typed composition.

    Immutable and hashable, so it can be an archive key and a dict key without copying.
    """

    ACCESS: str
    TRUST: str
    RAIL: str
    EVASION: str
    MONETISATION: str
    LABEL: str

    # ---- construction ---------------------------------------------------------
    @classmethod
    def parse(cls, text: str) -> "Composition":
        """Parse `ACCESS=a/TRUST=t/RAIL=r/EVASION=e/MONETISATION=m/LABEL=l`.

        Strict on purpose: slot order must be canonical, every slot must be present
        exactly once, and every morpheme must exist in its vocabulary. A permissive parser
        here would let a typo silently become a different attack.
        """
        raw = (text or "").strip()
        if not raw:
            raise CompositionError("empty composition string")
        parts = [p.strip() for p in raw.split("/") if p.strip()]
        if len(parts) != len(SLOT_ORDER):
            raise CompositionError(
                f"expected {len(SLOT_ORDER)} slots separated by '/', got {len(parts)}: {raw!r}"
            )
        found: dict[str, str] = {}
        for i, part in enumerate(parts):
            if "=" not in part:
                raise CompositionError(f"slot {i} ({part!r}) is not of the form SLOT=value")
            slot, _, value = part.partition("=")
            slot, value = slot.strip().upper(), value.strip()
            if slot != SLOT_ORDER[i]:
                raise CompositionError(
                    f"slot order is canonical: position {i} must be {SLOT_ORDER[i]}, got {slot}"
                )
            if not value:
                raise CompositionError(f"slot {slot} has an empty value")
            found[slot] = value
        vocab = load_slots()
        for slot, value in found.items():
            vocab.get(slot, value)  # raises KeyError with the declared list
        return cls(**found)

    @classmethod
    def from_dict(cls, d: Mapping[str, str]) -> "Composition":
        missing = [s for s in SLOT_ORDER if s not in d]
        if missing:
            raise CompositionError(f"missing slots: {missing}")
        return cls.parse("/".join(f"{s}={d[s]}" for s in SLOT_ORDER))

    # ---- access ---------------------------------------------------------------
    def __str__(self) -> str:
        return "/".join(f"{slot}={getattr(self, slot)}" for slot in SLOT_ORDER)

    def as_dict(self) -> dict[str, str]:
        return {slot: getattr(self, slot) for slot in SLOT_ORDER}

    def slot(self, name: str) -> str:
        if name not in SLOT_ORDER:
            raise KeyError(f"{name!r} is not a slot; slots are {SLOT_ORDER}")
        return str(getattr(self, name))

    def morphemes(self) -> Iterator[SlotValue]:
        vocab = load_slots()
        for slot in SLOT_ORDER:
            yield vocab.get(slot, self.slot(slot))

    def with_slot(self, slot: str, value: str) -> "Composition":
        """A copy with one slot replaced — the mutation operator's primitive."""
        d = self.as_dict()
        d[slot] = value
        return Composition.from_dict(d)

    def differing_slots(self, other: "Composition") -> tuple[str, ...]:
        return tuple(s for s in SLOT_ORDER if self.slot(s) != other.slot(s))

    def hamming(self, other: "Composition") -> int:
        """Number of differing slots. A *sibling* is exactly hamming == 1."""
        return len(self.differing_slots(other))

    def declared_signatures(self) -> tuple[str, ...]:
        """Union of the `signatures` lists declared by this composition's morphemes.

        These are the fields the composition CLAIMS to move. The admission gate resolves
        every one of them against sim/schema.py, so a composition claiming a signature no
        observer can see is rejected rather than archived.
        """
        sigs: list[str] = []
        for morpheme in self.morphemes():
            for s in morpheme.get("signatures") or ():
                if s not in sigs:
                    sigs.append(s)
        return tuple(sigs)

    def tier(self) -> str:
        """Fidelity tier of the RAIL. 'B' means NO message-level fidelity claim."""
        return str(load_slots().get("RAIL", self.RAIL).get("tier", "B"))

    def has_beneficiary_leg(self) -> bool:
        return bool(load_slots().get("RAIL", self.RAIL).get("has_beneficiary_leg", False))

    def response_ladder(self) -> str:
        return str(load_slots().get("RAIL", self.RAIL).get("response_ladder", "decline_or_refer"))
