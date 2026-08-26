"""Generator B — an INDEPENDENTLY WRITTEN benign+attack emitter. Different code path, same spec.

WHY IT EXISTS: training and testing on one simulator proves the consistency of one mental model, not
detection. Generator B is the only IN-SCOPE evidence that the detector learned payment STRUCTURE
rather than our main simulator's code artefacts. Resampling world parameters from the same code path
shares every generative artefact and proves nothing; a second author writing to the same schema does
not.

SCOPE IS BOUNDED ON PURPOSE: card-CNP and UPI-PAY only. A second full-rail generator is not a two-day
job, and pretending otherwise is how this line item becomes a week. What it replaces is stated: it is
the cross-generator arm of F2 and the artifact-independence check, not a second Tier-A simulator.

DELIBERATELY DIFFERENT from `sim/`: this file does NOT import the `sim/rails/` emitters or the
`sim/engine` day loop. It draws its own actors, its own amount law (a mixture-of-Gaussians rather than
a lognormal-with-atoms), its own diurnal shape (a two-state hidden Markov chain rather than von Mises),
and emits CanonicalEvent records directly. The ONLY thing it shares with `sim/` is `sim/schema.py` --
which is the point: same contract, independent construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from core.config import Config, load_config
from core.rng import stream
from sim.schema import CanonicalEvent

#: Generator B's OWN identifier space, disjoint from the main sim's, so a cross-generator eval cannot
#: accidentally join entities across generators.
_BIN_PREFIXES = ("999600", "999601", "999700")


@dataclass
class GeneratorB:
    """A compact, independently-authored emitter for card-CNP and UPI-PAY."""

    cfg: Config
    n_actors: int
    n_days: int
    base_rate: float

    @classmethod
    def build(cls, preset: str | None = None, cfg: Config | None = None) -> "GeneratorB":
        cfg = cfg or load_config()
        p = cfg.preset(preset)
        # Deliberately a fraction of the main sim's size: Generator B is an evidence arm, not a
        # production run, and its scope note says card-CNP + UPI-PAY only.
        return cls(cfg=cfg, n_actors=max(200, int(p["cardholders"]) // 6),
                   n_days=int(p["days"]), base_rate=cfg.base_rate)

    def _amount(self, rng: np.random.Generator, fraud: bool) -> float:
        """Mixture of Gaussians in log-space — a DIFFERENT amount law from the main sim's lognormal.

        If the detector had memorised the main sim's amount atoms, this different law would break it,
        which is exactly the artifact-independence the cross-generator arm tests.
        """
        if fraud:
            comp = rng.integers(0, 2)
            mu, sd = ([4.0, 1.2], [10.5, 0.6])[comp], ([4.0, 1.2], [10.5, 0.6])
            m, s = (4.0, 1.2) if comp == 0 else (10.5, 0.6)
        else:
            comp = rng.integers(0, 3)
            m, s = [(6.0, 0.9), (7.8, 0.7), (9.2, 1.1)][int(comp)]
        return float(np.clip(np.round(np.exp(rng.normal(m, s)), 2), 5.0, 500_000.0))

    def _hour(self, rng: np.random.Generator, state: int) -> float:
        """A two-state hidden-Markov diurnal shape, NOT the von Mises of the main sim."""
        centre = 11.0 if state == 0 else 20.0
        return float(np.clip(rng.normal(centre, 2.5) % 24.0, 0.0, 23.99))

    def run(self) -> list[CanonicalEvent]:
        rng = stream("generator_b.benign")
        arng = stream("generator_b.attack")
        cal_start = 1_772_000_000.0  # a fixed epoch base; Generator B has no calendar dependency
        events: list[CanonicalEvent] = []
        seq = 0
        rails = ("card-cnp-keyed", "upi-pay")

        for a in range(self.n_actors):
            pan = _BIN_PREFIXES[a % len(_BIN_PREFIXES)] + f"{a:09d}0"
            vpa = f"gb{a:07d}@vjpsp"
            rate = float(np.clip(rng.gamma(1.4, 0.8), 0.05, 8.0))
            state = int(rng.integers(0, 2))
            for day in range(self.n_days):
                n = int(rng.poisson(rate))
                for _ in range(n):
                    seq += 1
                    is_fraud = bool(rng.random() < self.base_rate)
                    r = rng.integers(0, 2)
                    rail = rails[int(r)]
                    hour = self._hour(rng, state)
                    ts = cal_start + day * 86_400.0 + hour * 3600.0
                    ev = CanonicalEvent(
                        event_id=f"GB{seq:010d}", ts=ts, day_index=day, hour_ist=hour,
                        dow=day % 7, rail=rail, message_kind="authorisation", tier="A",
                        amount_inr=self._amount(rng, is_fraud), generator="generator-b",
                    )
                    if rail == "card-cnp-keyed":
                        ev.pan_canonical = pan
                        ev.bin_prefix = pan[:6]
                        ev.pos_entry_mode = "ecommerce"
                        ev.cvv2_result = "match" if rng.random() < 0.9 else "no_match"
                        ev.avs_result = "match" if rng.random() < 0.7 else "not_requested"
                        ev.threeds_authentication_result = "not_applicable"
                        ev.threeds_eci = "none"
                        ev.emv_cryptogram_present = False
                    else:
                        ev.vpa = vpa
                        ev.payee_vpa = f"gbpayee{int(rng.integers(0, self.n_actors)):07d}@vjpsp"
                        ev.upi_initiation_mode = "intent"
                        ev.pos_entry_mode = "intent"
                        ev.cvm_result = "online_pin"
                        ev.threeds_authentication_result = "not_applicable"
                        ev.threeds_eci = "none"
                        ev.emv_cryptogram_present = False
                        ev.beneficiary_id = f"GBBEN{int(rng.integers(0, self.n_actors)):07d}"
                        ev.payee_vpa_age_days = float(rng.integers(0, 800))
                        ev.beneficiary_account_age_days = ev.payee_vpa_age_days
                    ev.account_age_days = float(rng.integers(0, 1500))
                    ev.pan_age_days = ev.account_age_days
                    ev.vpa_age_days = ev.account_age_days
                    ev.device_age_days = float(rng.integers(0, 900))
                    ev.approved = not (is_fraud and rng.random() < 0.4)
                    ev.response_code = "approved" if ev.approved else "declined_risk"
                    ev.response_latency_ms = float(abs(rng.normal(44.0, 15.0)))
                    ev.incumbent_accept_probability = float(np.clip(rng.beta(8, 2), 0.05, 0.95))
                    ev.incumbent_decision = "accept" if ev.approved else "decline"
                    if is_fraud:
                        ev.oracle_is_attack = True
                        ev.attack_family_id = "GENB-FRAUD"
                        ev.attack_grammar_str = ""  # Generator B is not grammar-driven; that is the point
                        ev.attack_campaign_id = f"GENB-{seq}"
                        ev.oracle_value_at_risk_inr = ev.amount_inr
                    if rng.random() < 0.02:
                        state = 1 - state
                    events.append(ev)

        events.sort(key=lambda e: (e.ts, e.event_id))
        return events

    def report(self, events: list[CanonicalEvent]) -> dict[str, Any]:
        n_attack = sum(1 for e in events if e.oracle_is_attack)
        return {
            "generator": "generator-b",
            "n_events": len(events),
            "n_attack": n_attack,
            "rails": ["card-cnp-keyed", "upi-pay"],
            "scope_note": (
                "card-CNP + UPI-PAY ONLY, independently authored. Different amount law "
                "(mixture-of-Gaussians vs the main sim's lognormal-with-atoms), different diurnal "
                "shape (two-state HMM vs von Mises), disjoint identifier space, NOT grammar-driven. "
                "The only shared thing is sim/schema.py -- same contract, independent construction."
            ),
            "what_it_replaces": (
                "the cross-generator arm of F2 and the artifact-independence check. NOT a second "
                "full-rail simulator; a second full-rail generator is not a two-day job."
            ),
        }
