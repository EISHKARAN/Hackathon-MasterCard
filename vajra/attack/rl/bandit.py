"""Level 1 of the hierarchical RL attacker: a Thompson-sampling contextual bandit over arm parameters.

Chapelle & Li (NeurIPS 2011) and Agrawal & Goyal (ICML 2013) for the regret behaviour and for why
Thompson sampling beats epsilon-greedy and UCB in the noisy-reward, non-stationary regime — which is
exactly what a fraud detector's feedback is.

WHAT THIS LEVEL IS FOR: the PARAMETRIC action space inside a tactic. Amount band x entry mode x hour
bucket x fan-out is thousands of arms with a noisy reward; discretising it into the Level-2 Q-table
would destroy the tabular tractability that makes Level 2 fast and inspectable. So Level 2 chooses the
TACTIC and Level 1 chooses the NUMBERS.

============================== THE NON-STATIONARITY FIX ================================
Posterior counts DECAY by `rho` per tick. Without the discount, the posterior for an arm is dominated
by the PRE-RETRAIN regime and the bandit stops adapting — which looks like the defender winning when
it is actually the bandit's memory failing. The discount is what makes the bandit TRACK a retrained
defender rather than average over its whole history.
========================================================================================

OBSERVES ONLY WHAT AN ATTACKER OBSERVES. The reward is derived from `AttackerObservation` and the
attacker's own books. There is no path from a detector score into this class.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from attack.rl.observation import AttackerObservation
from core.paths import paths
from core.rng import stream


@dataclass(frozen=True, slots=True)
class Arm:
    """One point in the parametric action space."""

    amount_band: str
    entry_mode: str
    hour_bucket: str
    fan_out: int

    @property
    def key(self) -> str:
        return f"{self.amount_band}|{self.entry_mode}|{self.hour_bucket}|{self.fan_out}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "amount_band": self.amount_band,
            "entry_mode": self.entry_mode,
            "hour_bucket": self.hour_bucket,
            "fan_out": int(self.fan_out),
        }


@dataclass(frozen=True, slots=True)
class Context:
    """The context the bandit conditions on. All attacker-observable."""

    rail: str
    amount_decile: int
    hour_bucket: str
    entity_age_bucket: str

    @property
    def key(self) -> str:
        return f"{self.rail}|{self.amount_decile}|{self.hour_bucket}|{self.entity_age_bucket}"


@dataclass
class ThompsonBandit:
    """Beta-Bernoulli Thompson sampling per (context, arm), with discounted counts.

    A Beta posterior over "did this arm produce a non-adverse outcome" is the right shape: the
    attacker's per-transaction feedback is binary from its point of view (did the money move, or did
    something adverse happen), and the VALUE of a success is handled separately by the Level-2 reward
    rather than being crammed into this posterior.
    """

    discount_rho: float = 0.97
    prior_alpha: float = 1.0
    prior_beta: float = 1.0
    min_pulls_before_exploit: int = 3
    #: (context_key, arm_key) -> [alpha, beta]
    posterior: dict[tuple[str, str], list[float]] = field(default_factory=dict)
    #: Linear-Gaussian posterior over the continuous amount dimension, per context.
    amount_mean: dict[str, float] = field(default_factory=dict)
    amount_var: dict[str, float] = field(default_factory=dict)
    amount_prior_variance: float = 4.0
    amount_noise_variance: float = 1.0
    n_pulls: int = 0
    tick: int = 0
    arms: tuple[Arm, ...] = ()

    @classmethod
    def from_config(cls) -> "ThompsonBandit":
        import yaml

        with (paths.config / "rl.yaml").open("r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh) or {}
        b = dict(doc.get("bandit") or {})
        a = dict(doc.get("arms") or {})
        arms = tuple(
            Arm(band, mode, hour, int(fan))
            for band in (a.get("amount_band") or ["mid"])
            for mode in (a.get("entry_mode") or ["ecommerce"])
            for hour in (a.get("hour_bucket") or ["midday"])
            for fan in (a.get("fan_out") or [1])
        )
        return cls(
            discount_rho=float(b.get("discount_rho", 0.97)),
            prior_alpha=float(b.get("prior_alpha", 1.0)),
            prior_beta=float(b.get("prior_beta", 1.0)),
            min_pulls_before_exploit=int(b.get("min_pulls_before_exploit", 3)),
            amount_prior_variance=float(b.get("amount_prior_variance", 4.0)),
            amount_noise_variance=float(b.get("amount_noise_variance", 1.0)),
            arms=arms,
        )

    # ---- acting ----------------------------------------------------------------------
    def candidate_arms(self, tactic: str) -> tuple[Arm, ...]:
        """Arms consistent with the tactic Level 2 chose.

        Level 2 decides the DIRECTION; Level 1 explores within it. An unfiltered arm set would let
        the bandit undo the tactic the MDP just selected, which would make the two levels fight.
        """
        if not self.arms:
            return ()
        if tactic == "probe":
            return tuple(a for a in self.arms if a.amount_band == "micro")
        if tactic == "escalate_amount":
            return tuple(a for a in self.arms if a.amount_band in ("high", "very_high"))
        if tactic == "deescalate_amount":
            return tuple(a for a in self.arms if a.amount_band in ("micro", "low"))
        if tactic == "hug_threshold":
            return tuple(a for a in self.arms if a.amount_band in ("low", "mid"))
        if tactic == "split_velocity":
            return tuple(a for a in self.arms if a.fan_out >= 3 and a.amount_band in ("micro", "low"))
        if tactic in ("rotate_entity", "pad_payer_set"):
            return tuple(a for a in self.arms if a.fan_out >= 8)
        if tactic == "cash_out":
            return tuple(a for a in self.arms if a.amount_band in ("mid", "high", "very_high"))
        return self.arms

    def select(
        self, ctx: Context, tactic: str, rng: np.random.Generator | None = None
    ) -> tuple[Arm, dict[str, float]]:
        """Thompson-sample an arm. Returns the arm and the sampled values, for the tick trace."""
        r = rng if rng is not None else stream("attack.bandit")
        cands = self.candidate_arms(tactic) or self.arms
        if not cands:
            raise ValueError("bandit has no arms; check config/rl.yaml::arms")
        samples: dict[str, float] = {}
        best, best_v = cands[0], -np.inf
        for arm in cands:
            a, b = self.posterior.get((ctx.key, arm.key), [self.prior_alpha, self.prior_beta])
            # Sample from the posterior. Under-pulled arms have a wide posterior and therefore get
            # explored automatically -- that is the whole point of Thompson sampling and it is why we
            # need no separate exploration schedule at this level.
            v = float(r.beta(max(a, 1e-6), max(b, 1e-6)))
            samples[arm.key] = v
            if v > best_v:
                best, best_v = arm, v
        return best, samples

    # ---- learning --------------------------------------------------------------------
    def update(self, ctx: Context, arm: Arm, obs: AttackerObservation) -> None:
        """Update from ATTACKER-OBSERVABLE feedback only.

        Success = the money moved and nothing adverse happened. Note this is a strictly weaker signal
        than the defender's label: the attacker does not know whether it was *detected*, only whether
        it was *stopped* — and the difference is exactly why the sibling metric is measured on the
        defender's side rather than here.
        """
        key = (ctx.key, arm.key)
        a, b = self.posterior.get(key, [self.prior_alpha, self.prior_beta])
        success = bool((obs.approved or obs.credit_landed) and not obs.adverse)
        if success:
            a += 1.0
        else:
            b += 1.0
        self.posterior[key] = [a, b]
        self.n_pulls += 1

        # Linear-Gaussian update on the continuous amount dimension.
        if obs.amount_inr > 0:
            x = float(np.log1p(obs.amount_inr))
            m = self.amount_mean.get(ctx.key, x)
            v = self.amount_var.get(ctx.key, self.amount_prior_variance)
            k = v / (v + self.amount_noise_variance)
            self.amount_mean[ctx.key] = m + k * ((x if success else m) - m)
            self.amount_var[ctx.key] = (1.0 - k) * v + 1e-6

    def end_tick(self) -> None:
        """Decay the posteriors. THE NON-STATIONARITY FIX — see the module docstring."""
        rho = float(self.discount_rho)
        for key, (a, b) in list(self.posterior.items()):
            # Decay TOWARD the prior rather than toward zero: decaying to zero would make an arm's
            # posterior improper and the Beta sample undefined.
            self.posterior[key] = [
                self.prior_alpha + rho * (a - self.prior_alpha),
                self.prior_beta + rho * (b - self.prior_beta),
            ]
        self.tick += 1

    # ---- inspection ------------------------------------------------------------------
    def top_arms(self, n: int = 15) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for (ctx_key, arm_key), (a, b) in self.posterior.items():
            pulls = (a - self.prior_alpha) + (b - self.prior_beta)
            if pulls < self.min_pulls_before_exploit:
                continue
            rows.append(
                {
                    "context": ctx_key,
                    "arm": arm_key,
                    "posterior_mean": float(a / max(a + b, 1e-9)),
                    "effective_pulls": float(pulls),
                }
            )
        rows.sort(key=lambda r: (-r["posterior_mean"], -r["effective_pulls"]))
        return rows[:n]

    def diagnostics(self) -> dict[str, Any]:
        return {
            "algorithm": "Thompson sampling, Beta-Bernoulli per (context, arm), DISCOUNTED counts",
            "n_arms_declared": len(self.arms),
            "n_context_arm_pairs_seen": len(self.posterior),
            "n_pulls": self.n_pulls,
            "tick": self.tick,
            "discount_rho": self.discount_rho,
            "non_stationarity_note": (
                "Counts decay toward the PRIOR each tick. Without the discount an arm's posterior is "
                "dominated by the pre-retrain regime and the bandit stops adapting — which looks like "
                "the defender winning when it is the bandit's memory failing."
            ),
            "observability": (
                "Updated from AttackerObservation only. Success is 'the money moved and nothing "
                "adverse happened', which is strictly weaker than the defender's label — the attacker "
                "does not learn whether it was detected, only whether it was stopped."
            ),
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "diagnostics": self.diagnostics(),
                    "top_arms": self.top_arms(40),
                    "posterior": {f"{k[0]}##{k[1]}": v for k, v in self.posterior.items()},
                    "tick": self.tick,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> "ThompsonBandit":
        b = cls.from_config()
        if not path.exists():
            return b
        d = json.loads(path.read_text(encoding="utf-8"))
        for k, v in (d.get("posterior") or {}).items():
            ck, ak = k.split("##", 1)
            b.posterior[(ck, ak)] = [float(v[0]), float(v[1])]
        b.tick = int(d.get("tick", 0))
        return b


def context_for(
    rail: str, amount_inr: float, hour_ist: float, min_entity_age_days: float
) -> Context:
    """Build the bandit context from attacker-observable quantities."""
    decile = int(min(9, max(0, int(np.log1p(max(amount_inr, 0.0)) / 1.4))))
    hb = (
        "night" if hour_ist < 5 else
        "morning" if hour_ist < 11 else
        "midday" if hour_ist < 16 else
        "evening" if hour_ist < 21 else "late"
    )
    age = (
        "unknown" if min_entity_age_days < 0 else
        "d0" if min_entity_age_days < 1 else
        "w1" if min_entity_age_days < 7 else
        "m1" if min_entity_age_days < 30 else "aged"
    )
    return Context(rail=rail, amount_decile=decile, hour_bucket=hb, entity_age_bucket=age)
