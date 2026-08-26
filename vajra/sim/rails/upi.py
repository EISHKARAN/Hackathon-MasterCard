"""Tier-A UPI rails: PAY, COLLECT, AutoPay mandate.

THE THING THAT MAKES THESE DIFFERENT FROM THE CARD RAILS: they have a **beneficiary leg**. An
inbound credit lands on a receiving account, and that account must eventually move money onward.
That is the only enforceable control point in an authorised push payment, where every payer-side
signal is genuine — correct device, correct binding, correct PIN, correct customer present.

So each emitter here produces the payer-side message AND the beneficiary-side `inbound_credit`,
and updates the receiving account's running state (inflow, outflow, payer set, dwell) that the
GATE-B inbound-credit scorer reads. Emitting only the payer leg would make GATE-B unscoreable and
would quietly reduce this submission to a payer-side-only design.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from sim.graph.entities import Beneficiary, Mandate
from sim.rails.base import (
    EmitResult,
    Followup,
    SimContext,
    apply_attack_provenance,
    hug_threshold,
)
from sim.schema import CanonicalEvent

#: Rupee thresholds that matter on UPI. ALL [VERIFY] and all swept config-shaped values; here
#: they are geometry for `distance_to_nearest_threshold`, never asserted as current rule state.
UPI_THRESHOLDS: tuple[float, ...] = (500.0, 2_000.0, 5_000.0, 15_000.0, 100_000.0)

#: The AFA-exempt band an e-mandate debit can be pinned under. [VERIFY current threshold] —
#: modelled as a swept parameter, never spoken as fact.
AFA_EXEMPT_BAND_INR = 15_000.0

_NOTE_TEMPLATES: tuple[str, ...] = (
    "payment", "thanks", "bill", "rent", "fees", "order", "refund", "advance", "settle", "gift",
)


def nearest_upi_threshold(amount: float) -> tuple[float, float]:
    best = min(UPI_THRESHOLDS, key=lambda t: abs(t - amount))
    return best, float(amount - best)


def pick_beneficiary(
    ctx: SimContext,
    cardholder_id: str,
    rng: np.random.Generator,
    *,
    fresh: bool = False,
    category: str | None = None,
) -> str:
    """Choose a payee. `fresh=True` mints a brand-new receiving account.

    Freshness is the observable that matters most on this rail: a new-payee-age near zero with an
    instant sweep-out is the QR-swap / coercion signature. It is ALSO an exact description of a
    legitimate new gig payee or a week-old small merchant, which is why HARD-BENIGN-B exists and
    why `false_freeze_rate` is a headline metric next to recall.
    """
    ch = ctx.world.cardholders[cardholder_id]
    if not fresh and ch.beneficiaries and rng.random() < 0.86:
        bid = ch.beneficiaries[int(rng.integers(0, len(ch.beneficiaries)))]
        cand = ctx.world.beneficiaries.get(bid)
        # Same-pool only. A beneficiary shared across the train/sealed partition would bridge the
        # entity-level holdout boundary through its inflow aggregate.
        if cand is not None and cand.pool == ch.pool:
            return bid
    bid = f"BENX{ctx.mint_event_id('')}"
    ctx.world.beneficiaries[bid] = Beneficiary(
        id=bid,
        payee_vpa=f"payee{bid.lower()}@vjpsp",
        payee_name=f"PAYEE {bid[-6:]}",
        psp_id=ctx.world.psps[int(rng.integers(0, len(ctx.world.psps)))],
        open_day=ctx.day,
        category=category or "p2p_individual",
        geo_cell=ch.geo_cell,
        pool=ch.pool,
    )
    if bid not in ch.beneficiaries:
        ch.beneficiaries.append(bid)
    ctx.bump("fresh_beneficiary_minted")
    return bid


def emit_inbound_credit(
    ctx: SimContext,
    payer_event: CanonicalEvent,
    beneficiary_id: str,
    rng: np.random.Generator,
    *,
    attack: dict[str, Any] | None = None,
    dwell_seconds: float | None = None,
    skim: float = 0.0,
) -> tuple[CanonicalEvent, Followup | None]:
    """The beneficiary-side leg, plus the onward send that determines dwell.

    `skim` is the fraction the mule retains. VALUE CONSERVATION NET OF A SKIM is the ATK-G1/G2
    observable, and a tight in-out skew is the mule signature — with the threshold a swept
    simulator parameter, not an empirical constant.
    """
    ben = ctx.world.beneficiaries[beneficiary_id]
    ev = ctx.new_event(
        rail=payer_event.rail,
        message_kind="inbound_credit",
        tier=payer_event.tier,
        day_index=payer_event.day_index,
        hour_ist=payer_event.hour_ist,
        amount_inr=payer_event.amount_inr,
    )
    # Both pairing keys, so the inbound credit resolves to its payer leg under either indexer.
    ev.original_auth_event_id = payer_event.event_id
    ev.rrn = payer_event.rrn
    ev.trace_number = payer_event.trace_number
    ev.beneficiary_id = beneficiary_id
    ev.payee_vpa = ben.payee_vpa
    ev.payee_name_string = ben.payee_name
    ev.payee_psp_id = ben.psp_id
    ev.beneficiary_category = ben.category
    ev.beneficiary_kyc_tier = ben.kyc_tier
    ev.cardholder_id = payer_event.cardholder_id
    ev.vpa = payer_event.vpa
    ev.geo_cell = ben.geo_cell
    ev.cohort_tag = ben.cohort_tag if ben.cohort_tag != "ordinary" else payer_event.cohort_tag
    ev.upi_initiation_mode = payer_event.upi_initiation_mode
    ev.approved = True
    ev.response_code = "approved"
    # A beneficiary-side receipt is not re-decided, but it does carry a measured processing
    # latency: a sentinel there would mean "we did not measure it".
    ev.response_latency_ms = float(abs(rng.normal(18.0, 7.0)))

    # ---- update running beneficiary state (what GATE-B actually reads) -----------------
    first_credit = ben.first_credit_ts < 0
    if first_credit:
        ben.first_credit_ts = ev.ts
        ben.first_credit_source = payer_event.cardholder_id
    ben.last_credit_ts = ev.ts
    ben.inflow_inr += ev.amount_inr
    ben.payer_ids.add(payer_event.cardholder_id)

    ev.beneficiary_account_age_days = float(max(0.0, ctx.day - ben.open_day))
    ev.payee_vpa_age_days = ev.beneficiary_account_age_days
    ev.beneficiary_distinct_payers_24h = len(ben.payer_ids)
    ev.beneficiary_inbound_credit_count_24h = -1     # engine's sketch layer fills the real window
    ev.beneficiary_inflow_24h_inr = ben.inflow_inr
    ev.beneficiary_outflow_24h_inr = ben.outflow_inr
    ev.beneficiary_fanin_degree = len(ben.payer_ids)
    ev.beneficiary_first_credit_source = ben.first_credit_source
    apply_attack_provenance(ev, attack)
    if attack:
        ev.attack_stage = "cashout" if skim > 0 else str(attack.get("stage", "extract"))
    ctx.bump("inbound_credit")

    # ---- onward send ------------------------------------------------------------------
    if dwell_seconds is None:
        # Legitimate receivers hold money for hours or days; a mule holds it for minutes. Both
        # populations must exist or dwell is a perfect signal.
        dwell_seconds = float(abs(rng.normal(52_000.0, 40_000.0)))
    onward_amount = float(np.round(ev.amount_inr * (1.0 - float(skim)), 2))
    if onward_amount <= 0.0:
        return ev, None

    onward_hour_total = ev.hour_ist + dwell_seconds / 3600.0
    onward_day = ev.day_index + int(onward_hour_total // 24)
    onward_hour = float(onward_hour_total % 24.0)
    ev.beneficiary_dwell_seconds = float(dwell_seconds)
    ev.beneficiary_onward_send_minutes = float(dwell_seconds / 60.0)

    src_event_id = ev.event_id
    src_rrn = ev.rrn

    def build_onward(c: SimContext) -> list[CanonicalEvent]:
        b = c.world.beneficiaries.get(beneficiary_id)
        if b is None:
            return []
        # A frozen or held account cannot move money onward. This is the mechanism by which
        # GATE-B's freeze recommendation actually reduces `value_retained` in the attacker's P&L
        # — without it the reward would credit money the gate already took back, while the RL
        # agent simultaneously observes `account_frozen`, which is incoherent.
        now_ts = c.calendar.ts(onward_day, onward_hour)
        if b.frozen_until_ts > now_ts:
            c.bump("onward_send_blocked_by_freeze")
            return []
        o = c.new_event(
            rail=payer_event.rail,
            message_kind="onward_send",
            tier=payer_event.tier,
            day_index=onward_day,
            hour_ist=onward_hour,
            amount_inr=onward_amount,
        )
        o.original_auth_event_id = src_event_id
        o.rrn = src_rrn
        o.beneficiary_id = beneficiary_id
        o.payee_vpa = b.payee_vpa
        o.payee_psp_id = b.psp_id
        o.beneficiary_category = b.category
        o.vpa = b.payee_vpa
        o.geo_cell = b.geo_cell
        o.cohort_tag = ev.cohort_tag
        o.approved = True
        o.response_code = "approved"
        o.response_latency_ms = float(abs(rng.normal(19.0, 7.0)))
        o.beneficiary_dwell_seconds = float(dwell_seconds)
        o.beneficiary_onward_send_minutes = float(dwell_seconds / 60.0)
        b.outflow_inr += onward_amount
        o.beneficiary_inflow_24h_inr = b.inflow_inr
        o.beneficiary_outflow_24h_inr = b.outflow_inr
        o.beneficiary_account_age_days = float(max(0.0, onward_day - b.open_day))
        o.beneficiary_fanin_degree = len(b.payer_ids)
        o.beneficiary_fanout_degree = 1 + int(rng.integers(0, 3))
        o.beneficiary_first_credit_source = b.first_credit_source
        apply_attack_provenance(o, attack)
        if attack:
            o.attack_stage = "cashout"
        c.bump("onward_send")
        return [o]

    return ev, Followup(onward_day, "onward_send", build_onward, ev.event_id)


def _base_upi_event(
    ctx: SimContext,
    cardholder_id: str,
    day_index: int,
    hour: float,
    rng: np.random.Generator,
    *,
    rail: str,
    message_kind: str,
    amount: float,
    cohort_tag: str,
    tier: str = "A",
) -> CanonicalEvent:
    ch = ctx.world.cardholders[cardholder_id]
    devs = ch.devices
    dev_id = devs[int(rng.integers(0, len(devs)))] if devs else ""
    dev = ctx.world.devices.get(dev_id)

    ev = ctx.new_event(
        rail=rail, message_kind=message_kind, tier=tier,
        day_index=day_index, hour_ist=hour, amount_inr=amount,
    )
    ev.rrn = ctx.mint_rrn()
    ev.trace_number = ctx.mint_trace()
    ev.cardholder_id = cardholder_id
    ev.vpa = ch.vpa
    ev.issuer_id = ch.issuer_id
    ev.geo_cell = ch.geo_cell
    ev.device_fingerprint_id = dev_id
    if dev is not None:
        ev.device_model = dev.model
        ev.device_os = dev.os
        ev.device_age_days = float(max(0, day_index - dev.first_seen_day))
        ev.ip_asn = dev.asn
    ev.vpa_age_days = float(max(0, day_index - ch.open_day))
    ev.account_age_days = ev.vpa_age_days
    ev.kyc_tier = ch.kyc_tier
    ev.cohort_tag = cohort_tag
    ev.session_id = f"S{ctx.mint_event_id('')}"
    # UPI carries no card constructs, ever.
    ev.threeds_authentication_result = "not_applicable"
    ev.threeds_eci = "none"
    ev.threeds_field_population_score = -1.0
    ev.emv_cryptogram_present = False
    ev.avs_result = "not_requested"
    ev.cvv2_result = "not_provided"
    # The PIN already IS the additional factor on this rail.
    ev.cvm_result = "online_pin"
    ev.txn_note = _NOTE_TEMPLATES[int(rng.integers(0, len(_NOTE_TEMPLATES)))]
    return ev


class UpiPayEmitter:
    rail = "upi-pay"
    tier = "A"

    def emit(
        self,
        ctx: SimContext,
        cardholder_id: str,
        day_index: int,
        rng: np.random.Generator,
        *,
        attack: dict[str, Any] | None = None,
        cohort_tag: str = "ordinary",
    ) -> EmitResult:
        habit = ctx.habits[cardholder_id]
        hour = habit.sample_hour(rng)
        amount = habit.sample_amount(rng)
        a = attack or {}
        evasion, access, monet = a.get("evasion", ""), a.get("access", ""), a.get("monetisation", "")

        if evasion == "threshold-hugging":
            t, _ = nearest_upi_threshold(amount)
            amount = hug_threshold(amount, t, rng)
        elif evasion == "velocity-splitting":
            amount = float(np.round(amount / max(1.0, rng.uniform(2.5, 7.0)), 2))
        if a.get("amount_band"):
            amount = ctx.sample_amount_in_band(str(a["amount_band"]), rng)
        if access == "authorised-but-deceived-payer" and a.get("stage") == "extract":
            # Escalating amounts in one hours-long session: the coercion observable.
            amount = float(np.round(amount * rng.uniform(1.6, 9.0), 2))

        ev = _base_upi_event(
            ctx, cardholder_id, day_index, hour, rng,
            rail=self.rail, message_kind="authorisation", amount=amount, cohort_tag=cohort_tag,
        )
        ev.upi_initiation_mode = str(
            rng.choice(["intent", "qr_static", "qr_dynamic", "in_app", "secure_intent"],
                       p=[0.30, 0.24, 0.18, 0.22, 0.06])
        )
        ev.pos_entry_mode = {
            "intent": "intent", "secure_intent": "secure_intent",
            "qr_static": "qr_static", "qr_dynamic": "qr_dynamic", "in_app": "intent",
        }[ev.upi_initiation_mode]

        fresh = bool(
            access in ("authorised-but-deceived-payer", "synthetic-identity")
            or evasion in ("graph-camouflage", "cohort-splitting")
        )
        if not fresh and rng.random() < 0.06:
            fresh = True   # legitimate new payees exist and must
        cat = "crypto_onramp" if monet == "crypto-offramp" else None
        bid = pick_beneficiary(ctx, cardholder_id, rng, fresh=fresh, category=cat)
        ben = ctx.world.beneficiaries[bid]
        ev.beneficiary_id = bid
        ev.payee_vpa = ben.payee_vpa
        ev.payee_name_string = ben.payee_name
        ev.payee_psp_id = ben.psp_id
        ev.beneficiary_category = ben.category
        ev.payee_vpa_age_days = float(max(0.0, day_index - ben.open_day))
        ev.beneficiary_account_age_days = ev.payee_vpa_age_days

        if attack and access == "authorised-but-deceived-payer":
            ev.session_duration_minutes = float(abs(rng.normal(145.0, 70.0)))
            ev.in_app_dwell_seconds = float(abs(rng.normal(9.0, 0.7)))       # human-implausibly uniform
            ev.typing_cadence_score = float(np.clip(rng.normal(0.12, 0.05), 0.0, 1.0))
            ev.screen_share_app_present = bool(evasion == "velocity-splitting")
            ev.accessibility_permission = ev.screen_share_app_present
        else:
            ev.session_duration_minutes = float(abs(rng.normal(6.0, 4.0)))
            ev.in_app_dwell_seconds = float(abs(rng.normal(26.0, 18.0)))
            ev.typing_cadence_score = float(np.clip(rng.normal(0.62, 0.18), 0.0, 1.0))

        if evasion == "cohort-splitting":
            ev.referrer_domain = f"pay-{int(rng.integers(1000, 9999))}.example"
            ev.referrer_domain_age_days = float(np.round(rng.uniform(0.0, 9.0), 2))
            ev.payee_name_string = f"BRANDLIKE {int(rng.integers(100, 999))}"
        elif ev.upi_initiation_mode in ("intent", "in_app") and rng.random() < 0.22:
            # ORDINARY PAYMENT LINKS HAVE REFERRERS. `evasion` is only ever non-empty when `attack`
            # is set, so the branch above was attack-only and `referrer_domain_age_days` was the -1
            # sentinel on every benign row -- a one-sided perfect separator, exactly as for
            # `beneficiary_change_ts` above.
            #
            # Again the real signal survives and is the mechanism rather than the presence: a genuine
            # merchant's payment-link domain is ESTABLISHED (months to years), while the
            # cohort-splitting attack registers a FRESH one (0-9 days). The feature still separates on
            # domain AGE, which is what a real control looks at.
            ev.referrer_domain = f"pay-{int(rng.integers(10, 999))}.example"
            ev.referrer_domain_age_days = float(np.round(rng.uniform(120.0, 2600.0), 2))

        t, dist = nearest_upi_threshold(ev.amount_inr)
        ev._scratch["threshold"] = t
        ev._scratch["threshold_distance"] = dist
        ev._scratch["beneficiary_id"] = bid
        # A mule sweeps out in minutes; a legitimate receiver does not.
        if attack and monet in ("mule-chain-cashout", "biller-giftcard-resale", "crypto-offramp"):
            ev._scratch["dwell_seconds"] = float(abs(rng.normal(120.0, 70.0)))
            ev._scratch["skim"] = float(np.clip(rng.normal(0.03, 0.015), 0.0, 0.2))
            if evasion == "graph-camouflage":
                # `extend_dwell` / `randomise_skim` beneficiary-evasion arms: adapt against a
                # beneficiary gate rather than against the payer-side scorer.
                ev._scratch["dwell_seconds"] = float(abs(rng.normal(2_400.0, 1_500.0)))
                ev._scratch["skim"] = float(np.clip(rng.normal(0.11, 0.05), 0.0, 0.4))
        apply_attack_provenance(ev, attack)
        ctx.bump(f"emit:{self.rail}")
        return EmitResult(events=[ev])


class UpiCollectEmitter:
    """Payee-initiated pull. Payee-side fan-out is invisible to any single payer PSP."""

    rail = "upi-collect"
    tier = "A"

    def emit(
        self,
        ctx: SimContext,
        cardholder_id: str,
        day_index: int,
        rng: np.random.Generator,
        *,
        attack: dict[str, Any] | None = None,
        cohort_tag: str = "ordinary",
    ) -> EmitResult:
        habit = ctx.habits[cardholder_id]
        hour = habit.sample_hour(rng)
        amount = habit.sample_amount(rng)
        a = attack or {}
        evasion = a.get("evasion", "")
        if evasion == "threshold-hugging":
            t, _ = nearest_upi_threshold(amount)
            amount = hug_threshold(amount, t, rng)
        if a.get("amount_band"):
            amount = ctx.sample_amount_in_band(str(a["amount_band"]), rng)

        result = EmitResult()
        req = _base_upi_event(
            ctx, cardholder_id, day_index, hour, rng,
            rail=self.rail, message_kind="collect_request", amount=amount, cohort_tag=cohort_tag,
        )
        req.upi_initiation_mode = "collect"
        req.pos_entry_mode = "collect"
        req.collect_request_id = f"CR{ctx.mint_event_id('')}"
        # A collect request is not itself a debit, so it carries no CVM.
        req.cvm_result = "none"

        bid = pick_beneficiary(
            ctx, cardholder_id, rng,
            fresh=bool(attack and evasion in ("cohort-splitting", "graph-camouflage")),
            category="small_merchant",
        )
        ben = ctx.world.beneficiaries[bid]
        req.beneficiary_id = bid
        req.payee_vpa = ben.payee_vpa
        req.payee_name_string = ben.payee_name
        req.payee_psp_id = ben.psp_id
        req.beneficiary_category = ben.category
        req.payee_vpa_age_days = float(max(0.0, day_index - ben.open_day))
        apply_attack_provenance(req, attack)
        result.events.append(req)

        # Farmed collect requests have a HIGH decline:accept ratio — that ratio is the observable,
        # so both outcomes must be emitted.
        accept_p = 0.22 if attack else 0.74
        accepted = bool(rng.random() < accept_p)

        resp = _base_upi_event(
            ctx, cardholder_id, day_index, min(23.99, hour + abs(float(rng.normal(0.05, 0.03)))), rng,
            rail=self.rail, message_kind="collect_response", amount=amount, cohort_tag=cohort_tag,
        )
        resp.original_auth_event_id = req.event_id
        resp.rrn = req.rrn
        resp.trace_number = req.trace_number
        resp.collect_request_id = req.collect_request_id
        resp.collect_accepted = accepted
        resp.upi_initiation_mode = "collect"
        resp.pos_entry_mode = "collect"
        resp.beneficiary_id = bid
        resp.payee_vpa = ben.payee_vpa
        resp.payee_psp_id = ben.psp_id
        resp.beneficiary_category = ben.category
        resp.payee_vpa_age_days = req.payee_vpa_age_days
        resp.approved = accepted
        resp.response_code = "approved" if accepted else "declined_do_not_honour"
        resp.cvm_result = "online_pin" if accepted else "none"
        resp._scratch["beneficiary_id"] = bid if accepted else ""
        if accepted and attack:
            resp._scratch["dwell_seconds"] = float(abs(rng.normal(220.0, 140.0)))
            resp._scratch["skim"] = float(np.clip(rng.normal(0.05, 0.02), 0.0, 0.25))
        apply_attack_provenance(resp, attack)
        result.events.append(resp)

        ctx.bump(f"emit:{self.rail}")
        return result


class UpiAutopayMandateEmitter:
    """Mandate creation, pre-debit notification, then debits. Two stages minimum, by nature."""

    rail = "upi-autopay-mandate"
    tier = "A"

    def emit(
        self,
        ctx: SimContext,
        cardholder_id: str,
        day_index: int,
        rng: np.random.Generator,
        *,
        attack: dict[str, Any] | None = None,
        cohort_tag: str = "ordinary",
    ) -> EmitResult:
        habit = ctx.habits[cardholder_id]
        hour = habit.sample_hour(rng)
        a = attack or {}
        evasion = a.get("evasion", "")
        result = EmitResult()

        cap = float(np.round(max(120.0, habit.sample_amount(rng) * rng.uniform(1.1, 3.0)), 0))
        if evasion == "threshold-hugging" and attack:
            # ATK-M3: debits pinned just under the AFA-exempt band. The threshold value itself is
            # [VERIFY] and swept; what we model is the PINNING, not the number.
            cap = AFA_EXEMPT_BAND_INR
        bid = pick_beneficiary(
            ctx, cardholder_id, rng,
            fresh=bool(attack), category="small_merchant" if attack else None,
        )
        ben = ctx.world.beneficiaries[bid]

        mandate_id = f"MND{ctx.mint_event_id('')}"
        create = _base_upi_event(
            ctx, cardholder_id, day_index, hour, rng,
            rail=self.rail, message_kind="mandate_creation", amount=0.0, cohort_tag=cohort_tag,
        )
        create.upi_initiation_mode = "mandate"
        create.pos_entry_mode = "intent"
        create.mandate_id = mandate_id
        create.mandate_max_amount_inr = cap
        create.mandate_frequency = str(rng.choice(["monthly", "weekly", "as_presented"], p=[0.62, 0.24, 0.14]))
        create.mandate_permitted_mcc = ctx.world.merchants[ctx.sample_merchant(rng)].mcc
        create.mandate_created_ts = create.ts
        create.mandate_debit_count_to_date = 0
        create.cit_mit_indicator = "CIT"
        create.beneficiary_id = bid
        create.payee_vpa = ben.payee_vpa
        create.payee_psp_id = ben.psp_id
        create.payee_vpa_age_days = float(max(0.0, day_index - ben.open_day))
        create.approved = True
        create.response_code = "approved"
        apply_attack_provenance(create, attack)
        if attack:
            create.attack_stage = "establish"
        result.events.append(create)

        ctx.world.mandates[mandate_id] = Mandate(
            id=mandate_id,
            cardholder_id=cardholder_id,
            payee_id=bid,
            max_amount_inr=cap,
            frequency=create.mandate_frequency,
            permitted_mcc=create.mandate_permitted_mcc,
            created_ts=create.ts,
        )

        # mandate_to_first_debit_minutes ~ 0 is the consent-fatigue observable.
        gap_days = 0 if (attack and evasion == "threshold-hugging") else int(rng.integers(1, 26))
        n_debits = int(rng.integers(1, 4)) if not attack else int(rng.integers(3, 9))
        for k in range(n_debits):
            due = day_index + gap_days + k * (1 if attack else int(rng.integers(6, 32)))
            result.followups.append(
                self._schedule_debit(
                    mandate_id, due, k, rng, attack, cohort_tag,
                    creation_day=day_index, creation_hour=hour,
                )
            )

        ctx.bump(f"emit:{self.rail}")
        return result

    @staticmethod
    def _schedule_debit(
        mandate_id: str,
        due_day: int,
        index: int,
        rng: np.random.Generator,
        attack: dict[str, Any] | None,
        cohort_tag: str,
        *,
        creation_day: int,
        creation_hour: float,
    ) -> Followup:
        def build(c: SimContext) -> list[CanonicalEvent]:
            m = c.world.mandates.get(mandate_id)
            if m is None or m.revoked:
                c.bump("mandate_debit_skipped_revoked")
                return []
            ch = c.world.cardholders.get(m.cardholder_id)
            ben = c.world.beneficiaries.get(m.payee_id)
            if ch is None or ben is None:
                return []
            evasion = (attack or {}).get("evasion", "")
            hour = float(np.clip(rng.normal(9.0, 2.0), 0.0, 23.99))
            # The notification lands the day before the debit -- unless that would put it before
            # the mandate that authorises it, which happens when the mandate-to-first-debit gap is
            # zero (the ATK-M3 consent-fatigue observable). In that case both land on the creation
            # day, strictly after the creation hour.
            notify_day = max(creation_day, due_day - 1)
            if notify_day == creation_day:
                hour = float(min(23.0, max(hour, creation_hour + 0.25)))
            events: list[CanonicalEvent] = []

            # Pre-debit notification. Its presence is what makes the debit "validly authorised
            # and pre-notified", which is exactly why ATK-M3 is hard.
            notify = _base_upi_event(
                c, m.cardholder_id, notify_day, hour, rng,
                rail="upi-autopay-mandate", message_kind="pre_debit_notification",
                amount=0.0, cohort_tag=cohort_tag,
            )
            notify.mandate_id = mandate_id
            notify.mandate_max_amount_inr = m.max_amount_inr
            notify.mandate_frequency = m.frequency
            notify.mandate_permitted_mcc = m.permitted_mcc
            notify.mandate_created_ts = m.created_ts
            notify.mandate_debit_count_to_date = m.debit_count
            notify.pre_debit_notification_sent = True
            notify.upi_initiation_mode = "mandate"
            notify.pos_entry_mode = "intent"
            notify.cvm_result = "none"
            notify.beneficiary_id = m.payee_id
            notify.payee_vpa = ben.payee_vpa
            notify.payee_psp_id = ben.psp_id
            notify.approved = True
            notify.response_code = "approved"
            apply_attack_provenance(notify, attack)
            events.append(notify)

            # The debit itself. Mandate-scope escalation pushes amount just under the cap; an
            # OVER-ENVELOPE debit is forced to DECLINE, because the mandate envelope is a G0
            # structural guard and an F1 invariant, not a risk score.
            over_envelope = bool(attack and evasion == "threshold-hugging" and index >= 4)
            if over_envelope:
                amount = float(np.round(m.max_amount_inr * rng.uniform(1.02, 1.4), 2))
            else:
                amount = float(np.round(m.max_amount_inr * rng.uniform(0.55, 0.995), 2))

            debit_day = max(due_day, notify_day)
            debit_hour = float(min(23.99, hour + 0.5)) if debit_day == notify_day else hour
            debit = _base_upi_event(
                c, m.cardholder_id, debit_day, debit_hour, rng,
                rail="upi-autopay-mandate", message_kind="mandate_debit",
                amount=amount, cohort_tag=cohort_tag,
            )
            debit.original_auth_event_id = notify.event_id
            debit.rrn = notify.rrn
            debit.trace_number = notify.trace_number
            debit.mandate_id = mandate_id
            debit.mandate_max_amount_inr = m.max_amount_inr
            debit.mandate_frequency = m.frequency
            debit.mandate_permitted_mcc = m.permitted_mcc
            debit.mandate_created_ts = m.created_ts
            debit.mandate_debit_count_to_date = m.debit_count
            debit.pre_debit_notification_sent = True
            debit.cit_mit_indicator = "MIT"
            debit.upi_initiation_mode = "mandate"
            debit.pos_entry_mode = "intent"
            debit.cvm_result = "none"        # MIT: no cardholder present, so no CVM
            debit.mcc = m.permitted_mcc
            if attack and evasion == "trust-inheritance":
                # MCC drift outside mandate scope: valid debit, wrong category.
                debit.mcc = c.world.merchants[c.sample_merchant(rng)].mcc
            debit.beneficiary_id = m.payee_id
            debit.payee_vpa = ben.payee_vpa
            debit.payee_psp_id = ben.psp_id
            debit.beneficiary_category = ben.category
            debit.payee_vpa_age_days = float(max(0.0, debit_day - ben.open_day))
            if over_envelope:
                debit.approved = False
                debit.response_code = "declined_mandate_scope"
                c.bump("mandate_over_envelope_declined")
            else:
                debit.approved = True
                debit.response_code = "approved"
                m.debit_count += 1
                m.cumulative_inr += amount
                debit._scratch["beneficiary_id"] = m.payee_id
            apply_attack_provenance(debit, attack)
            if attack:
                debit.attack_stage = "extract"
            events.append(debit)

            # Rising revocation rate alongside continued creation is the ATK-M3 observable.
            if rng.random() < (0.14 if attack else 0.02):
                m.revoked = True
                c.bump("mandate_revoked")
            return events

        return Followup(due_day, "mandate_debit", build, mandate_id)


UPI_EMITTERS = (UpiPayEmitter(), UpiCollectEmitter(), UpiAutopayMandateEmitter())
