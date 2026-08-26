"""Signature resolution: taxonomy observable name -> schema field, registry feature, or design-only.

The archive admission criterion is ">= 3 observable signatures that must RESOLVE". This module is what
makes "resolve" a machine-checked predicate rather than an intention, and `make grammar` fails the build
on any name that resolves to nothing.

FOUR OUTCOMES, and the third is the one that earns its keep:
    schema        the observable IS a canonical schema field
    feature       the observable IS (or aliases to) a registry feature we compute
    design_only   the observable is REAL, belongs in the taxonomy, and WE DO NOT BUILD IT
    unknown       a drift between the taxonomy and the implementation -> BUILD FAILURE

Only `schema` and `feature` count toward the >= 3 criterion. A composition whose signatures are all
design-only cannot be archived, which is what stops the design-only tier from being a loophole.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable, Mapping, Sequence

import yaml

from core.paths import paths
from sim.schema import CANONICAL_FIELDS

RESOLVED_KINDS: frozenset[str] = frozenset({"schema", "feature"})


@dataclass(frozen=True)
class Resolution:
    name: str
    kind: str                # schema | feature | design_only | unknown
    target: str = ""
    reason: str = ""
    group: str = ""

    @property
    def resolved(self) -> bool:
        """Counts toward the >= 3 admission criterion."""
        return self.kind in RESOLVED_KINDS

    @property
    def design_only(self) -> bool:
        return self.kind == "design_only"

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "target": self.target,
            "reason": self.reason,
            "group": self.group,
            "counts_toward_admission": self.resolved,
        }


@dataclass(frozen=True)
class SignatureMap:
    aliases: Mapping[str, str]
    design_only: Mapping[str, Mapping[str, str]]
    version: int

    def groups(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for meta in self.design_only.values():
            g = str(meta.get("group", "ungrouped"))
            out[g] = out.get(g, 0) + 1
        return dict(sorted(out.items()))


@lru_cache(maxsize=1)
def load_signature_map() -> SignatureMap:
    path = paths.grammar / "signatures.yaml"
    with path.open("r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    aliases = {str(k): str(v) for k, v in (doc.get("aliases") or {}).items()}
    design: dict[str, dict[str, str]] = {}
    for k, v in (doc.get("design_only") or {}).items():
        meta = dict(v or {})
        reason = " ".join(str(meta.get("reason", "")).split())
        if not reason:
            raise ValueError(
                f"design-only signature {k!r} has no reason. A design-only declaration without a "
                f"reason is indistinguishable from an oversight, and this tier only earns its keep "
                f"because every entry says why."
            )
        design[str(k)] = {"reason": reason, "group": str(meta.get("group", "ungrouped"))}
    # An alias that is ALSO declared design-only is a contradiction: either we compute it or we do not.
    overlap = sorted(set(aliases) & set(design))
    if overlap:
        raise ValueError(
            f"signatures {overlap} are BOTH aliased to a computed column and declared design-only. "
            f"Exactly one must be true."
        )
    return SignatureMap(aliases=aliases, design_only=design, version=int(doc.get("version", 1)))


@lru_cache(maxsize=1)
def _feature_names() -> frozenset[str]:
    from features.registry import load_registry

    return frozenset(load_registry().names)


def resolve(name: str) -> Resolution:
    """Resolve one observable name. Never raises: the caller decides what an `unknown` means."""
    m = load_signature_map()
    n = str(name)

    if n in CANONICAL_FIELDS:
        return Resolution(n, "schema", target=n)
    if n in _feature_names():
        return Resolution(n, "feature", target=n)

    alias = m.aliases.get(n)
    if alias:
        if alias in CANONICAL_FIELDS:
            return Resolution(n, "schema", target=alias)
        if alias in _feature_names():
            return Resolution(n, "feature", target=alias)
        return Resolution(
            n, "unknown", target=alias,
            reason=(
                f"aliased to {alias!r}, which is itself neither a schema field nor a registry "
                f"feature. The alias target has drifted."
            ),
        )

    d = m.design_only.get(n)
    if d:
        return Resolution(n, "design_only", reason=d["reason"], group=d["group"])

    return Resolution(
        n, "unknown",
        reason=(
            "named in the taxonomy but resolves to nothing. Either add an alias in "
            "grammar/signatures.yaml pointing at the column that computes it, or declare it "
            "design_only with a reason."
        ),
    )


def resolve_all(names: Iterable[str]) -> list[Resolution]:
    return [resolve(n) for n in names]


def resolved_count(names: Iterable[str]) -> int:
    """How many of these signatures COUNT toward the >= 3 admission criterion."""
    return sum(1 for r in resolve_all(names) if r.resolved)


def partition(names: Iterable[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"schema": [], "feature": [], "design_only": [], "unknown": []}
    for r in resolve_all(names):
        out[r.kind].append(r.name)
    return out


def audit(all_names: Iterable[str]) -> dict[str, Any]:
    """The audit `make grammar` prints. An `unknown` fails the build."""
    names = sorted(set(all_names))
    res = resolve_all(names)
    unknown = [r for r in res if r.kind == "unknown"]
    m = load_signature_map()
    return {
        "n_distinct_signatures": len(names),
        "n_schema": sum(1 for r in res if r.kind == "schema"),
        "n_feature": sum(1 for r in res if r.kind == "feature"),
        "n_design_only": sum(1 for r in res if r.kind == "design_only"),
        "n_unknown": len(unknown),
        "unknown": [r.as_dict() for r in unknown],
        "design_only_by_group": m.groups(),
        "n_aliases": len(m.aliases),
        "policy": (
            "Only `schema` and `feature` count toward the >= 3 admission criterion. A composition "
            "whose signatures are ALL design-only cannot be archived, which is what stops the "
            "design-only tier from being a loophole. An `unknown` fails the build."
        ),
        "design_only_meaning": (
            "REAL observables that belong in the taxonomy and that we do not build. Every entry "
            "carries a reason, grouped by WHY: refused_by_policy (no deepfake / voice / document "
            "forensics / narrative embeddings, ever), outside_personae (held by nobody in GATE-I or "
            "GATE-B), consortium, ops_telemetry and loop_telemetry (measured as report series rather "
            "than as per-event features), tier_b_thin (no message-level fidelity claim), app_sdk, and "
            "mechanism_covered (the attack IS detectable through what we build; this exact statistic "
            "is not one of our columns)."
        ),
    }


def all_taxonomy_signatures() -> list[str]:
    """Every observable named anywhere in the taxonomy: slot vocabularies plus seed rows."""
    from grammar.composition import SLOT_ORDER, load_slots
    from grammar.seeds import load_seeds

    names: set[str] = set()
    vocab = load_slots()
    for slot in SLOT_ORDER:
        for v in vocab.values[slot]:
            names.update(str(s) for s in (v.get("signatures") or ()))
    for sd in load_seeds():
        names.update(sd.signatures)
        # Seeds' explicitly design-only lists are declared as such by the seed itself; still resolve
        # them so a typo there is caught too.
        names.update(sd.design_only_signals)
    return sorted(names)
