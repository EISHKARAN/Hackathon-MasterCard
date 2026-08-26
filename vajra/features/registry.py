"""The feature registry: expansion, lineage, and view masking.

`features/registry.yaml` declares FAMILIES. This module expands them into named features and
reports the MACHINE-COUNTED total. The design's "~380" is a planned budget, and what ships is
whatever the registry actually contains.

Three things only this module may decide:

*   **The model matrix.** `model_feature_names()` excludes `audit_only` fields. A model that
    consumes label-channel disagreement is consuming the label, and a model that consumes the
    incumbent's accept PROBABILITY is consuming the propensity that the reject-inference estimator
    is supposed to correct with.
*   **View masking.** `features_for_view()` is what makes the single-institution visibility
    ablation a real ablation: an acquirer genuinely cannot construct PAN-canonical aggregation
    because it does not hold the token-to-PAN map, so those features are ABSENT rather than zeroed.
*   **Feature order.** Fixed and derived from the registry, because LightGBM's byte-identical
    artifact guarantee requires a fixed feature order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable, Mapping, Sequence

import yaml

from core.paths import paths
from sim.schema import ORACLE_FIELDS, OUT_OF_PERSONA_FIELDS, RAILS

#: The deployment views declared in gate/views.yaml. Fixed here so the registry and the views
#: file cannot drift apart silently; the consistency test lives in tests/test_views.py.
VIEWS: tuple[str, ...] = ("issuer", "acquirer", "payee_psp", "network")


@dataclass(frozen=True)
class Feature:
    name: str
    family: str
    dtype: str
    lineage: str
    views: frozenset[str]
    catches: str
    audit_only: bool = False
    #: For expanded families: which axis values produced this feature.
    axis: Mapping[str, str] = field(default_factory=dict, compare=False)

    def available_in(self, view: str) -> bool:
        return view in self.views


@dataclass(frozen=True)
class Registry:
    features: tuple[Feature, ...]
    audit_only_names: frozenset[str]
    protected_attribute_policy: Mapping[str, str]
    version: int

    # ---- counts ----------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self.features)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.features)

    def model_feature_names(self) -> tuple[str, ...]:
        """The matrix the model actually sees. Audit-only fields excluded."""
        return tuple(f.name for f in self.features if not f.audit_only)

    def audit_feature_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.features if f.audit_only)

    def get(self, name: str) -> Feature:
        for f in self.features:
            if f.name == name:
                return f
        raise KeyError(f"no registry feature {name!r}")

    def by_family(self) -> dict[str, list[Feature]]:
        out: dict[str, list[Feature]] = {}
        for f in self.features:
            out.setdefault(f.family, []).append(f)
        return out

    def family_counts(self) -> dict[str, int]:
        return {k: len(v) for k, v in sorted(self.by_family().items())}

    # ---- view masking -----------------------------------------------------------------
    def features_for_view(self, view: str) -> tuple[str, ...]:
        """Feature names constructible at a deployment view.

        ABSENT, not zeroed. Zeroing would tell the model "this entity has no token fan-out",
        which is a different and false statement from "this institution cannot see token
        fan-out" — and it would make the ablation measure the wrong thing.
        """
        if view not in VIEWS:
            raise KeyError(f"unknown view {view!r}; declared views are {VIEWS}")
        return tuple(f.name for f in self.features if not f.audit_only and f.available_in(view))

    def view_coverage(self) -> dict[str, dict[str, object]]:
        total = len(self.model_feature_names())
        out: dict[str, dict[str, object]] = {}
        for v in VIEWS:
            n = len(self.features_for_view(v))
            out[v] = {
                "n_features": n,
                "share_of_full": round(n / total, 4) if total else 0.0,
                "missing": total - n,
            }
        return out

    def report(self) -> dict[str, object]:
        return {
            "version": self.version,
            "n_features_total": len(self.features),
            "n_features_in_model_matrix": len(self.model_feature_names()),
            "n_audit_only": len(self.audit_feature_names()),
            "features_per_family": self.family_counts(),
            "view_coverage": self.view_coverage(),
            "audit_only": sorted(self.audit_only_names),
            "protected_attribute_policy": dict(self.protected_attribute_policy),
            "note": (
                "This count is MACHINE-COUNTED from features/registry.yaml. The design's ~380 is "
                "a planned budget; what ships is whatever this prints."
            ),
        }


def _one_line(s: Any) -> str:
    return " ".join(str(s or "").split())


def _expand(
    family: dict[str, Any],
    axes: dict[str, Any],
    audit_only: frozenset[str],
) -> list[Feature]:
    """Expand one family into named features."""
    fid = family["id"]
    lineage = _one_line(family.get("lineage"))
    catches = _one_line(family.get("catches"))
    if not catches:
        raise ValueError(
            f"family {fid!r} names no attack mechanism in `catches`. A feature with no named "
            f"mechanism is decoration, and the registry is where that has to be caught."
        )
    dtype = str(family.get("dtype", "float"))
    default_views = frozenset(family.get("views") or VIEWS)

    out: list[Feature] = []

    # --- explicitly listed features ---------------------------------------------------
    _ENTRY_KEYS = {"name", "lineage", "views"}
    for entry in family.get("features") or []:
        name = entry["name"]
        # A PER-FEATURE `views:` MUST BE HONOURED. This previously passed `default_views`
        # unconditionally, so a per-feature restriction declared in the YAML was silently dropped and
        # the feature became visible at every view. That is the one kind of bug the visibility
        # ablation cannot survive: it would report an institution constructing a feature it provably
        # cannot see, and nothing would fail. Not hypothetical -- `thin_rail_observables` declares
        # per-feature views because an acquirer cannot observe the payer's core-banking posting lag.
        entry_views = entry.get("views")
        if entry_views is not None:
            unknown = sorted(set(map(str, entry_views)) - set(VIEWS))
            if unknown:
                raise ValueError(
                    f"feature {name!r} in family {fid!r} declares unknown view(s) {unknown}; "
                    f"declared views are {list(VIEWS)}"
                )
        # An unrecognised key is a typo, and a typo in a `views` restriction fails OPEN -- the
        # feature would quietly become available everywhere. Refuse instead.
        stray = sorted(set(entry) - _ENTRY_KEYS)
        if stray:
            raise ValueError(
                f"feature {name!r} in family {fid!r} has unrecognised key(s) {stray}. Expected "
                f"{sorted(_ENTRY_KEYS)}. Refused rather than ignored, because an ignored `views` "
                f"typo silently widens what a deployment view can construct."
            )
        out.append(
            Feature(
                name=name,
                family=fid,
                dtype=dtype,
                lineage=_one_line(entry.get("lineage")) or lineage,
                views=frozenset(map(str, entry_views)) if entry_views else default_views,
                catches=catches,
                audit_only=name in audit_only,
            )
        )

    # --- cross-product expansions ------------------------------------------------------
    spec = family.get("expand")
    if not spec:
        return out
    template = family.get("name_template")
    if not template:
        raise ValueError(f"family {fid!r} declares `expand` but no `name_template`")
    parts = [p.strip() for p in str(spec).split("x")]

    if parts == ["rails"]:
        for rail in RAILS:
            out.append(
                Feature(
                    name=template.format(rail=rail.replace("-", "_")),
                    family=fid,
                    dtype=dtype,
                    lineage=lineage,
                    views=default_views,
                    catches=catches,
                    axis={"rail": rail},
                )
            )
        return out

    keys = axes["entity_keys"]
    windows = [str(w) for w in axes["windows"]]
    per_key_views = bool(family.get("per_key_views", False))

    if parts == ["entity_keys", "windows"]:
        for k in keys:
            kv = frozenset(k["views"]) if per_key_views else default_views
            for w in windows:
                out.append(
                    Feature(
                        name=template.format(key=k["name"], window=w),
                        family=fid,
                        dtype=dtype,
                        lineage=lineage,
                        views=kv,
                        catches=catches,
                        axis={"key": k["name"], "window": w},
                    )
                )
        return out

    if parts == ["entity_keys", "windows", "velocity_stats", "velocity_encodings"]:
        stats = [str(s) for s in axes["velocity_stats"]]
        encs = [str(e) for e in axes["velocity_encodings"]]
        for k in keys:
            kv = frozenset(k["views"]) if per_key_views else default_views
            for w in windows:
                for st in stats:
                    for en in encs:
                        out.append(
                            Feature(
                                name=template.format(key=k["name"], window=w, stat=st, encoding=en),
                                family=fid,
                                dtype=dtype,
                                lineage=lineage,
                                views=kv,
                                catches=catches,
                                axis={"key": k["name"], "window": w, "stat": st, "encoding": en},
                            )
                        )
        return out

    raise ValueError(
        f"family {fid!r} declares an unsupported expansion {spec!r}. Supported: 'rails', "
        f"'entity_keys x windows', 'entity_keys x windows x velocity_stats x velocity_encodings'."
    )


@lru_cache(maxsize=1)
def load_registry() -> Registry:
    with (paths.features / "registry.yaml").open("r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    audit_only = frozenset(doc.get("audit_only") or ())
    axes = doc.get("axes") or {}

    features: list[Feature] = []
    seen: set[str] = set()
    for family in doc["families"]:
        for f in _expand(family, axes, audit_only):
            if f.name in seen:
                raise ValueError(
                    f"duplicate feature name {f.name!r} (family {f.family!r}). A duplicate would "
                    f"silently collapse two features into one column and no downstream test could "
                    f"attribute the loss."
                )
            seen.add(f.name)
            features.append(f)

    # RULE 1: no feature may read an oracle field.
    oracle_collisions = sorted(seen & ORACLE_FIELDS)
    if oracle_collisions:
        raise ValueError(
            f"features {oracle_collisions} share a name with a simulator ORACLE field. Oracle "
            f"fields are ground truth for the evaluation harness only; a feature named after one "
            f"is a leak waiting to happen."
        )

    # Out-of-persona schema fields must not appear as model features.
    persona_collisions = sorted(seen & OUT_OF_PERSONA_FIELDS)
    if persona_collisions:
        raise ValueError(
            f"features {persona_collisions} are OUT_OF_PERSONA schema fields (app-SDK, "
            f"acquirer-underwriting or bureau). They stay in the schema because the observables "
            f"are real, but they are excluded from every scored result and must not be registry "
            f"features."
        )

    # `never_features` must be ABSENT. This is the check that makes a future well-meaning change
    # ("the propensity is informative, let's add it") fail the build instead of leaking silently.
    never = frozenset(doc.get("never_features") or ())
    never_collisions = sorted(seen & never)
    if never_collisions:
        raise ValueError(
            f"features {never_collisions} are listed under `never_features` in "
            f"features/registry.yaml and must not be computed as features. See the comments there "
            f"for why each one is excluded — the propensity case in particular turns a "
            f"selection-bias correction into a leak."
        )

    # `audit_only` names must EXIST as declared features, or the exclusion is aspirational.
    missing_audit = sorted(audit_only - seen)
    if missing_audit:
        raise ValueError(
            f"`audit_only` names {missing_audit} are not declared features. audit_only means "
            f"'computed and exported, but not a model column'. A name that is not computed at all "
            f"belongs under `never_features`."
        )

    return Registry(
        features=tuple(features),
        audit_only_names=audit_only,
        protected_attribute_policy={
            k: _one_line(v) for k, v in (doc.get("protected_attribute_policy") or {}).items()
        },
        version=int(doc.get("version", 1)),
    )


def feature_count() -> int:
    """Machine-counted. Printed by `make train`; never a literal."""
    return len(load_registry())


def model_feature_names() -> tuple[str, ...]:
    return load_registry().model_feature_names()


def lineage_table() -> list[dict[str, object]]:
    """The lineage export for governance/ and the UI's feature inspector."""
    return [
        {
            "name": f.name,
            "family": f.family,
            "dtype": f.dtype,
            "lineage": f.lineage,
            "catches": f.catches,
            "views": sorted(f.views),
            "audit_only": f.audit_only,
        }
        for f in load_registry().features
    ]


def assert_no_holdout_reference(names: Iterable[str], holdout_tokens: Sequence[str]) -> list[str]:
    """The leakage linter's core check: no feature name references a held-out family id.

    Returns the offending names. Called by eval/leakage/linter.py over feature names, rule
    strings and config values — the human channel that a four-level holdout table does not close.
    """
    lowered = [t.lower() for t in holdout_tokens if t]
    hits: list[str] = []
    for n in names:
        ln = n.lower()
        if any(tok in ln for tok in lowered):
            hits.append(n)
    return hits
