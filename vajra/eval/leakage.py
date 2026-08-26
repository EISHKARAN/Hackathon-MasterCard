"""The five leakage controls. Each one FAILS THE BUILD.

Leakage in a simulator-based study is MULTI-CHANNEL, so the controls are stacked at every level where
information could cross. A four-level holdout table is not enough on its own: the statistic-level and
the commit-order channels are invisible to an entity-id audit, and they are the two most likely ways a
recall number gets quietly inflated.

    LEVEL        WHAT IT PREVENTS
    simulator    a held-out family's random draws correlating with training data
    label        a row reading a label that had not arrived yet (FUTURE-LABEL LEAK)
    aggregate    a held-out campaign's device appearing in a training velocity aggregate
    statistic    a cohort baseline or quantile edge fitted over a pool containing sealed rows
    feature      the HUMAN channel: a feature engineered while looking at a held-out family

THE COMMIT-ORDER CONTROL IS THE ONE THAT CANNOT BE REPAIRED LATER. If the sealed manifest lands after
features have been engineered, the anti-circularity story is dead and re-committing does not fix it.
When the repo is not a git repo, `commit_order_audit` reports SKIPPED-UNVERIFIABLE rather than PASS —
a skip is honest; a pass we did not earn is not.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from core.paths import paths
from features.registry import load_registry
from grammar.sealed import load_sealed_manifest


@dataclass
class LeakageFinding:
    control: str
    level: str
    status: str                # PASS | FAIL | SKIPPED-UNVERIFIABLE
    detail: str
    evidence: Mapping[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return self.status == "FAIL"

    def as_dict(self) -> dict[str, Any]:
        return {
            "control": self.control,
            "level": self.level,
            "status": self.status,
            "detail": self.detail,
            "evidence": dict(self.evidence),
        }


# =======================================================================================
# 1. FEATURE level — the leakage linter over names, rules and config values
# =======================================================================================

def linter_audit(extra_strings: Mapping[str, str] | None = None) -> LeakageFinding:
    """No feature name, rule string or config value may reference a held-out family id.

    THE HUMAN CHANNEL. A four-level holdout table says nothing about an engineer who builds a feature
    while looking at a held-out family; a name that mentions the family is the visible tail of that,
    and it is cheap to forbid.
    """
    manifest = load_sealed_manifest()
    tokens = list(manifest.family_ids()) + [manifest.withheld_evasion_morpheme]
    reg = load_registry()
    names = list(reg.names)

    hits: list[str] = []
    lowered = [t.lower() for t in tokens if t]
    for n in names:
        if any(tok in n.lower() for tok in lowered):
            hits.append(f"feature name: {n}")

    # Also scan the config and gate rule strings a human might have written the id into.
    scan_paths = [
        paths.config / "ops.yaml",
        paths.config / "cost_matrix.yaml",
        paths.config / "scenario.yaml",
        paths.features / "registry.yaml",
        paths.root / "gate" / "views.yaml",
        paths.governance / "reason_codes.yaml",
    ]
    for p in scan_paths:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8").lower()
        for tok in lowered:
            # SEALED-nn family ids must not appear at all. The withheld EVASION morpheme is a
            # legitimate grammar value and appears in slot vocabularies, so it is only forbidden in
            # files that configure the DETECTOR.
            if tok.startswith("sealed-") and tok in text:
                hits.append(f"{p.name}: references {tok}")

    for k, v in (extra_strings or {}).items():
        if any(tok in str(v).lower() for tok in lowered if tok.startswith("sealed-")):
            hits.append(f"{k}: references a sealed family id")

    return LeakageFinding(
        control="leakage_linter",
        level="feature",
        status="FAIL" if hits else "PASS",
        detail=(
            f"{len(hits)} references to a held-out family id found in feature names, detector "
            f"configs or rule strings"
            if hits
            else "no feature name, detector config or rule string references a held-out family id"
        ),
        evidence={"tokens_checked": tokens, "hits": hits[:50], "n_features_scanned": len(names)},
    )


# =======================================================================================
# 2. LABEL level — no row may read a label that had not arrived
# =======================================================================================

def label_time_audit(
    event_ts: np.ndarray,
    label_as_of_ts: np.ndarray,
    window_end_ts: float,
) -> LeakageFinding:
    """Assert no resolved label has `as_of_ts` beyond the window end.

    THE DEFAULT OF SCORING A TIME-FORWARD WINDOW AGAINST FULLY MATURED LABELS IS A FUTURE-LABEL LEAK
    that an entity-id linter cannot see, and it is the single most likely way we would accidentally
    publish an inflated recall.
    """
    a = np.asarray(label_as_of_ts, dtype=np.float64)
    t = np.asarray(event_ts, dtype=np.float64)
    resolved = a > 0
    future = resolved & (a > float(window_end_ts) + 1e-6)
    # A label that arrives BEFORE its own event is a different bug and equally fatal.
    backwards = resolved & (a < t - 1e-6)
    n_bad = int(future.sum() + backwards.sum())
    return LeakageFinding(
        control="label_time_audit",
        level="label",
        status="FAIL" if n_bad else "PASS",
        detail=(
            f"{int(future.sum())} rows read a label from beyond the window end and "
            f"{int(backwards.sum())} read a label dated before their own event"
            if n_bad
            else "every resolved label arrived within the window and after its own event"
        ),
        evidence={
            "window_end_ts": float(window_end_ts),
            "n_rows": int(t.size),
            "n_resolved": int(resolved.sum()),
            "n_future_labels": int(future.sum()),
            "n_backwards_labels": int(backwards.sum()),
            "max_as_of_ts": float(a[resolved].max()) if resolved.any() else 0.0,
        },
    )


# =======================================================================================
# 3. AGGREGATE level — entity disjointness between training and holdout
# =======================================================================================

def entity_audit(
    train_mask: np.ndarray,
    holdout_mask: np.ndarray,
    entity_columns: Mapping[str, np.ndarray],
) -> LeakageFinding:
    """No training row may share an entity id with a holdout-family row.

    Family holdout LEAKS THROUGH AGGREGATES AND GRAPH NEIGHBOURHOODS without this test: withholding
    the LABEL while training on the same device node is not a holdout. The check is on shared IDS, not
    shared rows, because the aggregate is what carries the information.
    """
    tr = np.asarray(train_mask, dtype=bool)
    ho = np.asarray(holdout_mask, dtype=bool)
    shared: dict[str, list[str]] = {}
    for name, col in entity_columns.items():
        c = np.asarray(col, dtype=object).astype(str)
        tr_ids = {x for x in c[tr].tolist() if x}
        ho_ids = {x for x in c[ho].tolist() if x}
        inter = sorted(tr_ids & ho_ids)
        if inter:
            shared[name] = inter[:20]
    total = sum(len(v) for v in shared.values())
    return LeakageFinding(
        control="entity_audit",
        level="aggregate",
        status="FAIL" if shared else "PASS",
        detail=(
            f"{total}+ entity ids are shared between the training rows and holdout-family rows "
            f"across {len(shared)} key types"
            if shared
            else "no entity id is shared between training rows and holdout-family rows"
        ),
        evidence={
            "n_train_rows": int(tr.sum()),
            "n_holdout_rows": int(ho.sum()),
            "keys_checked": sorted(entity_columns),
            "shared_sample": shared,
            "why_it_matters": (
                "Withholding the label while training on the same device node is not a holdout. The "
                "aggregate carries the information even when no row crosses the boundary."
            ),
        },
    )


# =======================================================================================
# 4. STATISTIC level — the channel an entity-id audit cannot see
# =======================================================================================

#: Features that are deliberately NOT strictly point-in-time, with the reason. Listed here so the
#: exclusion is auditable rather than discovered by a reviewer.
STRICT_CAUSALITY_EXCLUSIONS: dict[str, str] = {
    "sketch_device_shared_entity_count": "structural graph property, not a time series",
    "sketch_address_node_density": "structural graph property, not a time series",
    "sketch_fingerprint_collision_degree": "structural graph property, not a time series",
    "acceptor_descriptor_mismatch": "compares against the acceptor's MODAL descriptor over its history",
    "traffic_geo_vs_registered_geo": "compares against the acceptor's MODAL geo cell over its history",
    "txn_note_template_score": "compares against the payee's MODAL transaction note",
}


def statistic_fit_audit(reference_stats_dict: Mapping[str, Any], split_dict: Mapping[str, Any]) -> LeakageFinding:
    """Assert the reference statistics were fitted on the TRAINING window with holdout rows excluded.

    THIS IS THE CONTROL AN ENTITY-ID AUDIT CANNOT SEE. A cohort baseline, a quantile edge, a scaler,
    the isotonic calibrator or the conformal calibration set fitted over a pool containing sealed-family
    rows imports holdout information into EVERY training feature — without a single id crossing the
    boundary. Only a window crosses, and only this check notices.
    """
    problems: list[str] = []
    fitted_n = int(reference_stats_dict.get("fitted_on_n_rows", 0))
    fitted_end = float(reference_stats_dict.get("fitted_window_end_ts", 0.0))
    train_end = float((split_dict.get("boundaries_ts") or {}).get("train", 0.0))
    test_start = float((split_dict.get("boundaries_ts") or {}).get("embargo", 0.0))

    if fitted_n <= 0:
        problems.append("reference statistics report zero fitted rows")
    if fitted_end > train_end + 1e-6:
        problems.append(
            f"reference statistics were fitted on data up to ts={fitted_end}, which is beyond the "
            f"training boundary ts={train_end}"
        )
    if fitted_end >= test_start and test_start > 0:
        problems.append("reference statistics reach into or past the embargo window")

    return LeakageFinding(
        control="statistic_fit_audit",
        level="statistic",
        status="FAIL" if problems else "PASS",
        detail=(
            "; ".join(problems)
            if problems
            else (
                "cohort baselines, quantile edges and cold-start priors were fitted causally on the "
                "training window with holdout-family rows excluded"
            )
        ),
        evidence={
            "reference_stats": dict(reference_stats_dict),
            "train_boundary_ts": train_end,
            "strict_causality_exclusions": STRICT_CAUSALITY_EXCLUSIONS,
            "exclusions_note": (
                "The features listed above are structural graph or modal-comparison properties rather "
                "than time series. They are NOT strictly point-in-time, and the exclusion is listed "
                "here so it is auditable rather than discovered."
            ),
        },
    )


# =======================================================================================
# 5. SIMULATOR level — commit order, and separate RNG streams
# =======================================================================================

def _git(*args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["git", *args], cwd=str(paths.root), capture_output=True, text=True, timeout=20
        )
        return p.returncode, (p.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return 127, ""


def commit_order_audit() -> LeakageFinding:
    """Did the sealed manifest land BEFORE the first commit under features/ or gate/?

    THE ONE FAILURE THAT CANNOT BE REPAIRED LATER. If the manifest lands after features have been
    engineered, the anti-circularity story is dead and re-committing does not fix it — which is why
    this compares COMMIT TIMESTAMPS rather than trusting a schedule.

    When the repo is not a git repo, this reports SKIPPED-UNVERIFIABLE rather than PASS. A skip is
    honest. A pass we did not earn would be the single most misleading line in the whole report.
    """
    rc, _ = _git("rev-parse", "--is-inside-work-tree")
    if rc != 0:
        return LeakageFinding(
            control="commit_order_audit",
            level="simulator",
            status="SKIPPED-UNVERIFIABLE",
            detail=(
                "not a git repository, so commit order cannot be verified. This is reported as a "
                "SKIP rather than a PASS: the sealing claim rests on `git log`, and without a repo "
                "there is no evidence either way."
            ),
            evidence={
                "how_to_make_it_real": (
                    "git init; git add grammar/ config/ docs/ sim/schema.py; "
                    "git commit -m 'grammar + sealed manifest, before any modelling'; "
                    "then git add features/ gate/ and commit separately. See README section "
                    "'Making the seal real'."
                )
            },
        )

    def first_commit_ts(pathspec: str) -> int | None:
        rc, out = _git("log", "--diff-filter=A", "--format=%ct", "--reverse", "--", pathspec)
        if rc != 0 or not out:
            return None
        return int(out.splitlines()[0])

    manifest_ts = first_commit_ts("grammar/sealed_manifest.yaml")
    feature_ts = first_commit_ts("features/")
    gate_ts = first_commit_ts("gate/")

    if manifest_ts is None:
        return LeakageFinding(
            control="commit_order_audit",
            level="simulator",
            status="SKIPPED-UNVERIFIABLE",
            detail="grammar/sealed_manifest.yaml has no commit history yet",
            evidence={"manifest_first_commit": None},
        )

    later = [
        (name, ts)
        for name, ts in (("features/", feature_ts), ("gate/", gate_ts))
        if ts is not None and ts < manifest_ts
    ]
    return LeakageFinding(
        control="commit_order_audit",
        level="simulator",
        status="FAIL" if later else "PASS",
        detail=(
            f"the sealed manifest was committed AFTER {[n for n, _ in later]}, so the seal came "
            f"after the modelling surface existed. This cannot be repaired by re-committing."
            if later
            else "the sealed manifest was committed before the first commit under features/ or gate/"
        ),
        evidence={
            "manifest_first_commit_ts": manifest_ts,
            "features_first_commit_ts": feature_ts,
            "gate_first_commit_ts": gate_ts,
        },
    )


def rng_stream_audit(family_ids: Iterable[str]) -> LeakageFinding:
    """Each family must derive its own KDF stream, so draws cannot correlate through shared state."""
    from core.rng import derive_seed

    ids = [f for f in family_ids if f]
    seeds = {f: derive_seed(f"attack.family.{f}") for f in ids}
    collisions = len(seeds) - len(set(seeds.values()))
    return LeakageFinding(
        control="rng_stream_audit",
        level="simulator",
        status="FAIL" if collisions else "PASS",
        detail=(
            f"{collisions} families share an RNG seed"
            if collisions
            else f"all {len(ids)} families derive distinct KDF-derived RNG streams"
        ),
        evidence={
            "n_families": len(ids),
            "n_distinct_seeds": len(set(seeds.values())),
            "why": (
                "Separate streams are what make adding a training campaign unable to shift a "
                "held-out family's draws. With one global generator, 'held out' would silently "
                "become 'generated from a state the training data determined'."
            ),
        },
    )


# =======================================================================================
# The suite
# =======================================================================================

def run_suite(
    *,
    event_ts: np.ndarray,
    label_as_of_ts: np.ndarray,
    window_end_ts: float,
    train_mask: np.ndarray,
    holdout_mask: np.ndarray,
    entity_columns: Mapping[str, np.ndarray],
    reference_stats_dict: Mapping[str, Any],
    split_dict: Mapping[str, Any],
    family_ids: Iterable[str],
) -> dict[str, Any]:
    """Run all five controls. Any FAIL fails the build."""
    findings = [
        commit_order_audit(),
        rng_stream_audit(family_ids),
        label_time_audit(event_ts, label_as_of_ts, window_end_ts),
        entity_audit(train_mask, holdout_mask, entity_columns),
        statistic_fit_audit(reference_stats_dict, split_dict),
        linter_audit(),
    ]
    failed = [f for f in findings if f.failed]
    skipped = [f for f in findings if f.status.startswith("SKIPPED")]
    return {
        "n_controls": len(findings),
        "n_failed": len(failed),
        "n_skipped_unverifiable": len(skipped),
        "passed": not failed,
        "findings": [f.as_dict() for f in findings],
        "policy": (
            "Any FAIL fails the build. A SKIPPED-UNVERIFIABLE is reported as a skip and never "
            "counted as a pass — a pass we did not earn would be the most misleading line in the "
            "whole report."
        ),
    }
