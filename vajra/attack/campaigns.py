"""Turning compositions into executable campaigns.

`Campaign` objects are what the simulator executes, and WHICH campaigns run is decided by the
archive, not by a wishlist. This module is the translation layer: composition + plan -> a
`CampaignSpec` the engine can run.

Two entry points:
  * `campaigns_from_seeds()` — the 51 hand-authored compositions, used by `make sim` so the
    simulator has attack traffic before the ARENA exists. This is also the STATIC CONTROL ARM's
    entire attack set: identical models trained once on the seeded compositions with no loop.
  * `campaigns_from_plans()` — the loop's path, where the ARENA supplies plans.
"""

from __future__ import annotations

import hashlib
from typing import Iterable, Sequence

import numpy as np

from core.config import Config, load_config
from core.rng import stream
from grammar.cell_of import cell_of
from grammar.composition import Composition
from grammar.sealed import load_sealed_manifest
from grammar.seeds import Seed, load_seeds
from sim.engine import CampaignSpec


def _campaign_id(grammar_str: str, family_id: str, salt: str) -> str:
    """Content-derived id: the same intent yields the same id.

    That is a determinism property, not a convenience: a run that produces the same campaigns
    must label them identically, or the per-family recall table changes name between runs.
    """
    h = hashlib.blake2b(
        f"{family_id}|{grammar_str}|{salt}".encode("utf-8"), digest_size=4
    ).hexdigest()
    return f"CMP-{h}"


def _spec_from(
    comp: Composition,
    *,
    family_id: str,
    stages: Sequence[str],
    start_day: int,
    duration_days: int,
    events_per_day: int,
    arm: dict[str, object] | None = None,
    blind_composer: bool = False,
    budget_inr: float = 250_000.0,
    salt: str = "",
) -> CampaignSpec:
    manifest = load_sealed_manifest()
    cell = cell_of(comp, stages)
    return CampaignSpec(
        campaign_id=_campaign_id(str(comp), family_id, salt),
        family_id=family_id,
        grammar_str=str(comp),
        cell_id=cell.id,
        rail=comp.RAIL,
        access=comp.ACCESS,
        trust=comp.TRUST,
        evasion=comp.EVASION,
        monetisation=comp.MONETISATION,
        label=comp.LABEL,
        stages=tuple(stages),
        arm=dict(arm or {}),
        start_day=int(start_day),
        duration_days=int(duration_days),
        events_per_day=int(events_per_day),
        sealed=manifest.is_sealed(comp),
        blind_composer=blind_composer,
        rng_stream=f"attack.family.{family_id}",
        budget_inr=float(budget_inr),
    )


def campaigns_from_seeds(
    preset: str | None = None,
    cfg: Config | None = None,
    *,
    seeds: Sequence[Seed] | None = None,
    include_excluded_from_scoring: bool = True,
) -> list[CampaignSpec]:
    """Build campaigns from the hand-authored seeds, sized to hit the configured base rate.

    THE BASE RATE IS A POLICY PARAMETER. We size the campaign volume to realise it rather than
    letting it emerge, and the realised share is printed next to the configured one in the sim
    report so the two can be compared.

    `include_excluded_from_scoring=True` keeps double-dagger rows in the DATA (their observables
    are real) while `Seed.excluded_from_scoring` keeps them out of every scored RESULT. Dropping
    them from generation instead would make the visibility ablation unable to quantify what those
    views cost.
    """
    cfg = cfg or load_config()
    p = cfg.preset(preset)
    seed_list = list(seeds if seeds is not None else load_seeds())
    if not include_excluded_from_scoring:
        seed_list = [s for s in seed_list if not s.excluded_from_scoring]

    n_days = int(p["days"])
    target_campaigns = int(p["attack_campaigns"])
    rng = stream("attack.campaign")

    if not seed_list:
        return []

    # ---- sizing the attack volume to the configured base rate -------------------------
    # The base rate is a POLICY PARAMETER, so we size campaign volume to realise it rather than
    # letting it emerge. The three constants below are ESTIMATES, not fits, and each is named:
    #
    #   MEAN_DAILY_RATE      E[Gamma(1.5, 0.9)] after clipping — the per-cardholder daily rate
    #                        drawn in sim/habits.py.
    #   LIFECYCLE_MULTIPLIER total events per PRIMARY emission. Every approved authorisation can
    #                        produce a presentment, a chargeback, a refund, an inbound credit and
    #                        an onward send, so the total stream is several times the primary one.
    #   CAMPAIGN_EVENT_FACTOR events per campaign-day per unit of `events_per_day`, accounting for
    #                        the bandit's fan-out arm (mean ~2.55) and the multi-event emitters
    #                        (token provisioning, mandates and Lite emit more than one message).
    #
    # THE REALISED SHARE GOVERNS, not this estimate. `make sim` prints realised versus configured
    # side by side, and every recall figure names the base rate it was measured at.
    MEAN_DAILY_RATE = 1.35
    LIFECYCLE_MULTIPLIER = 6.74
    CAMPAIGN_EVENT_FACTOR = 3.57

    n_ch = int(p["cardholders"])
    est_benign_total = max(1.0, n_ch * MEAN_DAILY_RATE * n_days * LIFECYCLE_MULTIPLIER)
    br = cfg.base_rate
    target_attack_events = br * est_benign_total / max(1e-9, 1.0 - br)

    mean_duration = max(
        1.0, float(np.mean([min(n_days, max(1, len(s.stages))) for s in seed_list]))
    )
    denom = max(1.0, target_campaigns * mean_duration * CAMPAIGN_EVENT_FACTOR)
    # Cap so one campaign cannot dominate a family's recall denominator.
    per_campaign = int(np.clip(round(target_attack_events / denom), 1, 60))

    out: list[CampaignSpec] = []
    i = 0
    while len(out) < target_campaigns:
        seed = seed_list[i % len(seed_list)]
        i += 1
        duration = min(n_days, max(1, len(seed.stages)))
        start = int(rng.integers(0, max(1, n_days - duration + 1)))
        arm = {
            "amount_band": str(rng.choice(["micro", "low", "mid", "high"], p=[0.18, 0.34, 0.34, 0.14])),
            "fan_out": int(rng.choice([1, 3, 8], p=[0.55, 0.32, 0.13])),
            "hour_bucket": str(rng.choice(["night", "morning", "midday", "evening", "late"])),
        }
        out.append(
            _spec_from(
                seed.composition,
                family_id=seed.id,
                stages=seed.stages,
                start_day=start,
                duration_days=duration,
                events_per_day=per_campaign,
                arm=arm,
                salt=f"seed:{len(out)}",
            )
        )
    return out


def campaigns_from_plans(
    plans: Iterable[dict[str, object]],
    *,
    n_days: int,
    events_per_day: int = 8,
    blind_composer: bool = False,
) -> list[CampaignSpec]:
    """Build campaigns from ARENA plans (`attack/plan.py::AttackPlan.as_dict()` shape)."""
    rng = stream("attack.campaign")
    out: list[CampaignSpec] = []
    for i, plan in enumerate(plans):
        comp = Composition.parse(str(plan["grammar_str"]))
        stages = tuple(str(s) for s in (plan.get("stages") or ("establish", "extract")))
        duration = min(n_days, max(1, len(stages)))
        start = int(rng.integers(0, max(1, n_days - duration + 1)))
        out.append(
            _spec_from(
                comp,
                family_id=str(plan.get("family_id") or f"GEN-{i:04d}"),
                stages=stages,
                start_day=start,
                duration_days=duration,
                events_per_day=int(plan.get("events_per_day") or events_per_day),
                arm=dict(plan.get("arm") or {}),
                blind_composer=bool(plan.get("blind_composer", blind_composer)),
                budget_inr=float(plan.get("budget_inr") or 250_000.0),
                salt=f"plan:{i}",
            )
        )
    return out


def campaign_summary(campaigns: Sequence[CampaignSpec]) -> dict[str, object]:
    by_family: dict[str, int] = {}
    by_cell: dict[str, int] = {}
    by_rail: dict[str, int] = {}
    n_sealed = 0
    for c in campaigns:
        by_family[c.family_id] = by_family.get(c.family_id, 0) + 1
        by_cell[c.cell_id] = by_cell.get(c.cell_id, 0) + 1
        by_rail[c.rail] = by_rail.get(c.rail, 0) + 1
        n_sealed += int(c.sealed)
    return {
        "n_campaigns": len(campaigns),
        "n_families": len(by_family),
        "n_cells": len(by_cell),
        "n_sealed_campaigns": n_sealed,
        "campaigns_per_family": dict(sorted(by_family.items())),
        "campaigns_per_rail": dict(sorted(by_rail.items())),
        "planned_events": sum(c.events_per_day * c.duration_days for c in campaigns),
    }
