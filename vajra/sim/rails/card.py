"""Tier-A card rails, emitted at message level.

Five emitters:
    card-cnp-3ds             authorisation + 3DS authentication block
    card-cnp-keyed           authorisation, NO authentication block, NO cryptogram
    card-cp-emv              authorisation + EMV cryptogram block (monotone ATC)
    card-clearing-dispute    presentment / refund / chargeback / representment — DERIVED ONLY
    card-token-provisioning  provisioning request + first tokenised spend

`card-clearing-dispute` is never sampled independently. It is produced as a FOLLOW-UP of an
authorisation, which is what makes the F1 invariant "every presentment resolves to an auth"
satisfiable by construction rather than by patching.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from sim.graph.builder import quasi_cash_mccs
from sim.rails.base import (
    AuthRecord,
    EmitResult,
    Followup,
    SimContext,
    apply_attack_provenance,
    hug_threshold,
)
from sim.schema import HOUR_MAX, CanonicalEvent

_UA_FAMILIES = ("uaA", "uaB", "uaC", "uaD", "uaE")
_LANGS = ("en-IN", "hi-IN", "ta-IN", "te-IN", "mr-IN", "bn-IN")
_SCREENS = ("360x800", "390x844", "412x915", "414x896", "1280x720", "1920x1080")

#: Policy thresholds the incumbent enforces, in INR. Swept config values in real deployments;
#: here they are the geometry that `distance_to_nearest_threshold` measures against.
POLICY_THRESHOLDS: tuple[float, ...] = (2_000.0, 5_000.0, 15_000.0, 50_000.0, 100_000.0)


def nearest_threshold(amount: float) -> tuple[float, float]:
    """(threshold, signed distance). The Policy-threshold-geometry feature family's primitive."""
    best = min(POLICY_THRESHOLDS, key=lambda t: abs(t - amount))
    return best, float(amount - best)


def _pick_device(ctx: SimContext, cardholder_id: str, rng: np.random.Generator) -> str:
    devs = ctx.world.cardholders[cardholder_id].devices
    return devs[int(rng.integers(0, len(devs)))] if devs else ""


def _base_card_event(
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
) -> CanonicalEvent:
    ch = ctx.world.cardholders[cardholder_id]
    mid = ctx.sample_merchant(rng)
    mer = ctx.world.merchants[mid]
    dev_id = _pick_device(ctx, cardholder_id, rng)
    dev = ctx.world.devices.get(dev_id)

    ev = ctx.new_event(
        rail=rail,
        message_kind=message_kind,
        tier="A",
        day_index=day_index,
        hour_ist=hour,
        amount_inr=amount,
    )
    ev.rrn = ctx.mint_rrn()
    ev.trace_number = ctx.mint_trace()
    ev.cardholder_id = cardholder_id
    ev.pan_canonical = ch.pan_canonical
    ev.bin_prefix = ch.bin_prefix
    ev.issuer_id = ch.issuer_id
    ev.merchant_id = mid
    ev.acquirer_id = mer.acquirer_id
    ev.mcc = mer.mcc
    ev.acceptor_descriptor = mer.descriptor
    ev.acceptor_country = mer.country
    ev.geo_cell = mer.geo_cell if rng.random() > 0.75 else ch.geo_cell
    ev.merchant_age_days = float(max(0, day_index - mer.onboard_day))
    ev.device_fingerprint_id = dev_id
    if dev is not None:
        ev.device_model = dev.model
        ev.device_os = dev.os
        ev.device_age_days = float(max(0, day_index - dev.first_seen_day))
        ev.ip_asn = dev.asn
    ev.pan_age_days = float(max(0, day_index - ch.open_day))
    ev.account_age_days = ev.pan_age_days
    ev.credit_limit_inr = ch.credit_limit_inr
    ev.cohort_tag = cohort_tag
    ev.kyc_tier = ch.kyc_tier
    return ev


def _fill_3ds_block(
    ev: CanonicalEvent,
    rng: np.random.Generator,
    *,
    synthesised: bool,
    challenge: bool,
) -> None:
    """Populate the 3DS authentication block.

    `synthesised=True` is the ATK-C4 case, and the tell is DATA QUALITY rather than anomaly: the
    bundle is internally implausible before it is unusual. We express that as (a) a HIGH
    field-population score with (b) an inconsistent combination — a mobile UA on a desktop
    screen size, a timezone that disagrees with the language, an ASN that disagrees with both.
    A naive "sparse fields = risk" feature would miss it entirely, which is the point.
    """
    ev.threeds_acs_id = f"ACS{int(rng.integers(1, 25)):03d}"
    ev.threeds_device_channel = "browser" if rng.random() < 0.72 else "app"
    ev.threeds_challenge_requested = bool(challenge)

    if synthesised:
        ev.threeds_field_population_score = float(np.clip(rng.normal(0.93, 0.04), 0.0, 1.0))
        # Deliberately inconsistent bundle.
        ev.threeds_ua_family = _UA_FAMILIES[0]
        ev.threeds_screen_wh = _SCREENS[int(rng.integers(4, 6))]      # desktop screen
        ev.threeds_device_channel = "app"                              # ... on the app channel
        ev.threeds_language = _LANGS[int(rng.integers(0, len(_LANGS)))]
        ev.threeds_timezone_offset_min = int(rng.choice([0, -300, 480]))  # not IST (+330)
        ev.threeds_ip_asn = f"AS{int(rng.integers(9000, 9100))}"          # off-pool ASN
    else:
        ev.threeds_field_population_score = float(np.clip(rng.beta(3.2, 2.0), 0.0, 1.0))
        ev.threeds_ua_family = _UA_FAMILIES[int(rng.integers(0, len(_UA_FAMILIES)))]
        ev.threeds_screen_wh = _SCREENS[int(rng.integers(0, len(_SCREENS)))]
        ev.threeds_language = _LANGS[int(rng.integers(0, len(_LANGS)))]
        ev.threeds_timezone_offset_min = 330
        ev.threeds_ip_asn = ev.ip_asn or f"AS{int(rng.integers(64500, 64540))}"

    if challenge:
        ev.threeds_authentication_result = (
            "challenge_success" if rng.random() < 0.86 else "challenge_abandoned"
        )
    else:
        ev.threeds_authentication_result = (
            "frictionless_success" if rng.random() < 0.94 else "attempted"
        )
    ev.threeds_eci = (
        "authenticated"
        if ev.threeds_authentication_result in ("frictionless_success", "challenge_success")
        else "attempted"
    )


def _schedule_clearing_and_dispute(
    ctx: SimContext,
    auth: AuthRecord,
    rng: np.random.Generator,
    *,
    divergence: float = 0.0,
    dispute_probability: float = 0.0,
    dispute_reason: str = "fraud_card_absent",
    friendly_fraud: bool = False,
) -> list[Followup]:
    """Schedule presentment (T+0/T+1) and, with probability, a chargeback weeks later.

    `divergence` is the auth-vs-clearing ratio minus one, which is the ATK-S1 observable. It is
    applied to the SETTLEMENT amount, never to the authorisation amount, because that is where
    the divergence physically lives.
    """
    if not auth.approved:
        return []
    fups: list[Followup] = []
    present_day = auth.day_index + (0 if rng.random() < 0.42 else 1)

    def build_presentment(c: SimContext) -> list[CanonicalEvent]:
        rec = c.auth_index.get(auth.event_id)
        if rec is None or rec.reversed_:
            c.bump("presentment_skipped_reversed")
            return []
        # The presentment MUST land after the authorisation in the sorted stream. Events are
        # emitted per cardholder and sorted by timestamp at the end, so a same-day presentment
        # drawn at an early hour would precede an authorisation drawn at a late one -- and then
        # "every presentment resolves to an auth" fails on ORDERING rather than on linkage.
        # STRICTLY AFTER, OR SPILL TO THE NEXT DAY. The old form was `min(HOUR_MAX, rec.hour_ist +
        # delta)`, which INVERTS when the authorisation's own hour is at or above the ceiling: it
        # returns an hour EARLIER than the auth, the presentment sorts ahead of its antecedent, and
        # F1-PAIR-01 then fails on ORDERING while reporting it as missing LINKAGE. That is precisely
        # what produced 14 violations in a 10M-event run. `new_event` now clamps every hour to
        # HOUR_MAX so the inversion can no longer arise, but this guard no longer DEPENDS on that:
        # if the same-day slot cannot fit strictly after the auth, the presentment moves to T+1,
        # which is what a real clearing file would do anyway.
        pday = present_day
        if pday == rec.day_index:
            hour = rec.hour_ist + float(rng.uniform(0.4, 3.0))
            if hour > HOUR_MAX:
                pday = rec.day_index + 1
                hour = float(np.clip(rng.normal(2.5, 1.2), 0.0, HOUR_MAX))
        else:
            hour = float(np.clip(rng.normal(2.5, 1.2), 0.0, HOUR_MAX))
        ev = c.new_event(
            rail="card-clearing-dispute",
            message_kind="presentment",
            tier="A",
            day_index=pday,
            hour_ist=hour,
            amount_inr=rec.amount_inr,
        )
        c.link_to_auth(ev, rec)
        ev.cardholder_id = rec.cardholder_id
        ev.pan_canonical = rec.pan_canonical
        ev.token_id = rec.token_id
        ev.token_requestor_id = rec.token_requestor_id
        ev.merchant_id = rec.merchant_id
        ev.mcc = rec.mcc
        mer = c.world.merchants.get(rec.merchant_id)
        if mer is not None:
            ev.acquirer_id = mer.acquirer_id
            ev.acceptor_descriptor = mer.descriptor
            ev.geo_cell = mer.geo_cell
            ev.merchant_age_days = float(max(0, pday - mer.onboard_day))
        ch = c.world.cardholders.get(rec.cardholder_id)
        if ch is not None:
            ev.issuer_id = ch.issuer_id
            ev.bin_prefix = ch.bin_prefix
        ev.settlement_amount_inr = float(np.round(rec.amount_inr * (1.0 + divergence), 2))
        ev.auth_to_presentment_ratio = (
            float(ev.settlement_amount_inr / rec.amount_inr) if rec.amount_inr > 0 else -1.0
        )
        ev.presentment_age_days = float(pday - rec.day_index)
        ev.incremental_auth_present = False
        ev.reversal_present = rec.reversed_
        ev.threeds_authentication_result = rec.threeds_result
        ev.threeds_eci = rec.threeds_eci
        ev.cohort_tag = rec.cohort_tag
        ev.approved = True
        ev.response_code = "approved"
        if rec.oracle_is_attack:
            apply_attack_provenance(
                ev,
                {
                    "campaign_id": rec.attack_campaign_id,
                    "family_id": rec.attack_family_id,
                    "grammar_str": rec.attack_grammar_str,
                    "cell_id": rec.attack_cell_id,
                    "stage": "clearing",
                },
            )
        rec.presented = True
        c.bump("presentment")
        return [ev]

    fups.append(Followup(present_day, "presentment", build_presentment, auth.event_id))

    if rng.random() < dispute_probability:
        lat = ctx.cfg.label_latency
        cb_day = auth.day_index + int(
            rng.integers(int(lat["chargeback_days_min"]), int(lat["chargeback_days_max"]) + 1)
        )

        def build_chargeback(c: SimContext) -> list[CanonicalEvent]:
            rec = c.auth_index.get(auth.event_id)
            if rec is None or not rec.presented:
                c.bump("chargeback_skipped_unpresented")
                return []
            hour = float(np.clip(rng.normal(13.0, 4.0), 0.0, 23.99))
            ev = c.new_event(
                rail="card-clearing-dispute",
                message_kind="chargeback",
                tier="A",
                day_index=cb_day,
                hour_ist=hour,
                amount_inr=rec.amount_inr,
            )
            c.link_to_auth(ev, rec)
            ev.cardholder_id = rec.cardholder_id
            ev.pan_canonical = rec.pan_canonical
            ev.token_id = rec.token_id
            ev.token_requestor_id = rec.token_requestor_id
            ev.merchant_id = rec.merchant_id
            ev.mcc = rec.mcc
            mer = c.world.merchants.get(rec.merchant_id)
            if mer is not None:
                ev.acquirer_id = mer.acquirer_id
                ev.acceptor_descriptor = mer.descriptor
                ev.geo_cell = mer.geo_cell
            ch = c.world.cardholders.get(rec.cardholder_id)
            if ch is not None:
                ev.issuer_id = ch.issuer_id
                ev.bin_prefix = ch.bin_prefix
            ev.dispute_reason_code = dispute_reason
            ev.dispute_filed_ts = ev.ts
            ev.settlement_amount_inr = rec.amount_inr
            ev.presentment_age_days = float(cb_day - rec.day_index)
            ev.threeds_authentication_result = rec.threeds_result
            ev.threeds_eci = rec.threeds_eci
            ev.cohort_tag = rec.cohort_tag
            ev.approved = False
            ev.response_code = "approved"
            # Friendly fraud / first-party misuse: the authorisation-time evidence CONTRADICTS
            # the claim, which is the ATK-D1 observable.
            ev.representment_filed = bool(friendly_fraud or rng.random() < 0.34)
            if ev.representment_filed:
                win_p = 0.72 if friendly_fraud else 0.31
                ev.representment_won = bool(rng.random() < win_p)
            if rec.oracle_is_attack:
                apply_attack_provenance(
                    ev,
                    {
                        "campaign_id": rec.attack_campaign_id,
                        "family_id": rec.attack_family_id,
                        "grammar_str": rec.attack_grammar_str,
                        "cell_id": rec.attack_cell_id,
                        "stage": "dispute",
                    },
                )
            rec.disputed = True
            c.bump("chargeback")
            return [ev]

        fups.append(Followup(cb_day, "chargeback", build_chargeback, auth.event_id))
    return fups


# =======================================================================================
# Emitters
# =======================================================================================

class CardCnp3dsEmitter:
    rail = "card-cnp-3ds"
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
        evasion = (attack or {}).get("evasion", "")

        if evasion == "threshold-hugging":
            t, _ = nearest_threshold(amount)
            amount = hug_threshold(amount, t, rng)
        if attack and (attack.get("amount_band")):
            amount = ctx.sample_amount_in_band(str(attack["amount_band"]), rng)

        ev = _base_card_event(
            ctx, cardholder_id, day_index, hour, rng,
            rail=self.rail, message_kind="authorisation", amount=amount, cohort_tag=cohort_tag,
        )
        ev.pos_entry_mode = "ecommerce"
        # A 3DS-authenticated CNP authorisation MUST NOT carry an EMV cryptogram: that pairing is
        # a G0 structural guard and an F1 invariant, so we never emit it.
        ev.emv_cryptogram_present = False
        ev.cvv2_result = "match" if rng.random() < 0.93 else "no_match"
        ev.avs_result = str(rng.choice(["match", "partial_match", "not_requested"], p=[0.62, 0.15, 0.23]))

        synthesised = bool(attack and evasion == "trust-inheritance")
        # Frictionless share: high for ordinary traffic, higher still when the attacker is
        # gaming the frictionless path.
        challenge = bool(rng.random() < (0.06 if synthesised else 0.17))
        _fill_3ds_block(ev, rng, synthesised=synthesised, challenge=challenge)

        if ctx.world.cardholders[cardholder_id].tokens and rng.random() < 0.35:
            tid = ctx.world.cardholders[cardholder_id].tokens[
                int(rng.integers(0, len(ctx.world.cardholders[cardholder_id].tokens)))
            ]
            ev.token_id = tid
            tok = ctx.world.tokens[tid]
            ev.token_requestor_id = tok.requestor_id
            ev.token_assurance_level = tok.assurance

        t, dist = nearest_threshold(ev.amount_inr)
        ev._scratch["threshold"] = t
        ev._scratch["threshold_distance"] = dist
        apply_attack_provenance(ev, attack)
        ctx.bump(f"emit:{self.rail}")
        return EmitResult(events=[ev])


class CardCnpKeyedEmitter:
    rail = "card-cnp-keyed"
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
        evasion = (attack or {}).get("evasion", "")

        if evasion == "oracle-probing":
            # Probing is near-uniform micro-value: the attacker is buying information, not goods.
            amount = float(np.round(rng.uniform(1.0, 42.0), 2))
        elif evasion == "threshold-hugging":
            t, _ = nearest_threshold(amount)
            amount = hug_threshold(amount, t, rng)
        elif evasion == "velocity-splitting":
            amount = float(np.round(amount / max(1.0, rng.uniform(2.0, 6.0)), 2))
        if attack and attack.get("amount_band"):
            amount = ctx.sample_amount_in_band(str(attack["amount_band"]), rng)

        ev = _base_card_event(
            ctx, cardholder_id, day_index, hour, rng,
            rail=self.rail, message_kind="authorisation", amount=amount, cohort_tag=cohort_tag,
        )
        ev.pos_entry_mode = "keyed" if rng.random() < 0.35 else "ecommerce"
        # By the rail's DEFINITION: no authentication block and no cryptogram. Both are F1
        # invariants and both are guaranteed here rather than checked afterwards.
        ev.threeds_authentication_result = "not_applicable"
        ev.threeds_eci = "none"
        ev.threeds_field_population_score = -1.0
        ev.emv_cryptogram_present = False

        if evasion == "oracle-probing":
            # An AVS trajectory is a real trajectory: the state advances per attempt on this
            # cardholder, so `avs_trajectory_shape` has something to read.
            prev = ctx.avs_state.get(cardholder_id, "no_match")
            nxt = {"no_match": "partial_match", "partial_match": "match", "match": "match"}[prev]
            ctx.avs_state[cardholder_id] = nxt
            ev.avs_result = nxt
            ev.cvv2_result = str(rng.choice(["no_match", "match"], p=[0.82, 0.18]))
        else:
            ev.avs_result = str(rng.choice(["match", "no_match", "not_requested"], p=[0.55, 0.09, 0.36]))
            ev.cvv2_result = str(rng.choice(["match", "no_match", "not_provided"], p=[0.83, 0.05, 0.12]))

        t, dist = nearest_threshold(ev.amount_inr)
        ev._scratch["threshold"] = t
        ev._scratch["threshold_distance"] = dist
        apply_attack_provenance(ev, attack)
        ctx.bump(f"emit:{self.rail}")
        return EmitResult(events=[ev])


class CardCpEmvEmitter:
    rail = "card-cp-emv"
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
        evasion = (attack or {}).get("evasion", "")
        if attack and attack.get("amount_band"):
            amount = ctx.sample_amount_in_band(str(attack["amount_band"]), rng)

        ev = _base_card_event(
            ctx, cardholder_id, day_index, hour, rng,
            rail=self.rail, message_kind="authorisation", amount=amount, cohort_tag=cohort_tag,
        )
        mer = ctx.world.merchants[ev.merchant_id]
        term_id = mer.terminals[int(rng.integers(0, len(mer.terminals)))] if mer.terminals else ""
        term = ctx.world.terminals.get(term_id)
        ev.terminal_id = term_id
        ev.geo_cell = (term.geo_cell if term else mer.geo_cell)

        # Card present carries no 3DS block, ever.
        ev.threeds_authentication_result = "not_applicable"
        ev.threeds_eci = "none"
        ev.threeds_field_population_score = -1.0
        ev.avs_result = "not_requested"
        ev.cvv2_result = "not_provided"

        fallback = bool(
            evasion == "trust-inheritance"
            and term is not None
            and term.accepts_fallback
            and rng.random() < 0.75
        ) or bool(term is not None and term.accepts_fallback and rng.random() < 0.03)

        if fallback:
            # Technical fallback: magstripe path, so NO cryptogram. That is the whole point of
            # the downgrade and it must be structurally consistent.
            ev.pos_entry_mode = "magstripe_fallback"
            ev.emv_cryptogram_present = False
            ev.cvm_result = "signature" if rng.random() < 0.6 else "none"
            ev.terminal_verification_result = "fallback_used"
        else:
            contactless = bool(rng.random() < 0.62)
            ev.pos_entry_mode = "contactless" if contactless else "chip"
            ev.emv_cryptogram_present = True
            if evasion == "oracle-probing" and attack:
                # ATK-P2 replay: re-issue the LAST ATC. Named as a replay so the F1 ATC
                # invariant can legitimately scope itself to non-attack events.
                ev.emv_cryptogram_atc = ctx.replay_atc(ev.pan_canonical)
                ev._scratch["atc_replay"] = True
                ev.emv_cryptogram_verified = bool(rng.random() < 0.35)
                ev.issuer_application_data_consistent = False
                ev.terminal_verification_result = "cryptogram_anomaly"
            else:
                ev.emv_cryptogram_atc = ctx.next_atc(ev.pan_canonical)
                ev.emv_cryptogram_verified = True
                ev.terminal_verification_result = "ok"
            ev.emv_unpredictable_number = f"{int(rng.integers(0, 1 << 31)):08x}"
            no_cvm_ok = bool(term is not None and term.accepts_no_cvm_contactless)
            if contactless and no_cvm_ok and ev.amount_inr < 5_000:
                ev.pos_entry_mode = "contactless_no_cvm"
                ev.cvm_result = "none"
            else:
                ev.cvm_result = str(rng.choice(["online_pin", "cdcvm", "offline_pin"], p=[0.58, 0.27, 0.15]))

        t, dist = nearest_threshold(ev.amount_inr)
        ev._scratch["threshold"] = t
        ev._scratch["threshold_distance"] = dist
        apply_attack_provenance(ev, attack)
        ctx.bump(f"emit:{self.rail}")
        return EmitResult(events=[ev])


class CardTokenProvisioningEmitter:
    """Provisioning request, then the first tokenised spend. Two stages by nature."""

    rail = "card-token-provisioning"
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
        ch = ctx.world.cardholders[cardholder_id]
        habit = ctx.habits[cardholder_id]
        hour = habit.sample_hour(rng)
        evasion = (attack or {}).get("evasion", "")
        result = EmitResult()

        prov = _base_card_event(
            ctx, cardholder_id, day_index, hour, rng,
            rail=self.rail, message_kind="provisioning_request", amount=0.0, cohort_tag=cohort_tag,
        )
        token_id = f"TOKX{ctx.mint_event_id('')}"
        prov.token_id = token_id
        prov.token_requestor_id = f"TRQ{int(rng.integers(1, 40)):03d}"
        # A takeover-driven provisioning has LOW assurance with a device age near zero: the
        # combination is the observable, not either half.
        attacked = bool(attack)
        prov.token_assurance_level = (
            str(rng.choice(["low", "medium"], p=[0.78, 0.22])) if attacked
            else str(rng.choice(["low", "medium", "high"], p=[0.12, 0.40, 0.48]))
        )
        if attacked:
            prov.device_age_days = float(np.round(rng.uniform(0.0, 1.0), 3))
            prov.cvm_result = "cdcvm"
        prov.provisioning_event_id = prov.event_id
        prov.pos_entry_mode = "ecommerce"
        prov.threeds_authentication_result = "not_applicable"
        prov.threeds_eci = "none"
        prov.threeds_field_population_score = -1.0
        prov.emv_cryptogram_present = False
        prov.approved = True
        prov.response_code = "approved"
        apply_attack_provenance(prov, attack)
        if attack:
            prov.attack_stage = "establish"
        ctx.provisioning_ts[token_id] = prov.ts
        result.events.append(prov)

        # First tokenised spend, minutes to hours later. Provisioning-to-first-spend latency is
        # the load-bearing observable for the family.
        gap_min = float(abs(rng.normal(6.0, 4.0))) if attacked else float(abs(rng.normal(2200.0, 1800.0)))
        spend_hour = (hour + gap_min / 60.0)
        spend_day = day_index + int(spend_hour // 24)
        spend_hour = spend_hour % 24.0

        spend = _base_card_event(
            ctx, cardholder_id, spend_day, spend_hour, rng,
            rail=self.rail, message_kind="authorisation", amount=habit.sample_amount(rng),
            cohort_tag=cohort_tag,
        )
        spend.token_id = token_id
        spend.token_requestor_id = prov.token_requestor_id
        spend.token_assurance_level = prov.token_assurance_level
        spend.provisioning_event_id = prov.event_id
        spend.provisioning_to_first_spend_minutes = gap_min
        spend.pos_entry_mode = "ecommerce"
        spend.cvm_result = "cdcvm" if rng.random() < 0.7 else "none"
        spend.threeds_authentication_result = "not_applicable"
        spend.threeds_eci = "none"
        spend.threeds_field_population_score = -1.0
        spend.emv_cryptogram_present = False
        spend.avs_result = "not_requested"
        spend.cvv2_result = "not_provided"
        if attacked:
            spend.device_age_days = prov.device_age_days
        if evasion == "graph-camouflage":
            # ATK-T2: PAN-level fan-out to distinct token requestors, every per-token velocity
            # sub-threshold. The fan-out is the signal; each token looks ordinary.
            spend._scratch["token_fanout_intent"] = True
        t, dist = nearest_threshold(spend.amount_inr)
        spend._scratch["threshold"] = t
        spend._scratch["threshold_distance"] = dist
        apply_attack_provenance(spend, attack)
        if attack:
            spend.attack_stage = "extract"
        result.events.append(spend)

        ctx.bump(f"emit:{self.rail}")
        return result


def schedule_card_lifecycle(
    ctx: SimContext,
    ev: CanonicalEvent,
    rng: np.random.Generator,
    *,
    attack: dict[str, Any] | None = None,
) -> list[Followup]:
    """Register an approved card authorisation and schedule its clearing and dispute tail.

    Called by the engine AFTER the incumbent policy and the issuer response are resolved, because
    only an APPROVED authorisation has a lifecycle. Doing this inside the emitter would schedule
    presentments for declined authorisations, which is an F1 violation by construction.
    """
    if ev.rail not in ("card-cnp-3ds", "card-cnp-keyed", "card-cp-emv", "card-token-provisioning"):
        return []
    if ev.message_kind not in ("authorisation",):
        return []
    rec = ctx.register_auth(ev)
    if not ev.approved:
        return []

    habit = ctx.habits.get(ev.cardholder_id)
    base_dispute = habit.dispute_propensity if habit else 0.002

    evasion = (attack or {}).get("evasion", "")
    monetisation = (attack or {}).get("monetisation", "")
    access = (attack or {}).get("access", "")

    divergence = 0.0
    dispute_p = base_dispute
    reason = "fraud_card_absent"
    friendly = False

    if attack:
        if ev.oracle_is_attack and access != "synthetic-identity":
            dispute_p = 0.55 if evasion != "label-attack" else 0.82
        if access == "first-party-misuse":
            friendly = True
            reason = "goods_not_received" if rng.random() < 0.35 else "fraud_card_absent"
            dispute_p = 0.9
        if access == "synthetic-identity":
            # NO VICTIM EVER COMPLAINS. This is the mechanism that makes the family invisible to
            # any model trained on network fraud reports, and it must be produced here.
            dispute_p = 0.0
        if monetisation == "merchant-settlement" and rng.random() < 0.5:
            # ATK-S1: per-MCC tolerance divergence, chosen to sit inside normal tolerance bands.
            divergence = float(abs(rng.normal(0.11, 0.05)))
    elif ev.mcc in ("5812", "5541", "7011") and rng.random() < 0.30:
        # Legitimate tip / fuel / hotel incremental divergence. Without this benign population,
        # auth-vs-clearing divergence is a perfect fraud signal and ATK-S1 is free.
        divergence = float(abs(rng.normal(0.09, 0.06)))

    if ev.mcc in quasi_cash_mccs():
        ev._scratch["quasi_cash"] = True

    return _schedule_clearing_and_dispute(
        ctx,
        rec,
        rng,
        divergence=divergence,
        dispute_probability=float(np.clip(dispute_p, 0.0, 1.0)),
        dispute_reason=reason,
        friendly_fraud=friendly,
    )


def schedule_refund(
    ctx: SimContext,
    auth_event_id: str,
    rng: np.random.Generator,
    *,
    day_offset: int = 3,
    fraction: float = 1.0,
    exceed: bool = False,
    to_different_credential: bool = False,
    without_original: bool = False,
    attack: dict[str, Any] | None = None,
) -> Followup | None:
    """Schedule a refund/credit.

    TWO F1 INVARIANTS LIVE HERE: a refund must resolve to an existing authorisation, and the
    cumulative refunded amount must not exceed the original. ATK-V2 and ATK-A2 are unbuildable
    without a first-class refund message, and `without_original=True` deliberately violates the
    first invariant — which is why that path is only reachable from an attack and the invariant
    is scoped to non-attack events.
    """
    rec = ctx.auth_index.get(auth_event_id)
    if rec is None and not without_original:
        return None
    due = (rec.day_index if rec else ctx.day) + max(0, int(day_offset))

    def build(c: SimContext) -> list[CanonicalEvent]:
        r = c.auth_index.get(auth_event_id) if auth_event_id else None
        if r is None and not without_original:
            c.bump("refund_skipped_no_auth")
            return []
        base = r.amount_inr if r else float(np.round(rng.uniform(500.0, 25_000.0), 2))
        want = base * float(fraction) * (1.35 if exceed else 1.0)
        if r is not None and not exceed:
            headroom = max(0.0, r.amount_inr - r.refunded_inr)
            want = min(want, headroom)
            if want <= 0.0:
                c.bump("refund_skipped_no_headroom")
                return []
        hour = float(np.clip(rng.normal(15.0, 3.5), 0.0, 23.99))
        ev = c.new_event(
            rail="card-clearing-dispute",
            message_kind="refund_credit",
            tier="A",
            day_index=due,
            hour_ist=hour,
            amount_inr=float(np.round(want, 2)),
        )
        if r is not None:
            c.link_to_auth(ev, r)
            ev.cardholder_id = r.cardholder_id
            ev.pan_canonical = r.pan_canonical
            ev.token_id = r.token_id
            ev.token_requestor_id = r.token_requestor_id
            ev.merchant_id = r.merchant_id
            ev.mcc = r.mcc
            ev.cohort_tag = r.cohort_tag
            mer = c.world.merchants.get(r.merchant_id)
            if mer is not None:
                ev.acquirer_id = mer.acquirer_id
                ev.acceptor_descriptor = mer.descriptor
                ev.geo_cell = mer.geo_cell
            ch = c.world.cardholders.get(r.cardholder_id)
            if ch is not None:
                ev.issuer_id = ch.issuer_id
                ev.bin_prefix = ch.bin_prefix
            r.refunded_inr += ev.amount_inr
        else:
            # Deliberately orphaned: the ATK-V2 "refund with no matching original" observable.
            ev.rrn = c.mint_rrn()
            ev.trace_number = c.mint_trace()
            ev.merchant_id = c.sample_merchant(rng)
            mer = c.world.merchants[ev.merchant_id]
            ev.mcc = mer.mcc
            ev.acquirer_id = mer.acquirer_id
            ev.acceptor_descriptor = mer.descriptor
            ev.geo_cell = mer.geo_cell
        ev.refund_amount_inr = ev.amount_inr
        ev.approved = True
        ev.response_code = "approved"
        if to_different_credential:
            ev.pan_canonical = ""      # credited elsewhere: the observable is the mismatch
            ev.refund_to_different_credential = True
        apply_attack_provenance(ev, attack)
        c.bump("refund_credit")
        return [ev]

    return Followup(due, "refund_credit", build, auth_event_id)


CARD_EMITTERS = (
    CardCnp3dsEmitter(),
    CardCnpKeyedEmitter(),
    CardCpEmvEmitter(),
    CardTokenProvisioningEmitter(),
)
