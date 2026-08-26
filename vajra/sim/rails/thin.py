"""TIER-B THIN EMITTERS — upi-lite-offline, aeps-microatm, agentic-commerce.

============================ WHAT "THIN" MEANS, EXACTLY ================================
These rails carry attack compositions and observable signatures. They appear in the archive and
in the attack table. They make **NO CLAIM OF MESSAGE-LEVEL FIDELITY**, and the UI renders a
"thin emitter" badge on every card that touches them.

That is a scope decision stated as a limitation rather than hidden as an omission. What we
deliberately do NOT model here:
  * UPI Lite: the on-device ledger's actual posting mechanics and reconciliation semantics
    [VERIFY]. We model "weakened central velocity visibility" as a reconciliation LAG and a
    cohort RATIO, without asserting how posting works.
  * AePS: the biometric authentication exchange. We model terminal-level population statistics
    (distinct customers per terminal, balance-enquiry-to-withdrawal ratio) and nothing about
    biometrics [VERIFY current Aadhaar-lock and onboarding rules].
  * agentic-commerce: the field names are ILLUSTRATIVE, our own invention, and badged as such.
    There is no standard we are asserting conformance to [VERIFY protocol status as of 2026].
========================================================================================
"""

from __future__ import annotations

from typing import Any

import numpy as np

from sim.rails.base import EmitResult, SimContext, apply_attack_provenance
from sim.rails.upi import pick_beneficiary
from sim.schema import CanonicalEvent


class UpiLiteOfflineEmitter:
    """UPI Lite / 123Pay. PIN-free small-value debits from an on-device ledger."""

    rail = "upi-lite-offline"
    tier = "B"

    #: Lite debits sit beneath most rule floors by design. That is the whole mechanism.
    LITE_CEILING_INR = 500.0

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
        result = EmitResult()
        devs = ch.devices
        dev_id = devs[int(rng.integers(0, len(devs)))] if devs else ""
        dev = ctx.world.devices.get(dev_id)

        def base(kind: str, amount: float, h: float) -> CanonicalEvent:
            ev = ctx.new_event(
                rail=self.rail, message_kind=kind, tier="B",
                day_index=day_index, hour_ist=h, amount_inr=amount,
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
            ev.account_age_days = float(max(0, day_index - ch.open_day))
            ev.vpa_age_days = ev.account_age_days
            ev.kyc_tier = ch.kyc_tier
            ev.cohort_tag = cohort_tag
            # `pos_entry_mode` is the ON-DEVICE LEDGER mode here, not "intent". A previous build
            # emitted "intent" for Lite, which contradicted the rail's own definition and tripped
            # the F1 entry-mode invariant.
            ev.pos_entry_mode = "on_device_ledger"
            ev.upi_initiation_mode = "in_app"
            # PIN-FREE by design: that is the point of the rail.
            ev.cvm_result = "none"
            ev.threeds_authentication_result = "not_applicable"
            ev.threeds_eci = "none"
            ev.threeds_field_population_score = -1.0
            ev.emv_cryptogram_present = False
            ev.avs_result = "not_requested"
            ev.cvv2_result = "not_provided"
            # Delayed core-banking reconciliation: the low-visibility observable, modelled as a
            # LAG rather than as a claim about posting mechanics.
            ev.reconciliation_lag_minutes = float(abs(rng.normal(340.0, 220.0))) if attack else float(
                abs(rng.normal(95.0, 70.0))
            )
            ev.approved = True
            ev.response_code = "approved"
            return ev

        # Top-up, then several sub-ceiling debits. The top-up FREQUENCY spike plus many small
        # debits to few payees is the ATK-U6 signature.
        topup = base("lite_topup", float(np.round(rng.uniform(200.0, 2_000.0), 2)), hour)
        apply_attack_provenance(topup, attack)
        result.events.append(topup)

        n_debits = int(rng.integers(4, 12)) if attack else int(rng.integers(1, 5))
        bid = pick_beneficiary(ctx, cardholder_id, rng, fresh=bool(attack))
        ben = ctx.world.beneficiaries[bid]
        for k in range(n_debits):
            amt = float(np.round(min(self.LITE_CEILING_INR - 1.0, abs(rng.normal(180.0, 90.0)) + 5.0), 2))
            d = base("lite_debit", amt, min(23.99, hour + 0.05 * (k + 1)))
            d.original_auth_event_id = topup.event_id
            d.rrn = topup.rrn
            d.trace_number = topup.trace_number
            d.beneficiary_id = bid
            d.payee_vpa = ben.payee_vpa
            d.payee_psp_id = ben.psp_id
            d.beneficiary_category = ben.category
            d.payee_vpa_age_days = float(max(0.0, day_index - ben.open_day))
            d.beneficiary_account_age_days = d.payee_vpa_age_days
            apply_attack_provenance(d, attack)
            if attack:
                d._scratch["beneficiary_id"] = bid
                d._scratch["dwell_seconds"] = float(abs(rng.normal(300.0, 200.0)))
                d._scratch["skim"] = 0.02
            result.events.append(d)

        ctx.bump(f"emit:{self.rail}")
        return result


class AepsMicroAtmEmitter:
    """AePS / micro-ATM assisted withdrawal. Terminal-level population statistics only."""

    rail = "aeps-microatm"
    tier = "B"

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
        # Night clusters are an observable; ordinary AePS traffic is daytime.
        hour = float(np.clip(rng.normal(2.0, 1.2), 0.0, 23.99)) if attack else habit.sample_hour(rng)
        result = EmitResult()

        mid = ctx.sample_merchant(rng)
        mer = ctx.world.merchants[mid]
        term_id = mer.terminals[int(rng.integers(0, len(mer.terminals)))] if mer.terminals else ""

        def base(kind: str, amount: float, h: float) -> CanonicalEvent:
            ev = ctx.new_event(
                rail=self.rail, message_kind=kind, tier="B",
                day_index=day_index, hour_ist=h, amount_inr=amount,
            )
            ev.rrn = ctx.mint_rrn()
            ev.trace_number = ctx.mint_trace()
            ev.cardholder_id = cardholder_id
            ev.issuer_id = ch.issuer_id
            ev.merchant_id = mid
            ev.acquirer_id = mer.acquirer_id
            ev.mcc = mer.mcc
            ev.acceptor_descriptor = mer.descriptor
            ev.terminal_id = term_id
            # Geo far from the customer's home cell is the ATK-U11 observable.
            ev.geo_cell = mer.geo_cell if attack else ch.geo_cell
            ev.account_age_days = float(max(0, day_index - ch.open_day))
            ev.kyc_tier = ch.kyc_tier
            ev.cohort_tag = cohort_tag
            ev.pos_entry_mode = "biometric_assisted"
            # NO PIN OR OTP TO CHALLENGE: biometrics are treated as strong authentication, which
            # is exactly why the family is hard. We model the RESULT, never the exchange.
            ev.cvm_result = "biometric"
            ev.upi_initiation_mode = "not_applicable"
            ev.threeds_authentication_result = "not_applicable"
            ev.threeds_eci = "none"
            ev.threeds_field_population_score = -1.0
            ev.emv_cryptogram_present = False
            ev.avs_result = "not_requested"
            ev.cvv2_result = "not_provided"
            ev.approved = True
            ev.response_code = "approved"
            return ev

        # Balance-enquiry-to-withdrawal ratio anomaly: an agent probing which references work
        # runs many enquiries per withdrawal.
        n_enq = int(rng.integers(3, 9)) if attack else int(rng.integers(0, 2))
        for k in range(n_enq):
            e = base("balance_enquiry", 0.0, min(23.99, hour + 0.02 * k))
            apply_attack_provenance(e, attack)
            result.events.append(e)

        # Identical amounts across unrelated customers is an observable, so attack withdrawals
        # are quantised and ordinary ones are not.
        amt = 5_000.0 if attack else float(np.round(rng.uniform(500.0, 10_000.0), 2))
        w = base("assisted_withdrawal", amt, min(23.99, hour + 0.05 * max(1, n_enq)))
        # AePS terminates in physical cash: there is NO beneficiary leg on this rail, so we do
        # not emit one. (`has_beneficiary_leg: false` in grammar/slots/rail.yaml.)
        apply_attack_provenance(w, attack)
        result.events.append(w)

        ctx.bump(f"emit:{self.rail}")
        return result


class AgenticCommerceEmitter:
    """Agent mandate object, then an agent-initiated authorisation. ILLUSTRATIVE field naming."""

    rail = "agentic-commerce"
    tier = "B"

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
        a = attack or {}
        evasion = a.get("evasion", "")
        result = EmitResult()

        agent_id = f"AGT{int(rng.integers(1, 400)):04d}"
        mid = ctx.sample_merchant(rng)
        mer = ctx.world.merchants[mid]

        def base(kind: str, amount: float, h: float) -> CanonicalEvent:
            ev = ctx.new_event(
                rail=self.rail, message_kind=kind, tier="B",
                day_index=day_index, hour_ist=h, amount_inr=amount,
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
            ev.geo_cell = mer.geo_cell
            ev.merchant_age_days = float(max(0, day_index - mer.onboard_day))
            ev.agent_identity_id = agent_id
            ev.agentic_indicator = True
            ev.account_age_days = float(max(0, day_index - ch.open_day))
            ev.cohort_tag = cohort_tag
            ev.pos_entry_mode = "agent"
            ev.upi_initiation_mode = "not_applicable"
            ev.threeds_authentication_result = "not_applicable"
            ev.threeds_eci = "none"
            ev.threeds_field_population_score = -1.0
            # No consumer device is present at the point of the message, so no CVM and no
            # cryptogram. Both are structural.
            ev.cvm_result = "none"
            ev.emv_cryptogram_present = False
            ev.avs_result = "not_requested"
            ev.cvv2_result = "not_provided"
            ev.approved = True
            ev.response_code = "approved"
            return ev

        quoted = float(np.round(habit.sample_amount(rng), 2))
        mandate = base("agent_mandate_object", 0.0, hour)
        mandate.agent_mandate_signature_valid = not bool(attack and evasion == "cohort-splitting")
        mandate.agent_attestation_status = (
            "unattested" if (attack and evasion == "cohort-splitting")
            else str(rng.choice(["attested", "self_attested"], p=[0.72, 0.28]))
        )
        mandate.agent_endpoint_age_days = (
            float(np.round(rng.uniform(0.0, 6.0), 2)) if attack
            else float(np.round(rng.uniform(30.0, 900.0), 1))
        )
        mandate.agent_quoted_amount_inr = quoted
        mandate.mandate_max_amount_inr = float(np.round(quoted * rng.uniform(1.0, 1.6), 2))
        mandate.mandate_id = f"AMD{ctx.mint_event_id('')}"
        mandate.cit_mit_indicator = "CIT"
        apply_attack_provenance(mandate, attack)
        if attack:
            mandate.attack_stage = "establish"
        result.events.append(mandate)

        # The authorisation. MANDATE-VERSUS-EXECUTION MISMATCH on item/MCC/amount/merchant is the
        # ATK-X1 observable, and the honest note is that there is NO MESSAGE FIELD for "the
        # instruction was poisoned" -- so the mismatch is all a detector has.
        authorised = quoted
        if attack and evasion == "trust-inheritance":
            authorised = float(np.round(quoted * rng.uniform(1.15, 3.2), 2))
        auth = base("agent_authorisation", authorised, min(23.99, hour + 0.08))
        auth.original_auth_event_id = mandate.event_id
        auth.rrn = mandate.rrn
        auth.trace_number = mandate.trace_number
        auth.mandate_id = mandate.mandate_id
        auth.mandate_max_amount_inr = mandate.mandate_max_amount_inr
        auth.agent_attestation_status = mandate.agent_attestation_status
        auth.agent_endpoint_age_days = mandate.agent_endpoint_age_days
        auth.agent_mandate_signature_valid = mandate.agent_mandate_signature_valid
        auth.agent_quoted_amount_inr = quoted
        auth.cit_mit_indicator = "MIT"
        auth.agent_human_confirmation_event = bool(not attack and rng.random() < 0.55)
        if authorised > mandate.mandate_max_amount_inr:
            # Over-mandate execution is refused STRUCTURALLY (a G0 mandate-conformance guard),
            # not scored. If it were merely scored, the guard would not be a guard.
            auth.approved = False
            auth.response_code = "declined_mandate_scope"
            ctx.bump("agentic_over_mandate_refused")
        apply_attack_provenance(auth, attack)
        if attack:
            auth.attack_stage = "extract"
        result.events.append(auth)

        ctx.bump(f"emit:{self.rail}")
        return result


THIN_EMITTERS = (UpiLiteOfflineEmitter(), AepsMicroAtmEmitter(), AgenticCommerceEmitter())
