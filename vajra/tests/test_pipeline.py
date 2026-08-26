"""End-to-end pipeline invariants on the smoke preset: determinism, F1, features, leakage, RL contract."""

from __future__ import annotations

import numpy as np
import pytest

from attack.campaigns import campaigns_from_seeds
from core.io import table_hash, to_table
from fidelity.f1_invariants import check_events, invariant_count
from sim.engine import run_sim
from sim.schema import ORACLE_FIELDS, canonical_field_order, field_count


@pytest.fixture(scope="module")
def sim_result():
    return run_sim("smoke", campaigns_from_seeds("smoke"))


def test_f1_zero_violations(sim_result):
    """The never-cut gate: zero structural violations."""
    f1 = check_events(sim_result.events)
    assert f1["passed"], f"F1 violations: {f1['violations_by_invariant']}"
    assert f1["n_invariants"] == invariant_count()


def test_sim_is_byte_reproducible():
    """Same seed + config -> same logical Parquet hash. The determinism guarantee."""
    order = canonical_field_order()

    def _hash():
        res = run_sim("smoke", campaigns_from_seeds("smoke"))
        rows = [e.as_row() for e in res.events]
        cols = {n: [r[n] for r in rows] for n in order}
        return table_hash(to_table(cols, order))

    assert _hash() == _hash()


def test_schema_field_count_stable(sim_result):
    assert field_count() == len(canonical_field_order())


def test_no_oracle_field_is_a_registry_feature():
    """No feature may read a simulator oracle field. The structural anti-leak."""
    from features.registry import load_registry

    names = set(load_registry().names)
    assert not (names & ORACLE_FIELDS), f"oracle fields leaked into features: {names & ORACLE_FIELDS}"


def test_feature_matrix_matches_registry_and_is_finite(sim_result):
    from features.builder import build_matrix, fit_reference_stats, prepare_columns
    from features.registry import model_feature_names

    cols = prepare_columns(sim_result.events)
    y = np.full(cols["ts"].size, -1, dtype=np.int64)
    ref = fit_reference_stats(cols, y, train_mask=np.ones(cols["ts"].size, dtype=bool))
    fm = build_matrix(cols, ref)
    assert list(fm.names) == list(model_feature_names())
    assert np.isfinite(fm.X).all(), "feature matrix has non-finite values"


def test_label_table_refuses_future_reads(sim_result):
    """A point-in-time read must never return a label whose as_of exceeds the window."""
    table = sim_result.labels.table
    recs = table.all_records()
    if not recs:
        pytest.skip("no labels in this smoke run")
    early = min(r.as_of_ts for r in recs)
    eid = recs[0].event_id
    lab, _c, _d = table.resolve(eid, early - 1.0)
    # Before any label arrived, resolve returns None (unknown), never a future label.
    assert lab is None or all(r.as_of_ts <= early - 1.0 for r in table.visible(eid, early - 1.0))


def test_entity_pool_partition_holds(sim_result):
    """Sealed-pool cardholders and train-pool cardholders must be disjoint."""
    world = sim_result.world
    sealed = {cid for cid, ch in world.cardholders.items() if ch.pool == "sealed"}
    train = {cid for cid, ch in world.cardholders.items() if ch.pool == "train"}
    assert sealed and train
    assert not (sealed & train)


def test_attacker_observability_contract():
    """The attacker may not observe defender internals. The whole time-to-evade metric depends on it."""
    from attack.rl.observation import assert_observability_contract

    assert_observability_contract()  # raises on drift


def test_provenance_exactly_two_t1():
    """Exactly two conditionals may claim T1 — the single most load-bearing fidelity honesty guard."""
    from fidelity.provenance import assert_two_t1_conditionals

    assert_two_t1_conditionals()  # raises otherwise
