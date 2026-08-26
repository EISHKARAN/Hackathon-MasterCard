"""Per-cardholder habit vectors, drawn from a hierarchical prior.

WHY THIS EXISTS AT ALL: the habit model is what lets anomaly be defined *relative to self*.
Every G1 velocity feature is computed as a ratio to the entity's own trailing baseline **as well
as** a peer-cohort percentile, and neither is meaningful without a per-actor habit model. A
generator with no habits can only produce global anomalies, and a global anomaly is the easy
case that every submission catches.

We fit PRIORS and never cardholder rows. That is why F6's membership-inference AUC target of
~0.50 is a property of the construction rather than an achievement we tuned for, and we say so
rather than presenting it as a privacy result.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.config import Config, load_config
from core.rng import substream
from sim.graph.entities import World


@dataclass(slots=True)
class Habit:
    """One cardholder's behavioural signature."""

    cardholder_id: str
    #: MCC mix: probability over the world's MCC pool. Sparse in practice — a real cardholder
    #: transacts in a handful of categories, not thirty.
    mcc_weights: np.ndarray
    #: Ticket-size lognormal, per cardholder, plus that cardholder's own rupee atoms.
    ticket_mu: float
    ticket_sigma: float
    atom_probability: float
    #: Diurnal phase (IST hours) and concentration. von Mises, so it wraps correctly at midnight.
    diurnal_phase: float
    diurnal_kappa: float
    #: Expected transactions per active day. The baseline every velocity RATIO divides by.
    daily_rate: float
    #: Home geo cell and how often the cardholder transacts away from it.
    home_geo: str
    travel_probability: float
    #: Per-rail propensity, so a cardholder is not equally likely on every rail.
    rail_weights: dict[str, float] = field(default_factory=dict)
    #: Dispute propensity: the base rate for a benign complaint, and for friendly fraud.
    dispute_propensity: float = 0.0
    #: Preferred device index, so device churn is a real signal rather than uniform noise.
    primary_device_idx: int = 0

    def sample_amount(self, rng: np.random.Generator) -> float:
        """Draw a ticket. Round-number atoms are the F5 stylised fact this produces."""
        if rng.random() < self.atom_probability:
            atoms = _ATOMS
            return float(atoms[int(rng.integers(0, len(atoms)))])
        v = float(np.exp(rng.normal(self.ticket_mu, self.ticket_sigma)))
        return float(np.clip(np.round(v, 2), _MIN_AMOUNT, _MAX_AMOUNT))

    def sample_hour(self, rng: np.random.Generator) -> float:
        """Draw an IST hour from the cardholder's own von Mises diurnal shape.

        von Mises rather than a truncated normal because time-of-day is CIRCULAR: a normal
        centred at 23:00 leaks probability past midnight into negative hours, and the Bahnsen
        et al. (2016) result on periodic features is specifically about getting this right.
        """
        theta = float(rng.vonmises(mu=self.diurnal_phase, kappa=self.diurnal_kappa))
        hour = (theta + np.pi) / (2.0 * np.pi) * 24.0
        return float(hour % 24.0)


_ATOMS: tuple[float, ...] = ()
_MIN_AMOUNT = 5.0
_MAX_AMOUNT = 500_000.0


def _init_amount_constants(cfg: Config) -> None:
    global _ATOMS, _MIN_AMOUNT, _MAX_AMOUNT
    acfg = cfg.scenario["amount_law"]
    _ATOMS = tuple(float(x) for x in acfg["atoms"])
    _MIN_AMOUNT = float(acfg["min_amount"])
    _MAX_AMOUNT = float(acfg["max_amount"])


def hour_to_vonmises_mu(hour_ist: float) -> float:
    """Map an IST hour to the von Mises mu on [-pi, pi)."""
    return (float(hour_ist) / 24.0) * 2.0 * np.pi - np.pi


def build_habits(world: World, cfg: Config | None = None) -> dict[str, Habit]:
    """One habit vector per cardholder, from a hierarchical prior.

    Hierarchical in the sense that matters: population-level hyper-parameters come from
    config/scenario.yaml, and each cardholder draws its own parameters from them. That is what
    makes peer-cohort percentiles meaningful — there is a real population distribution to be a
    percentile of.
    """
    cfg = cfg or load_config()
    _init_amount_constants(cfg)
    acfg = cfg.scenario["amount_law"]
    calcfg = cfg.scenario["calendar"]
    mix = cfg.rail_mix

    n_mcc = len(world.mcc_pool)
    peaks = [float(h) for h in calcfg["diurnal_peaks_ist"]]
    pop_kappa = float(calcfg["diurnal_concentration"])

    habits: dict[str, Habit] = {}
    for cid, ch in world.cardholders.items():
        rng = substream("sim.habits", cid)

        # Sparse MCC mix: a Dirichlet with a small concentration puts most mass on a few MCCs,
        # which is what a real cardholder's category footprint looks like.
        alpha = np.full(n_mcc, 0.12)
        # Everyone shops for groceries and fuel; those get a lift so the population mix is not
        # uniform-random-sparse.
        for common_idx in range(min(6, n_mcc)):
            alpha[common_idx] += 0.9
        w = rng.dirichlet(alpha)

        # Per-cardholder ticket law around the population law.
        mu = float(rng.normal(float(acfg["lognormal_mu"]), 0.45))
        sigma = float(np.clip(rng.normal(float(acfg["lognormal_sigma"]), 0.18), 0.35, 2.2))

        # Two population diurnal modes (a midday peak and an evening peak); each cardholder
        # picks one and jitters it.
        peak = peaks[int(rng.integers(0, len(peaks)))]
        phase = hour_to_vonmises_mu((peak + float(rng.normal(0.0, 1.6))) % 24.0)

        # Daily rate: heavy-tailed. A few cardholders transact constantly; most rarely.
        rate = float(np.clip(rng.gamma(shape=1.5, scale=0.9), 0.03, 14.0))

        # Per-rail propensity: perturb the population mix per cardholder so rail choice is a
        # personal habit, then renormalise.
        rw_raw = {r: max(1e-6, float(rng.gamma(shape=2.0, scale=1.0)) * p) for r, p in mix.items()}
        rw_total = sum(rw_raw.values())
        rail_weights = {r: v / rw_total for r, v in rw_raw.items()}

        habits[cid] = Habit(
            cardholder_id=cid,
            mcc_weights=w,
            ticket_mu=mu,
            ticket_sigma=sigma,
            atom_probability=float(
                np.clip(rng.normal(float(acfg["atom_probability"]), 0.05), 0.02, 0.45)
            ),
            diurnal_phase=phase,
            diurnal_kappa=float(np.clip(rng.normal(pop_kappa, 0.4), 0.35, 5.0)),
            daily_rate=rate,
            home_geo=ch.geo_cell,
            travel_probability=float(np.clip(rng.beta(1.4, 22.0), 0.0, 0.35)),
            rail_weights=rail_weights,
            dispute_propensity=float(np.clip(rng.beta(1.2, 260.0), 0.0, 0.08)),
            primary_device_idx=0,
        )
    return habits


def peer_cohort_key(world: World, cardholder_id: str) -> str:
    """The cohort a cardholder's percentile features are computed WITHIN.

    Deliberately coarse and BUSINESS-MEANINGFUL (issuer x credit-limit band x geo tier) rather
    than a clustering, because a learned cohort assignment fitted on a pool containing sealed
    rows would import holdout information into every percentile feature — the statistic-level
    leakage channel that an entity-id audit cannot see.
    """
    ch = world.cardholders[cardholder_id]
    if ch.credit_limit_inr < 0:
        band = "nolimit"
    elif ch.credit_limit_inr < 50_000:
        band = "lo"
    elif ch.credit_limit_inr < 200_000:
        band = "mid"
    else:
        band = "hi"
    return f"{ch.issuer_id}|{band}"
