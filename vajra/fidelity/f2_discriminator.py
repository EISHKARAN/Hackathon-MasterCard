"""F2 — the comparative real-vs-synthetic discriminator.

============================ WHY THE DISCRIMINATOR IS OUT OF THE LOOP ===================
The tempting design puts the realism critic INSIDE the attacker's reward. Both reviewing judges
flagged it as fatal and they are right: optimising against a learned critic on a few thousand samples
produces compositions that score realistic TO THAT CRITIC while drifting away from payment legality in
dimensions the critic never learned, and a low AUC then becomes a statement about how well the
generator gamed its own judge -- the failure mode of every GAN fidelity claim.

So the discriminator is a FROZEN, VERSIONED AUDITOR used at EVALUATION TIME ONLY. F1's hand-written
invariants are the fidelity mechanism inside the loop, because an invariant is not gameable by
gradient, only satisfiable or violated.
========================================================================================

THE COMPARATIVE FRAMING carries the value, and it needs TWO things bolted on:

1.  DEMONSTRATED POWER. A low AUC is otherwise indistinguishable from a subspace too narrow to
    discriminate. So a POSITIVE CONTROL -- a marginal-independent shuffled sampler built from our own
    rows -- must be separated at AUC >= 0.90. If the control fails, NO F2 NUMBER IS REPORTED AT ALL.

2.  A PRE-COMMITTED INTERPRETATION, because we may lose the aligned subspace and should not pretend
    otherwise. CTGAN fitted to the same projection is directly optimising those marginals, so on the
    ALIGNED subspace it SHOULD be hard to separate -- possibly harder than us -- and treating "CTGAN
    beats us there" as a red gate would be losing on the wrong axis. So F2 reports two subspaces: the
    ALIGNED marginal subspace (CTGAN expected competitive, we say so in advance) and a STRUCTURE
    subspace (lifecycle pairing, graph, value conservation) where a row-wise tabular generator has
    nothing to fit and cannot compete. The claim we defend is the PAIR, not a single AUC.

CTGAN/PaySim/Sparkov are OPTIONAL. When absent, F2 reports the control and the ours-vs-real number and
records the missing arms as SKIPPED-DEPENDENCY-ABSENT rather than fabricating them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

from core.rng import stream
from eval.metrics import roc_auc

#: The positive-control power floor. Below this, the harness has no demonstrated power and no F2
#: number is reported.
POWER_FLOOR_AUC = 0.90


@dataclass
class F2Result:
    subspace: str
    ours_vs_real_auc: float
    positive_control_auc: float
    power_ok: bool
    control_arms: dict[str, float]
    n_real: int
    n_synth: int
    columns: tuple[str, ...]
    reportable: bool
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "subspace": self.subspace,
            "ours_vs_real_auc": self.ours_vs_real_auc if self.reportable else None,
            "positive_control_auc": self.positive_control_auc,
            "power_ok": self.power_ok,
            "power_floor": POWER_FLOOR_AUC,
            "control_arms": self.control_arms,
            "n_real": self.n_real,
            "n_synth": self.n_synth,
            "n_columns": len(self.columns),
            "reportable": self.reportable,
            "note": self.note,
        }


def _lightgbm_auc(X_pos: np.ndarray, X_neg: np.ndarray, *, seed: int = 20260909) -> float:
    """Train a frozen, versioned LightGBM to separate two row sets; return held-out AUC.

    A held-out AUC, on a time-agnostic random split, because the QUESTION here is "are these two row
    sets distinguishable at all" rather than "does a model generalise forward" -- this is the one
    place a random split is the correct tool, and saying so is the difference between using it and
    using it by accident.
    """
    import lightgbm as lgb

    X = np.vstack([X_pos, X_neg]).astype(np.float64)
    y = np.concatenate([np.ones(len(X_pos)), np.zeros(len(X_neg))]).astype(int)
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(X))
    cut = int(0.7 * len(X))
    tr, te = idx[:cut], idx[cut:]
    if len(np.unique(y[tr])) < 2 or len(np.unique(y[te])) < 2:
        return 0.5
    ds = lgb.Dataset(X[tr], label=y[tr])
    booster = lgb.train(
        {"objective": "binary", "num_leaves": 31, "learning_rate": 0.1, "num_threads": 1,
         "seed": seed, "deterministic": True, "verbosity": -1},
        ds,
        num_boost_round=120,
    )
    return float(roc_auc(y[te], booster.predict(X[te])))


def _shuffled_marginal_control(X: np.ndarray, seed: int = 7) -> np.ndarray:
    """A marginal-independent shuffled sampler from OUR OWN rows.

    Each column is permuted independently, which preserves every MARGINAL exactly and destroys every
    JOINT. A discriminator with real power separates this from the true rows easily (the joints are
    gone); one that cannot is a discriminator with no power, and that is what the control detects.
    """
    rng = np.random.default_rng(seed)
    out = X.copy()
    for j in range(out.shape[1]):
        out[:, j] = out[rng.permutation(out.shape[0]), j]
    return out


def run_f2(
    *,
    real_aligned: np.ndarray,
    ours_aligned: np.ndarray,
    ours_structure: np.ndarray | None = None,
    real_structure: np.ndarray | None = None,
    aligned_columns: Sequence[str] = (),
    structure_columns: Sequence[str] = (),
    ctgan_aligned: np.ndarray | None = None,
    paysim_aligned: np.ndarray | None = None,
    sparkov_aligned: np.ndarray | None = None,
) -> dict[str, Any]:
    """Run F2 on both subspaces, with the positive control gating everything."""
    results: dict[str, Any] = {}

    # ---- the positive control, on the aligned subspace -----------------------------
    control = _shuffled_marginal_control(ours_aligned)
    control_auc = _lightgbm_auc(control, real_aligned)
    power_ok = control_auc >= POWER_FLOOR_AUC

    def _one(subspace: str, ours: np.ndarray, real: np.ndarray, cols: Sequence[str],
             others: Mapping[str, np.ndarray | None]) -> F2Result:
        ours_auc = _lightgbm_auc(ours, real)
        arms: dict[str, float] = {}
        for name, arr in others.items():
            if arr is not None and len(arr):
                arms[name] = _lightgbm_auc(arr, real)
            else:
                arms[name] = float("nan")  # SKIPPED-DEPENDENCY-ABSENT, reported as such below
        return F2Result(
            subspace=subspace,
            ours_vs_real_auc=ours_auc,
            positive_control_auc=control_auc,
            power_ok=power_ok,
            control_arms=arms,
            n_real=len(real),
            n_synth=len(ours),
            columns=tuple(cols),
            reportable=power_ok,
            note=(
                "positive control passed; F2 numbers are reportable" if power_ok else
                "POSITIVE CONTROL FAILED (AUC below 0.90): the harness has no demonstrated power on "
                "this subspace, so NO F2 number is reported -- a low AUC here would be "
                "indistinguishable from a subspace too narrow to discriminate"
            ),
        )

    results["aligned_marginal"] = _one(
        "aligned_marginal", ours_aligned, real_aligned, aligned_columns,
        {"ctgan": ctgan_aligned, "paysim": paysim_aligned, "sparkov": sparkov_aligned},
    ).as_dict()
    results["aligned_marginal"]["interpretation"] = (
        "CTGAN is EXPECTED to be competitive here BY CONSTRUCTION -- it fits these marginals "
        "directly -- and we say so in advance. 'CTGAN beats us on the aligned subspace' is not a red "
        "gate; it would be losing on the wrong axis."
    )

    if ours_structure is not None and real_structure is not None and len(ours_structure):
        results["structure"] = _one(
            "structure", ours_structure, real_structure, structure_columns,
            {"ctgan": ctgan_aligned},  # a row-wise tabular generator has no structure to fit
        ).as_dict()
        results["structure"]["interpretation"] = (
            "The STRUCTURE subspace (lifecycle pairing, graph relations, value conservation) is where "
            "a row-wise tabular generator has nothing to fit and cannot compete. The claim we defend "
            "is the PAIR of subspaces, not a single AUC."
        )

    absent = [k for k, v in results["aligned_marginal"]["control_arms"].items()
              if v != v]  # NaN check
    results["summary"] = {
        "power_floor": POWER_FLOOR_AUC,
        "positive_control_auc": control_auc,
        "power_ok": power_ok,
        "control_arms_absent": absent,
        "targets": {
            "positive_control": ">= 0.90, else nothing is reported",
            "ours_aligned": "<= 0.65 (committed BEFORE running; if we land at 0.78 we publish 0.78)",
            "ours_below_ctgan_on_structure": "expected, and the whole point of the two-subspace split",
        },
        "goodhart_note": (
            "The discriminator is a FROZEN, VERSIONED AUDITOR used at evaluation time only. It is "
            "NEVER inside the attacker's reward, because a fidelity critic in the optimiser is "
            "textbook Goodhart -- the failure mode of every GAN fidelity claim."
        ),
        "missing_arms_note": (
            "CTGAN/PaySim/Sparkov are OPTIONAL controls. When a dependency or a public CSV is absent, "
            "that arm is reported SKIPPED-DEPENDENCY-ABSENT rather than fabricated."
        ),
    }
    return results
