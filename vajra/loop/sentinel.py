"""The Sentinel and the frozen canary suite.

============================ WHY A CONJUNCTION, NOT A THRESHOLD =========================
PAYMENTS DRIFT IS OVERWHELMINGLY BENIGN: festivals, a new co-brand portfolio, an acquirer migration, a
merchant-mix shift. A single-signal PSI or KS trigger would fire constantly, and its firing would mean
nothing — which is a flaw we identified and fixed rather than inherited.

So the Sentinel fires ONLY on a conjunction of three:
    1. feature drift UNEXPLAINED BY A BENIGN-DRIFT NULL MODEL — the same world replayed without attack
       campaigns, seasonal terms included; AND
    2. a shift in conformal p-value mass; AND
    3. canary-probe degradation.

Single-signal PSI movement produces a LOGGED NOTE, not a red team. The secondary benefit is
adversarial: deliberately tripping the Sentinel to exhaust red-team budget is an attack in the
AUTOIMMUNE suite, and a conjunction trigger is materially harder to trip than a threshold on one
statistic.
========================================================================================

THE CANARY SUITE IS IMMUNE MEMORY AGAINST SLOW-DRIP POISONING (ATK-Z2). A fixed set of probe
transactions is re-scored after EVERY retrain, and a MONOTONE DECLINE in canary anomaly score across
model versions fails the promotion gate. Without it, an attacker who interpolates gradually from
benign to attack behaviour is retrained into the model's notion of normal, and no in-window statistic
notices.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


# ---------------------------------------------------------------------------------------
# Drift statistics
# ---------------------------------------------------------------------------------------

def population_stability_index(
    reference: np.ndarray, current: np.ndarray, n_bins: int = 10
) -> float:
    """PSI over quantile bins of the REFERENCE distribution.

    Bins from the reference, not from the pooled data: pooled bins move when the current window moves,
    which understates drift precisely when drift is what you are trying to measure.
    """
    r = np.asarray(reference, dtype=np.float64)
    c = np.asarray(current, dtype=np.float64)
    r, c = r[np.isfinite(r)], c[np.isfinite(c)]
    if r.size < 20 or c.size < 20:
        return 0.0
    edges = np.unique(np.quantile(r, np.linspace(0, 1, n_bins + 1)))
    if edges.size < 3:
        return 0.0
    rh, _ = np.histogram(r, bins=edges)
    ch, _ = np.histogram(c, bins=edges)
    rp = np.maximum(rh / max(1, rh.sum()), 1e-6)
    cp = np.maximum(ch / max(1, ch.sum()), 1e-6)
    return float(np.sum((cp - rp) * np.log(cp / rp)))


def conformal_p_mass_shift(
    reference_p: np.ndarray, current_p: np.ndarray, alpha: float = 0.05
) -> dict[str, float]:
    """Change in the MASS of low conformal p-values.

    Not a distribution distance: the quantity that matters operationally is "how much more of my
    traffic is now unlike anything in my calibration set", which is a mass in the low tail. A
    distribution distance would also move for benign reasons in the middle of the distribution.
    """
    r = np.asarray(reference_p, dtype=np.float64)
    c = np.asarray(current_p, dtype=np.float64)
    r, c = r[np.isfinite(r)], c[np.isfinite(c)]
    if r.size < 20 or c.size < 20:
        return {"reference_mass": 0.0, "current_mass": 0.0, "shift": 0.0}
    rm = float((r <= alpha).mean())
    cm = float((c <= alpha).mean())
    return {"reference_mass": rm, "current_mass": cm, "shift": cm - rm, "alpha": alpha}


# ---------------------------------------------------------------------------------------
# The frozen canary suite
# ---------------------------------------------------------------------------------------

@dataclass
class CanarySuite:
    """A FIXED set of probe rows, re-scored after every retrain.

    FROZEN across the whole evaluation — the probe set is chosen once and never regenerated. Selecting
    fresh canaries per tick would make a decline in their score unattributable: you could not tell
    whether the model changed or the probes did.
    """

    X: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))
    feature_names: tuple[str, ...] = ()
    #: score history per model version, in order.
    history: list[dict[str, Any]] = field(default_factory=list)
    frozen: bool = False

    @classmethod
    def freeze_from(
        cls, X: np.ndarray, feature_names: Sequence[str], *, n: int = 200, seed_name: str = "loop.tick"
    ) -> "CanarySuite":
        from core.rng import stream

        rng = stream(seed_name)
        m = X.shape[0]
        if m == 0:
            return cls(frozen=True, feature_names=tuple(feature_names))
        idx = rng.choice(m, size=int(min(n, m)), replace=False)
        return cls(X=np.asarray(X)[np.sort(idx)].copy(), feature_names=tuple(feature_names), frozen=True)

    def observe(self, model_version: str, scores: np.ndarray) -> dict[str, Any]:
        s = np.asarray(scores, dtype=np.float64)
        rec = {
            "model_version": model_version,
            "n": int(s.size),
            "mean_score": float(s.mean()) if s.size else 0.0,
            "p90_score": float(np.quantile(s, 0.9)) if s.size else 0.0,
        }
        self.history.append(rec)
        return rec

    def degradation(self, *, min_versions: int = 3) -> dict[str, Any]:
        """MONOTONE DECLINE across model versions is the ATK-Z2 signature.

        Monotone rather than "lower than the first": a single dip is noise, and a monotone sequence
        across three or more versions is the shape slow-drip contamination actually produces.
        """
        if len(self.history) < min_versions:
            return {
                "detected": False,
                "n_versions": len(self.history),
                "why": f"needs at least {min_versions} model versions to judge a trend",
            }
        means = [h["mean_score"] for h in self.history]
        monotone = all(means[i + 1] <= means[i] + 1e-12 for i in range(len(means) - 1))
        total_drop = means[0] - means[-1]
        return {
            "detected": bool(monotone and total_drop > 0.02),
            "monotone_decline": monotone,
            "total_drop": float(total_drop),
            "means": [float(m) for m in means],
            "n_versions": len(self.history),
            "why_monotone": (
                "A single dip is noise. A monotone decline across three or more retrains is the shape "
                "slow-drip contamination (ATK-Z2) produces, and it is what the promotion gate blocks on."
            ),
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path.with_suffix(".npz"), X=self.X)
        path.with_suffix(".json").write_text(
            json.dumps(
                {
                    "feature_names": list(self.feature_names),
                    "frozen": self.frozen,
                    "history": self.history,
                    "degradation": self.degradation(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> "CanarySuite":
        npz, meta = path.with_suffix(".npz"), path.with_suffix(".json")
        X = np.load(npz)["X"] if npz.exists() else np.zeros((0, 0))
        d = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
        return cls(
            X=X,
            feature_names=tuple(d.get("feature_names") or ()),
            history=list(d.get("history") or []),
            frozen=bool(d.get("frozen", True)),
        )


# ---------------------------------------------------------------------------------------
# The Sentinel
# ---------------------------------------------------------------------------------------

@dataclass
class SentinelVerdict:
    fired: bool
    signals: dict[str, Any]
    note: str

    def as_dict(self) -> dict[str, Any]:
        return {"fired": self.fired, "signals": self.signals, "note": self.note}


@dataclass
class Sentinel:
    """The three-way conjunction trigger."""

    psi_threshold: float = 0.20
    conformal_shift_threshold: float = 0.03
    #: Fraction of a feature's PSI that must be unexplained by the benign-null replay.
    benign_null_explained_fraction: float = 0.60
    log: list[dict[str, Any]] = field(default_factory=list)

    def evaluate(
        self,
        *,
        reference_features: Mapping[str, np.ndarray],
        current_features: Mapping[str, np.ndarray],
        benign_null_features: Mapping[str, np.ndarray] | None,
        reference_conformal_p: np.ndarray,
        current_conformal_p: np.ndarray,
        canary: CanarySuite,
        stamped_at: str = "",
    ) -> SentinelVerdict:
        """Evaluate the conjunction. A single signal produces a LOGGED NOTE, never a red team."""
        # ---- signal 1: drift UNEXPLAINED by the benign-drift null model -----------------
        per_feature: dict[str, dict[str, float]] = {}
        unexplained: list[str] = []
        for name, cur in current_features.items():
            ref = reference_features.get(name)
            if ref is None:
                continue
            psi_obs = population_stability_index(ref, cur)
            psi_null = 0.0
            if benign_null_features is not None and name in benign_null_features:
                # The SAME WORLD replayed WITHOUT attack campaigns, seasonal terms included. If the
                # null model drifts as much as the observed window, the drift is benign and the
                # Sentinel must not fire on it -- that is the whole point of having a null model
                # rather than a threshold.
                psi_null = population_stability_index(ref, benign_null_features[name])
            explained = (psi_null / psi_obs) if psi_obs > 1e-9 else 1.0
            per_feature[name] = {
                "psi_observed": psi_obs,
                "psi_benign_null": psi_null,
                "explained_fraction": float(min(1.0, explained)),
            }
            if psi_obs >= self.psi_threshold and explained < self.benign_null_explained_fraction:
                unexplained.append(name)
        signal_drift = bool(unexplained)

        # ---- signal 2: conformal p-mass shift -------------------------------------------
        pm = conformal_p_mass_shift(reference_conformal_p, current_conformal_p)
        signal_conformal = bool(pm["shift"] >= self.conformal_shift_threshold)

        # ---- signal 3: canary degradation -----------------------------------------------
        deg = canary.degradation()
        signal_canary = bool(deg.get("detected", False))

        signals = {
            "unexplained_drift": {
                "fired": signal_drift,
                "features": unexplained[:12],
                "n_features_checked": len(per_feature),
                "per_feature": dict(sorted(per_feature.items())[:20]),
            },
            "conformal_p_mass_shift": {"fired": signal_conformal, **pm},
            "canary_degradation": {"fired": signal_canary, **deg},
        }
        n_fired = sum(1 for k in ("unexplained_drift", "conformal_p_mass_shift", "canary_degradation")
                      if signals[k]["fired"])
        fired = n_fired == 3

        if fired:
            note = (
                "SENTINEL FIRED. All three conditions held: drift unexplained by the benign-null "
                "replay, a shift in conformal p-value mass, AND canary degradation. Firing the red team."
            )
        elif n_fired == 0:
            note = "no signal. No note logged beyond this record."
        else:
            note = (
                f"LOGGED NOTE ONLY, not a red team: {n_fired} of 3 conditions held. Payments drift is "
                f"overwhelmingly benign, so a single-signal trigger would fire constantly and its "
                f"firing would mean nothing. This is also why deliberately tripping the Sentinel to "
                f"exhaust red-team budget (an AUTOIMMUNE attack) is hard."
            )

        self.log.append(
            {"stamped_at": stamped_at, "fired": fired, "n_signals_fired": n_fired, "note": note}
        )
        return SentinelVerdict(fired=fired, signals=signals, note=note)

    def as_dict(self) -> dict[str, Any]:
        return {
            "thresholds": {
                "psi": self.psi_threshold,
                "conformal_shift": self.conformal_shift_threshold,
                "benign_null_explained_fraction": self.benign_null_explained_fraction,
            },
            "trigger": "CONJUNCTION of three signals; a single signal is a logged note",
            "log": self.log,
            "design_note": (
                "Payments drift is overwhelmingly BENIGN — festivals, a new portfolio, an acquirer "
                "migration. A single-signal PSI or KS trigger fires constantly and means nothing. The "
                "benign-drift null model is the same world replayed WITHOUT attack campaigns, seasonal "
                "terms included, generated by `make sim --no-attacks`."
            ),
        }
