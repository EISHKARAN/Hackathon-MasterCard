"""vajra-sim: the deterministic seeded discrete-event engine.

A hand-rolled SimPy-style loop rather than a framework. One process. Polars/pyarrow on the way
out, DuckDB for analytics. No message bus, no Kafka, no Flink — those buy throughput we are not
measuring at scale and cost days we do not have.

THE DAY LOOP, in order, because the order is load-bearing:

    1.  advance actor lifecycle (dormancy / reactivation / closure)
    2.  run today's due FOLLOW-UPS first — a presentment for yesterday's auth must land before
        today's traffic, or the lifecycle reads as out-of-order to any sequence feature
    3.  draw today's benign traffic per active cardholder, scaled by the shared calendar
    4.  overlay the HARD-BENIGN cohorts
    5.  overlay attack campaigns
    6.  for every emitted event: incumbent policy -> issuer response -> lifecycle scheduling ->
        beneficiary leg -> label observation

Step 6's ORDER is the part that is easy to get wrong. The incumbent decides BEFORE the issuer
response, because the incumbent's decline is what makes training data approval-conditioned. The
lifecycle is scheduled AFTER the response, because only an APPROVED authorisation has a
presentment — scheduling it inside the emitter would create presentments for declined
authorisations, which is an F1 violation by construction.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np

from core.config import Config, load_config
from core.rng import stream, substream
from sim.calendar import Calendar, advance_lifecycle, build_calendar
from sim.cohorts import ALL_COHORTS, HARD_BENIGN_12, HARD_BENIGN_B, CohortSpec, sizing_report
from sim.graph.builder import build_world
from sim.graph.entities import World
from sim.habits import Habit, build_habits
from sim.incumbent import IncumbentPolicy, propensity_histogram
from sim.labels import LabelEngine
from sim.rails import (
    DERIVED_RAILS,
    EMITTERS,
    Followup,
    SimContext,
    emit_inbound_credit,
    emit_pacs_status,
    emitter_for,
    schedule_card_lifecycle,
    schedule_refund,
)
from sim.schema import CanonicalEvent

#: Response codes the issuer can return, and the shape of the decision.
_STEP_UP_RAILS = frozenset({"card-cnp-3ds", "card-token-provisioning"})

#: Message kinds that are actually DECIDED — i.e. that reach the incumbent policy and receive an
#: issuer response. Everything else is informational or derived: it inherits its outcome from the
#: message it resolves to and must NOT be re-decided.
#:
#: Getting this set wrong is not cosmetic. Passing a presentment through the incumbent would let
#: the policy "decline" a settlement message that had already been approved at authorisation
#: time, which is incoherent as payments and would also silently overwrite a STRUCTURAL decline
#: code (a mandate-scope refusal) with a risk decline.
DECISIONABLE_KINDS: frozenset[str] = frozenset(
    {
        "authorisation",
        "provisioning_request",
        "collect_response",
        "mandate_debit",
        "credit_transfer",
        "agent_authorisation",
        "lite_debit",
        "assisted_withdrawal",
        "refund_credit",
    }
)

#: Structural decline codes. A structural refusal is a G0-style guard: it wins over any risk
#: decision, and the risk engine must not be able to relabel it.
_STRUCTURAL_DECLINES: frozenset[str] = frozenset({"declined_mandate_scope"})


@dataclass
class CampaignSpec:
    """An attack campaign the engine executes. Produced by the ARENA, or from a seed."""

    campaign_id: str
    family_id: str
    grammar_str: str
    cell_id: str
    rail: str
    access: str
    trust: str
    evasion: str
    monetisation: str
    label: str
    stages: tuple[str, ...]
    #: Bandit arm parameters (amount band, entry mode, hour bucket, fan-out, ...).
    arm: dict[str, Any] = field(default_factory=dict)
    #: Days the campaign is active, and how many events per active day.
    start_day: int = 0
    duration_days: int = 3
    events_per_day: int = 6
    sealed: bool = False
    blind_composer: bool = False
    rng_stream: str = ""
    budget_inr: float = 250_000.0

    def attack_dict(self, stage: str) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "family_id": self.family_id,
            "grammar_str": self.grammar_str,
            "cell_id": self.cell_id,
            "stage": stage,
            "sealed": self.sealed,
            "rng_stream": self.rng_stream or f"attack.family.{self.family_id}",
            "access": self.access,
            "trust": self.trust,
            "evasion": self.evasion,
            "monetisation": self.monetisation,
            "label": self.label,
            "amount_band": self.arm.get("amount_band"),
            "entry_mode": self.arm.get("entry_mode"),
            "fan_out": self.arm.get("fan_out"),
        }


@dataclass
class SimResult:
    events: list[CanonicalEvent]
    labels: LabelEngine
    world: World
    ctx: SimContext
    report: dict[str, Any]


def _attack_from_event(ev: CanonicalEvent) -> dict[str, Any] | None:
    """Reconstruct the attack dict from an event's own provenance, or None if it is benign.

    Followup builders run long after their antecedent, so the engine no longer holds the campaign's
    attack dict. The event carries the provenance it needs, so this recovers it rather than defaulting
    to "benign" -- which is what silently reclassified the derived legs of every attack chain.

    Deliberately PARTIAL: only the keys `_finalise` and `schedule_card_lifecycle` actually read are
    reconstructed. Inventing an `evasion` or `amount_band` we do not know would fabricate attacker
    intent for a message the attacker did not choose the shape of.
    """
    if not ev.oracle_is_attack:
        return None
    return {
        "campaign_id": ev.attack_campaign_id,
        "family_id": ev.attack_family_id,
        "grammar_str": ev.attack_grammar_str,
        "cell_id": ev.attack_cell_id,
        "stage": ev.attack_stage or "extract",
    }


#: Days of benign volume to observe before the attack-volume controller engages. Below this, one
#: day's Poisson draw would swing the whole run.
_ATTACK_TUNE_WARMUP_DAYS = 3


class Engine:
    def __init__(
        self,
        preset: str | None = None,
        cfg: Config | None = None,
        *,
        generator: str = "vajra-sim",
    ) -> None:
        self.cfg = cfg or load_config()
        self.preset = self.cfg.preset(preset)
        self.generator = generator
        #: Multiplier on every campaign's events_per_day, steered by `_retune_attack_volume`.
        self._attack_volume_factor: float = 1.0
        self._n_attack_emitted: int = 0
        self._campaign_day_factor_sum: float = 0.0
        self._campaign_days_after: list[int] = []
        self.n_days = int(self.preset["days"])
        self.calendar: Calendar = build_calendar(self.n_days)
        self.world: World = build_world(self.preset["name"], self.cfg)
        self.habits: dict[str, Habit] = build_habits(self.world, self.cfg)
        self.ctx = SimContext(
            world=self.world,
            habits=self.habits,
            calendar=self.calendar,
            cfg=self.cfg,
            rng=stream("sim.rails"),
        )
        self.incumbent = IncumbentPolicy.from_config(self.cfg)
        self.labels = LabelEngine.build(self.cfg)

        self._benign_rng = stream("sim.benign")
        self._cohort_rng = stream("sim.cohorts.hard_benign_12")
        self._cohort_b_rng = stream("sim.cohorts.hard_benign_b")
        self._incumbent_rng = stream("sim.incumbent")
        self._label_rng = stream("sim.labels")
        self._lifecycle_rng = stream("sim.calendar")

        self._followups: dict[int, list[Followup]] = {}
        self._states: dict[str, str] = {cid: ch.state for cid, ch in self.world.cardholders.items()}
        self._dormant_since: dict[str, int] = {cid: -1 for cid in self.world.cardholders}
        self._accept_probs: list[float] = []
        self._sampled_rails = [r for r in self.cfg.all_rails if r not in DERIVED_RAILS]
        self._emitted = 0

    # ---- scheduling -------------------------------------------------------------------
    def _schedule(self, fups: Iterable[Followup]) -> None:
        for f in fups:
            if f is None:
                continue
            day = int(f.due_day)
            if day < 0 or day >= self.n_days:
                # Beyond the horizon. Counted so a truncated lifecycle is VISIBLE rather than
                # silently absent — a chargeback at day 400 of a 120-day run is a real limitation
                # of the window, and the label-maturity report is how we express it.
                self.ctx.bump("followup_beyond_horizon")
                continue
            self._followups.setdefault(day, []).append(f)

    # ---- the issuer response ----------------------------------------------------------
    def _resolve_response(self, ev: CanonicalEvent, rng: np.random.Generator) -> None:
        """Decide the realised response. THE INCUMBENT HAS ALREADY DECIDED.

        If the incumbent declined, the event is declined and NEVER RECEIVES AN OUTCOME — which is
        the whole point of the policy shadow. If the incumbent accepted, ordinary issuer-side
        reasons (funds, expiry, card status) can still decline it.
        """
        # STRUCTURAL declines are resolved FIRST and win. A mandate-scope refusal is a structural
        # guard, and letting the incumbent relabel it `declined_risk` would (a) misreport the
        # reason to a reviewer and (b) break the invariant that an over-cap debit carries the
        # mandate-scope code. Order matters here and this is the whole reason it does.
        if ev.response_code in _STRUCTURAL_DECLINES:
            ev.approved = False
            ev.response_latency_ms = float(abs(rng.normal(42.0, 14.0)))
            self.ctx.bump("structural_decline")
            return
        if ev.message_kind == "collect_response" and not ev.collect_accepted:
            ev.approved = False
            ev.response_latency_ms = float(abs(rng.normal(51.0, 18.0)))
            return

        if ev.incumbent_decision == "decline":
            ev.approved = False
            ev.response_code = (
                "declined_risk" if "INC" in ev.incumbent_rule_fired else "declined_do_not_honour"
            )
            ev.response_latency_ms = float(abs(rng.normal(38.0, 12.0)))
            self.ctx.bump("incumbent_declined")
            return

        u = rng.random()
        if ev.cvv2_result == "no_match" and u < 0.55:
            ev.approved = False
            ev.response_code = "declined_cvv2_mismatch"
        elif ev.avs_result == "no_match" and u < 0.28:
            ev.approved = False
            ev.response_code = "declined_avs_mismatch"
        elif u < 0.028:
            ev.approved = False
            ev.response_code = "declined_insufficient_funds"
        elif u < 0.036:
            ev.approved = False
            ev.response_code = "declined_invalid_card"
        elif ev.rail in _STEP_UP_RAILS and u < 0.052:
            ev.approved = False
            ev.response_code = "step_up_required"
        else:
            ev.approved = True
            ev.response_code = "approved"
        ev.response_latency_ms = float(abs(rng.normal(46.0, 17.0)))

    # ---- post-processing per event ----------------------------------------------------
    def _finalise(
        self,
        ev: CanonicalEvent,
        rng: np.random.Generator,
        *,
        attack: dict[str, Any] | None,
    ) -> list[CanonicalEvent]:
        """Run policy, response, lifecycle, beneficiary leg and labels for one event.

        Returns any ADDITIONAL events produced synchronously (the beneficiary credit leg and the
        pacs.002 status), which must be finalised too but must not recurse.
        """
        ev.generator = self.generator
        ch = self.world.cardholders.get(ev.cardholder_id)
        if ch is not None:
            ev.entity_pool = ch.pool
        elif ev.beneficiary_id:
            ben = self.world.beneficiaries.get(ev.beneficiary_id)
            if ben is not None:
                ev.entity_pool = ben.pool
        extra: list[CanonicalEvent] = []

        if ev.message_kind in DECISIONABLE_KINDS:
            # 1. incumbent policy shadow — BEFORE the issuer response, because its decline is what
            #    makes the training population approval-conditioned.
            self.incumbent.apply(ev, self._incumbent_rng)
            self._accept_probs.append(ev.incumbent_accept_probability)
            # 2. issuer response
            self._resolve_response(ev, rng)
        else:
            # Informational or derived messages inherit their outcome from what they resolve to.
            # They still carry a MEASURED processing latency, because every message that carries a
            # response code has one and a sentinel there would mean "we did not measure it".
            ev.response_latency_ms = float(abs(rng.normal(21.0, 8.0)))

        # 3. lifecycle — AFTER the response, because only an approved auth has a presentment.
        self._schedule(schedule_card_lifecycle(self.ctx, ev, rng, attack=attack))

        # 3b. refunds. A first-class refund message with a mandatory original-auth reference is
        #     what makes ATK-V2 and ATK-A2 buildable at all.
        if ev.approved and ev.message_kind == "authorisation":
            if attack and str(attack.get("monetisation", "")) == "refund-chargeback-recovery":
                f = schedule_refund(
                    self.ctx, ev.event_id, rng,
                    day_offset=int(rng.integers(1, 9)),
                    fraction=1.0,
                    exceed=bool(rng.random() < 0.35),
                    to_different_credential=bool(rng.random() < 0.4),
                    attack=attack,
                )
                self._schedule([f] if f else [])
            elif rng.random() < 0.017:
                f = schedule_refund(self.ctx, ev.event_id, rng, day_offset=int(rng.integers(1, 21)))
                self._schedule([f] if f else [])

        # 4. beneficiary leg — only on approved events on a rail that has one.
        ben_id = str(ev._scratch.get("beneficiary_id", "") or "")
        if ev.approved and ben_id and ben_id in self.world.beneficiaries:
            credit, onward = emit_inbound_credit(
                self.ctx, ev, ben_id, rng,
                attack=attack,
                dwell_seconds=ev._scratch.get("dwell_seconds"),
                skim=float(ev._scratch.get("skim", 0.0)),
            )
            credit.entity_pool = ev.entity_pool
            extra.append(credit)
            if onward is not None:
                self._schedule([onward])

        # 4b. pacs.002 status for the A2A rail.
        if ev.rail == "a2a-credit-transfer" and ev.message_kind == "credit_transfer":
            st = emit_pacs_status(self.ctx, ev, rng, accepted=ev.approved)
            st.entity_pool = ev.entity_pool
            extra.append(st)

        # 5. labels. `alerted` is a proxy at generation time: the real alert decision belongs to
        #    GATE, but the analyst channel needs SOMETHING to have raised a case. We use the
        #    incumbent's decline plus a small random sample of approvals, which is what a legacy
        #    stack's queue actually contains.
        alerted = bool(
            ev.incumbent_decision == "decline"
            or (ev.oracle_is_attack and rng.random() < 0.35)
            or rng.random() < 0.004
        )
        if ev.message_kind not in ("balance_enquiry", "pre_debit_notification", "collect_request"):
            self.labels.observe(
                event_id=ev.event_id,
                event_ts=ev.ts,
                day_index=ev.day_index,
                oracle_is_attack=ev.oracle_is_attack,
                label_morpheme=str(attack.get("label", "")) if attack else "",
                alerted=alerted,
                dispute_filed_ts=ev.dispute_filed_ts,
                poisons_channel=bool(attack and str(attack.get("label", "")) == "label-poisoned"),
                rng=self._label_rng,
            )
        return extra

    # ---- the day loop -----------------------------------------------------------------
    def run(self, campaigns: Sequence[CampaignSpec] | None = None) -> SimResult:
        t0 = time.perf_counter()
        campaigns = list(campaigns or [])
        by_day: dict[int, list[CampaignSpec]] = {}
        for c in campaigns:
            for d in range(c.start_day, min(self.n_days, c.start_day + c.duration_days)):
                by_day.setdefault(d, []).append(c)

        out: list[CanonicalEvent] = []
        cohort_plan = self._plan_cohorts()
        # Campaign-days STRICTLY AFTER each day, so the controller can solve for the factor that
        # delivers the remaining attack budget over the remaining campaign-days.
        self._campaign_days_after = [0] * (self.n_days + 1)
        for d in range(self.n_days - 1, -1, -1):
            self._campaign_days_after[d] = self._campaign_days_after[d + 1] + len(by_day.get(d, []))

        for day in range(self.n_days):
            self.ctx.day = day
            advance_lifecycle(self._states, self._dormant_since, day, self._lifecycle_rng, self.cfg)
            for cid, st in self._states.items():
                self.world.cardholders[cid].state = st

            # (2) today's due follow-ups FIRST, so a presentment for yesterday lands before
            #     today's traffic and the lifecycle is in order for any sequence feature.
            for f in self._followups.pop(day, []):
                for ev in f.builder(self.ctx):
                    out.append(ev)
                    # `attack=None` here was unconditional, so a followup on an ATTACK chain was
                    # finalised as benign traffic: no attack-conditional lifecycle scheduling, and
                    # the mule/sweep legs of an attack mandate debit drew from the shared benign RNG.
                    # The event now carries its own provenance (via `link_to_auth`), so we reconstruct
                    # the minimum attack dict `_finalise` consumes rather than asserting innocence.
                    out.extend(
                        self._finalise(ev, self._benign_rng, attack=_attack_from_event(ev))
                    )

            mult = self.calendar.volume_multiplier(day)

            # (3) benign traffic
            for cid in self.world.active_cardholders(day):
                habit = self.habits[cid]
                lam = habit.daily_rate * mult
                n = int(self._benign_rng.poisson(lam))
                if n <= 0:
                    continue
                for _ in range(n):
                    rail = self._pick_rail(habit, self._benign_rng)
                    res = emitter_for(rail).emit(
                        self.ctx, cid, day, self._benign_rng, attack=None, cohort_tag="ordinary"
                    )
                    self._schedule(res.followups)
                    for ev in res.events:
                        out.append(ev)
                        out.extend(self._finalise(ev, self._benign_rng, attack=None))

            # (4) HARD-BENIGN cohorts
            for spec, cid, rail in cohort_plan.get(day, []):
                rng = self._cohort_rng if spec.tag.startswith("hb12_") else self._cohort_b_rng
                res = emitter_for(rail).emit(
                    self.ctx, cid, day, rng, attack=None, cohort_tag=spec.tag
                )
                self._schedule(res.followups)
                for ev in res.events:
                    spec.mutate(ev, rng)
                    out.append(ev)
                    out.extend(self._finalise(ev, rng, attack=None))

            # (5) attack campaigns, volume tracked to the CONFIGURED base rate by a CAUSAL
            #     controller. `attack/campaigns.py` can only ESTIMATE benign volume ahead of the run,
            #     and that estimate was fitted at the smoke preset where a FIXED-SIZE hard-benign
            #     cohort set is 65.6% of the stream. At the full preset the same cohorts are ~3%, so
            #     the fitted multiplier over-counted benign volume 2.66x and the realised attack share
            #     came out 4.1x the configured 0.5%. No constant can be right at every horizon, so we
            #     stop fitting one: the controller measures benign volume ALREADY EMITTED and steers
            #     the remaining campaign volume toward the target share.
            #
            #     IT USES ONLY THE PAST. Days 0..day are already emitted when this runs, so there is
            #     no forward information and no leakage -- and it is volume accounting, never a
            #     defender signal. Attack STRUCTURE is untouched; only how many events a campaign-day
            #     emits is modulated, which was always a parameter.
            self._retune_attack_volume(day, len(out))
            for c in by_day.get(day, []):
                batch = self._run_campaign_day(c, day)
                # Counted INCREMENTALLY. Rescanning `out` each day would be O(n) per day, which at
                # the full preset is ~600M attribute reads across the run for a number we can simply
                # accumulate.
                self._n_attack_emitted += sum(1 for e in batch if e.oracle_is_attack)
                out.extend(batch)

            self._emitted = len(out)

        # Deterministic output order: by timestamp, then by event id. Follow-ups are generated
        # out of order by construction, and a stable sort is what makes the Parquet hash stable.
        out.sort(key=lambda e: (e.ts, e.event_id))

        # The application transaction counter must be monotone per card IN CHRONOLOGICAL ORDER,
        # and events are emitted per cardholder rather than per clock — a card's two transactions
        # on one day are drawn at random hours. So the counter is assigned in a post-pass over the
        # SORTED stream. Assigning it at emission time is what made the ATC invariant fail: the
        # numbers were monotone in emission order and non-monotone in the order anyone reads them.
        self._renumber_atc(out)

        elapsed = time.perf_counter() - t0
        return SimResult(
            events=out,
            labels=self.labels,
            world=self.world,
            ctx=self.ctx,
            report=self._build_report(out, elapsed, campaigns),
        )

    # ---- helpers ----------------------------------------------------------------------
    @staticmethod
    def _renumber_atc(events: list[CanonicalEvent]) -> None:
        """Assign the EMV application transaction counter in chronological order, per card.

        Two behaviours, and the difference between them is the point:

        *   an ORDINARY cryptogram gets the next counter for its card, so monotonicity holds by
            construction and the F1 invariant cannot be violated by emission order;
        *   an event marked `atc_replay` (a deliberate ATK-P2 cryptogram replay) is given the
            card's CURRENT counter, so it duplicates rather than advances. That is the attack's
            observable signature, and it is why the F1 ATC invariant is scoped to non-attack
            events by name rather than by silently excluding all attack rows.

        The per-card starting value is derived from the PAN so cards do not all start at 1 — a
        real card in the wild has history — and the derivation is a hash, so it is deterministic.
        """
        import hashlib

        last: dict[str, int] = {}
        for ev in events:
            if not ev.emv_cryptogram_present or ev.emv_cryptogram_atc < 0:
                continue
            pan = ev.pan_canonical
            if pan not in last:
                seed = hashlib.blake2b(pan.encode("utf-8"), digest_size=2).digest()
                last[pan] = 20 + int.from_bytes(seed, "big") % 900
            if ev._scratch.get("atc_replay"):
                ev.emv_cryptogram_atc = last[pan]
            else:
                last[pan] += 1
                ev.emv_cryptogram_atc = last[pan]

    def _pick_rail(self, habit: Habit, rng: np.random.Generator) -> str:
        rails = [r for r in self._sampled_rails if r in EMITTERS]
        w = np.asarray([max(1e-9, habit.rail_weights.get(r, 1e-6)) for r in rails], dtype=np.float64)
        w = w / w.sum()
        return rails[int(rng.choice(len(rails), p=w))]

    def _retune_attack_volume(self, day: int, n_emitted_total: int) -> None:
        """Solve for the volume factor that lands the run on the configured base rate.

        SOLVED ABSOLUTELY, NOT COMPOUNDED. A multiplicative controller (`factor *= adjustment`)
        ratchets: campaigns start on staggered days, so early days under-deliver, the adjustment
        saturates at its cap every day, and the factor walks to the ceiling -- which drove the smoke
        preset to a 1.92% realised share against a 0.5% target. Solving for the factor directly from
        the remaining budget and the remaining campaign-days has no such memory.

        Uses only days 0..`day`, which are already emitted, so there is no forward information. It is
        volume accounting and never a defender signal. Attack STRUCTURE is untouched.

        The realised share is still MEASURED AND PRINTED beside the configured one; this makes them
        agree in the ordinary case rather than turning the configured value into a guarantee.
        """
        elapsed = day + 1
        if elapsed < _ATTACK_TUNE_WARMUP_DAYS or elapsed >= self.n_days:
            return
        remaining_cd = self._campaign_days_after[elapsed]
        if remaining_cd <= 0 or self._campaign_day_factor_sum <= 0.0:
            return
        n_attack = self._n_attack_emitted
        if n_attack <= 0:
            return
        n_benign = max(1, n_emitted_total - n_attack)
        br = float(self.cfg.base_rate)
        projected_benign = n_benign * (self.n_days / elapsed)
        target_total = br * projected_benign / max(1e-9, 1.0 - br)
        remaining_target = target_total - n_attack
        if remaining_target <= 0.0:
            self._attack_volume_factor = 0.05
            self.ctx.bump("attack_volume_retune")
            return
        # Attack events per campaign-day per UNIT of factor, measured from what actually happened.
        unit = n_attack / self._campaign_day_factor_sum
        if unit <= 0.0:
            return
        self._attack_volume_factor = float(
            np.clip(remaining_target / (remaining_cd * unit), 0.05, 20.0)
        )
        self.ctx.bump("attack_volume_retune")

    def _plan_cohorts(self) -> dict[int, list[tuple[CohortSpec, str, str]]]:
        """Pre-plan cohort events per day, so their volume is a FIXED authored set.

        Fixed rather than a share of traffic: the cohorts are hand-authored adversarial cases, and
        their count is what the minimum-detectable-effect arithmetic is computed against. A
        previous build carried a `hard_benign_12_share` config key that nothing consumed, so the
        F3 assertion measured 0.0018 against a config value of 0.035 — an assertion about a
        quantity the generator never produced. There is no such key now.
        """
        ccfg = self.cfg.scenario["cohorts"]
        n12 = int(ccfg["hard_benign_12_rows_per_cohort"])
        nb = int(ccfg["hard_benign_b_rows_per_cohort"])
        plan: dict[int, list[tuple[CohortSpec, str, str]]] = {}
        ch_ids = self.world.cardholder_ids()
        if not ch_ids:
            return plan

        # Payer-side cohorts ride the rails their attack twin rides.
        rail_for_12 = {
            "hb12_bereavement": "card-cnp-keyed",
            "hb12_wedding": "card-cnp-3ds",
            "hb12_relocation": "card-cp-emv",
            "hb12_new_phone_reprovision": "card-token-provisioning",
            "hb12_gig_fanin": "upi-pay",
            "hb12_festival_travel": "card-cnp-3ds",
            "hb12_first_high_ticket": "card-cnp-3ds",
            "hb12_joint_account": "card-cp-emv",
            "hb12_seasonal_merchant_ramp": "upi-collect",
            "hb12_student_fee": "upi-collect",
            "hb12_nri_remittance": "a2a-credit-transfer",
            "hb12_medical_fd_liquidation": "a2a-credit-transfer",
        }
        rail_for_b = {
            "hbb_new_gig_aggregator_payee": "upi-pay",
            "hbb_week_old_small_merchant": "upi-collect",
            "hbb_school_fee_collection": "upi-collect",
            "hbb_festival_street_vendor": "upi-pay",
            "hbb_community_chit_collection": "upi-pay",
            "hbb_freelancer_foreign_inbound": "a2a-credit-transfer",
        }

        rng = stream("sim.cohorts.hard_benign_12")
        for spec in HARD_BENIGN_12:
            rail = rail_for_12[spec.tag]
            for _ in range(n12):
                day = int(rng.integers(0, self.n_days))
                cid = ch_ids[int(rng.integers(0, len(ch_ids)))]
                plan.setdefault(day, []).append((spec, cid, rail))
        rngb = stream("sim.cohorts.hard_benign_b")
        for spec in HARD_BENIGN_B:
            rail = rail_for_b[spec.tag]
            for _ in range(nb):
                day = int(rngb.integers(0, self.n_days))
                cid = ch_ids[int(rngb.integers(0, len(ch_ids)))]
                plan.setdefault(day, []).append((spec, cid, rail))
        return plan

    def _run_campaign_day(self, c: CampaignSpec, day: int) -> list[CanonicalEvent]:
        """Execute one campaign's events for one day, under its OWN RNG stream.

        The separate stream is control #2 of the sealed-family protocol: a held-out family's draws
        cannot correlate with training data through shared generator state, so adding a training
        campaign cannot shift a sealed family's numbers.
        """
        rng = substream("attack.campaign", f"{c.campaign_id}:{day}")
        # ENTITY-LEVEL HOLDOUT. A sealed campaign draws its victims ONLY from the sealed pool, and a
        # trainable campaign only from the train pool. Without this, a sealed family's cardholders,
        # devices and beneficiaries appear in the training set through their benign traffic, the model
        # learns their aggregates including the run-up to the attack, and the "holdout" is a holdout
        # of labels rather than of information. `eval/leakage.py::entity_audit` fails the build if the
        # partition is not respected.
        pool = "sealed" if c.sealed else "train"
        ch_ids = self.world.active_cardholders(day, pool=pool) or self.world.cardholders_in_pool(pool)
        if not ch_ids:
            self.ctx.bump(f"campaign_no_victims_in_pool:{pool}")
            return []
        rail = c.rail if c.rail in EMITTERS else "card-cnp-keyed"
        stage_idx = min(len(c.stages) - 1, max(0, day - c.start_day))
        stage = c.stages[stage_idx] if c.stages else "extract"
        attack = c.attack_dict(stage)

        fan = int(c.arm.get("fan_out", 1) or 1)
        n = max(1, int(round(c.events_per_day * self._attack_volume_factor)))
        # Factor-weighted campaign-day count, so the controller can measure attack events per
        # campaign-day PER UNIT OF FACTOR and invert it without assuming the factor was constant.
        self._campaign_day_factor_sum += self._attack_volume_factor
        out: list[CanonicalEvent] = []
        for _ in range(n):
            # Fan-out spreads the campaign across distinct victims/entities, which is what
            # cohort-splitting and velocity-splitting actually do.
            for _f in range(max(1, min(fan, 6))):
                cid = ch_ids[int(rng.integers(0, len(ch_ids)))]
                res = emitter_for(rail).emit(
                    self.ctx, cid, day, rng, attack=attack, cohort_tag="ordinary"
                )
                self._schedule(res.followups)
                for ev in res.events:
                    out.append(ev)
                    out.extend(self._finalise(ev, rng, attack=attack))
        self.ctx.bump(f"campaign:{c.family_id}", len(out))
        return out

    # ---- reporting --------------------------------------------------------------------
    def _build_report(
        self, events: Sequence[CanonicalEvent], elapsed: float, campaigns: Sequence[CampaignSpec]
    ) -> dict[str, Any]:
        by_rail: dict[str, int] = {}
        by_kind: dict[str, int] = {}
        by_cohort: dict[str, int] = {}
        n_attack = 0
        n_approved = 0
        n_sealed = 0
        for ev in events:
            by_rail[ev.rail] = by_rail.get(ev.rail, 0) + 1
            by_kind[ev.message_kind] = by_kind.get(ev.message_kind, 0) + 1
            by_cohort[ev.cohort_tag] = by_cohort.get(ev.cohort_tag, 0) + 1
            n_attack += int(ev.oracle_is_attack)
            n_approved += int(ev.approved)
            n_sealed += int(ev.sealed_holdout)

        ccfg = self.cfg.scenario["cohorts"]
        return {
            "preset": self.preset,
            "generator": self.generator,
            "n_events": len(events),
            "n_days": self.n_days,
            "wall_clock_seconds": round(elapsed, 2),
            "events_by_rail": dict(sorted(by_rail.items())),
            "events_by_message_kind": dict(sorted(by_kind.items())),
            "events_by_cohort": dict(sorted(by_cohort.items())),
            "n_attack_events": n_attack,
            "realised_attack_share": (n_attack / len(events)) if events else 0.0,
            "configured_base_rate": self.cfg.base_rate,
            "n_approved": n_approved,
            "approval_rate": (n_approved / len(events)) if events else 0.0,
            "n_sealed_holdout_events": n_sealed,
            "entity_pool_counts": {
                p: int(sum(1 for e in events if e.entity_pool == p))
                for p in sorted({e.entity_pool for e in events})
            },
            "entity_pool_note": (
                "Benign traffic and the HARD-BENIGN cohorts cover BOTH pools deliberately. A sealed "
                "pool whose every event was an attack would be trivially separable, which would be a "
                "worse leak than the aggregate leak the partition fixes."
            ),
            "n_campaigns": len(campaigns),
            "world": self.world.summary(),
            "labels": self.labels.report(),
            "propensity_histogram": propensity_histogram(np.asarray(self._accept_probs)),
            "cohort_sizing": sizing_report(
                int(ccfg["hard_benign_12_rows_per_cohort"]),
                int(ccfg["hard_benign_b_rows_per_cohort"]),
            ),
            "calendar": self.calendar.describe(),
            "expected_dow_share": self.calendar.expected_dow_share(),
            "emitter_counters": dict(sorted(self.ctx.counters.items())),
            "followups_pending_at_end": sum(len(v) for v in self._followups.values()),
        }


def run_sim(
    preset: str | None = None,
    campaigns: Sequence[CampaignSpec] | None = None,
    cfg: Config | None = None,
    *,
    generator: str = "vajra-sim",
) -> SimResult:
    return Engine(preset=preset, cfg=cfg, generator=generator).run(campaigns)
