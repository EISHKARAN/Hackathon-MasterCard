"""No scored feature may be populated ONLY on attack rows.

THE BUG CLASS THIS EXISTS TO KILL. `sim/rails/a2a.py` set `beneficiary_change_ts` inside
`if attack and evasion in ("trust-inheritance", "low-visibility-rail")` and nowhere else. The schema
default is the -1 sentinel, so the derived feature
`beneficiary_change_within_cooling_hours` was -1 on EVERY benign row in the corpus and a real number
on a subset of attack rows. Any tree splits it at zero and gets 100% precision on that
subpopulation. That is not detection; it is the generator handing the model the answer.

WHY THE EXISTING GUARDS MISS IT. `tests/test_no_oracle_in_features.py` checks that no feature READS
an oracle field, and `eval/leakage.py::leakage_linter` checks that no feature NAME references a
held-out family. Neither notices a legitimately-named, legitimately-sourced feature whose SUPPORT
happens to be attack-only. The leak is in the joint distribution, not in the lineage.

WHY A SMOKE RUN IS NOT ENOUGH. The offending field produced ZERO rows at the smoke preset, because
no a2a campaign carrying those evasion morphemes was sampled among 24 campaigns. It would have gone
live at the full preset with 1600. So this test builds a campaign set covering EVERY seed family,
which is what makes the check meaningful at CI scale.

A one-sided sentinel is the only thing asserted here. Features that are merely CORRELATED with attacks
are the entire point of the system and are not flagged.
"""

from __future__ import annotations

import numpy as np
import pytest

from attack.campaigns import campaigns_from_seeds
from features.builder import build_matrix, fit_reference_stats, prepare_columns
from features.registry import load_registry
from grammar.seeds import load_seeds
from sim.engine import run_sim

#: Features whose sentinel-only-on-benign shape is STRUCTURAL rather than a leak, each with a reason.
#: Kept deliberately short; an entry here is a claim that needs justifying, not a mute button.
ALLOWED: dict[str, str] = {}


@pytest.fixture(scope="module")
def matrix():
    """A smoke world, but with campaigns covering EVERY seed family."""
    seeds = load_seeds()
    campaigns = campaigns_from_seeds("smoke")
    # campaigns_from_seeds cycles the seed list, so ask for at least one campaign per family.
    if len({c.family_id for c in campaigns}) < len(seeds):
        from attack.campaigns import campaigns_from_seeds as _c

        campaigns = _c("small")  # 420 campaigns over 51 families, but run on the smoke world
    res = run_sim("smoke", campaigns)
    cols = prepare_columns(res.events)
    y = np.full(cols["ts"].size, -1, dtype=np.int64)
    ref = fit_reference_stats(cols, y, train_mask=np.ones(cols["ts"].size, dtype=bool))
    fm = build_matrix(cols, ref)
    attack = np.asarray(cols["oracle_is_attack"], dtype=bool)
    return fm, attack


def test_no_feature_is_populated_only_on_attack_rows(matrix):
    fm, attack = matrix
    if attack.sum() == 0:
        pytest.skip("no attack rows generated; the check would be vacuous")
    reg = load_registry()
    model_names = set(reg.model_feature_names())

    offenders: list[dict[str, object]] = []
    for j, name in enumerate(fm.names):
        if name not in model_names or name in ALLOWED:
            continue
        col = fm.X[:, j].astype(np.float64)
        # "Populated" = not the sentinel. A feature populated on some attack rows and NO benign row
        # is a one-sided perfect separator.
        populated = col > -1.0
        n_attack_pop = int((populated & attack).sum())
        n_benign_pop = int((populated & ~attack).sum())
        if n_attack_pop > 0 and n_benign_pop == 0:
            offenders.append(
                {
                    "feature": name,
                    "attack_rows_populated": n_attack_pop,
                    "benign_rows_populated": 0,
                    "precision_of_trivial_rule": 1.0,
                }
            )

    assert not offenders, (
        "these scored features are populated ONLY on attack rows, so a single threshold at the "
        "sentinel separates them perfectly — the generator is handing the model the answer:\n"
        + "\n".join(
            f"  {o['feature']}: {o['attack_rows_populated']} attack rows, 0 benign rows" for o in offenders
        )
        + "\nFix the GENERATOR (give the field a realistic benign population), not this test."
    )
