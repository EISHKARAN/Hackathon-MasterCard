"""Tier-A A2A credit transfer, shaped as ISO 20022 pacs.008 / pacs.002.

SHAPED, NOT CONFORMANT, and we call it that. The message carries an end-to-end id, a creditor
name, unstructured remittance info and a status report, because those four are what the
ATK-B1/ATK-V3 observables are expressed over — creditor-name-versus-account mismatch
(confirmation-of-payee failure), remittance-info drift against prior invoices, a beneficiary
change inside the cooling window, and an amount outside vendor history.

We do not claim conformance to any pacs version, and `sim/field_map.yaml` marks every element
`verified: false`.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from sim.rails.base import EmitResult, SimContext, apply_attack_provenance, hug_threshold
from sim.rails.upi import emit_inbound_credit, pick_beneficiary
from sim.schema import CanonicalEvent

#: A2A thresholds (IMPS/NEFT/RTGS-shaped bands). ALL [VERIFY] and swept; geometry only.
A2A_THRESHOLDS: tuple[float, ...] = (25_000.0, 200_000.0, 500_000.0)

_REMITTANCE_TEMPLATES: tuple[str, ...] = (
    "INV-{n}", "PO-{n}", "SALARY-{n}", "VENDOR-{n}", "REIMB-{n}", "RENT-{n}",
)


class A2ACreditTransferEmitter:
    rail = "a2a-credit-transfer"
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
        ch = ctx.world.cardholders[cardholder_id]
        hour = habit.sample_hour(rng)
        a = attack or {}
        evasion, access, monet = a.get("evasion", ""), a.get("access", ""), a.get("monetisation", "")

        # A2A tickets are larger than card or UPI tickets: this is a corporate and high-value
        # retail rail, and the amount law has to reflect that or the rail is indistinguishable.
        amount = float(np.round(habit.sample_amount(rng) * rng.uniform(2.0, 14.0), 2))
        if evasion == "threshold-hugging":
            t = min(A2A_THRESHOLDS, key=lambda x: abs(x - amount))
            amount = hug_threshold(amount, t, rng)
        if a.get("amount_band"):
            amount = ctx.sample_amount_in_band(str(a["amount_band"]), rng)
        if access == "authorised-but-deceived-payer" and a.get("stage") in ("extract", "cashout"):
            amount = float(np.round(amount * rng.uniform(1.5, 6.0), 2))

        result = EmitResult()
        devs = ch.devices
        dev_id = devs[int(rng.integers(0, len(devs)))] if devs else ""
        dev = ctx.world.devices.get(dev_id)

        ev = ctx.new_event(
            rail=self.rail, message_kind="credit_transfer", tier="A",
            day_index=day_index, hour_ist=hour, amount_inr=amount,
        )
        ev.rrn = ctx.mint_rrn()
        ev.trace_number = ctx.mint_trace()
        ev.pacs_end_to_end_id = f"E2E{ctx.mint_event_id('')}"
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
        ev.kyc_tier = ch.kyc_tier
        ev.cohort_tag = cohort_tag
        ev.pos_entry_mode = "file_upload" if rng.random() < 0.22 else "in_app"
        ev.upi_initiation_mode = "not_applicable"
        ev.threeds_authentication_result = "not_applicable"
        ev.threeds_eci = "none"
        ev.threeds_field_population_score = -1.0
        ev.emv_cryptogram_present = False
        ev.avs_result = "not_requested"
        ev.cvv2_result = "not_provided"
        ev.cvm_result = "online_pin" if ev.pos_entry_mode == "in_app" else "none"
        ev.session_duration_minutes = float(abs(rng.normal(11.0, 7.0)))
        ev.remittance_info = _REMITTANCE_TEMPLATES[
            int(rng.integers(0, len(_REMITTANCE_TEMPLATES)))
        ].format(n=int(rng.integers(10_000, 99_999)))

        fresh = bool(attack) or bool(rng.random() < 0.05)
        cat = (
            "crypto_onramp" if monet == "crypto-offramp"
            else "corporate_vendor" if rng.random() < 0.4 else "payroll"
        )
        bid = pick_beneficiary(ctx, cardholder_id, rng, fresh=fresh, category=cat)
        ben = ctx.world.beneficiaries[bid]
        ev.beneficiary_id = bid
        ev.payee_vpa = ben.payee_vpa
        ev.payee_psp_id = ben.psp_id
        ev.beneficiary_category = ben.category
        ev.beneficiary_account_age_days = float(max(0.0, day_index - ben.open_day))
        ev.payee_vpa_age_days = ev.beneficiary_account_age_days

        # Confirmation-of-payee: the standard control, and the observable ATK-B1 defeats.
        if attack and evasion in ("trust-inheritance", "low-visibility-rail"):
            ev.creditor_name_string = f"{ben.payee_name} SERVICES"     # plausible but not the account name
            ev.creditor_name_match_score = float(np.clip(rng.normal(0.42, 0.12), 0.0, 1.0))
            ev.beneficiary_change_ts = ev.ts - float(rng.uniform(1.0, 40.0)) * 3600.0
            ev.remittance_info = _REMITTANCE_TEMPLATES[0].format(n=int(rng.integers(1, 99)))
        else:
            ev.creditor_name_string = ben.payee_name
            ev.creditor_name_match_score = float(np.clip(rng.normal(0.94, 0.06), 0.0, 1.0))
            # BENIGN PAYEES CHANGE BANK DETAILS TOO. Without this branch `beneficiary_change_ts` was
            # set on the attack path AND NOWHERE ELSE, so the derived feature
            # `beneficiary_change_within_cooling_hours` was the -1 sentinel on every benign row in the
            # corpus and a real number on attack rows: a ONE-SIDED PERFECT SEPARATOR that any tree
            # splits at zero for 100% precision. The generator would have been handing the model the
            # answer, and the reported recall would have been measuring our own leak.
            #
            # The DISCRIMINATIVE content is preserved and is the thing that is actually true of the
            # world: a real payee's details changed WEEKS ago (outside any confirmation-of-payee
            # cooling window), whereas ATK-B1's changed HOURS ago (inside it). So the feature still
            # separates -- on the cooling window, which is the mechanism -- rather than on presence.
            if rng.random() < 0.06:
                days_ago = float(rng.uniform(21.0, 400.0))
                ev.beneficiary_change_ts = ev.ts - days_ago * 86_400.0

        if attack and access == "authorised-but-deceived-payer":
            ev.session_duration_minutes = float(abs(rng.normal(160.0, 80.0)))
            ev.in_app_dwell_seconds = float(abs(rng.normal(8.5, 0.6)))
            ev.fd_liquidation_flag = True

        ev._scratch["beneficiary_id"] = bid
        if attack and monet in ("mule-chain-cashout", "biller-giftcard-resale", "crypto-offramp"):
            ev._scratch["dwell_seconds"] = float(abs(rng.normal(180.0, 110.0)))
            ev._scratch["skim"] = float(np.clip(rng.normal(0.025, 0.012), 0.0, 0.2))
            if evasion == "graph-camouflage":
                ev._scratch["dwell_seconds"] = float(abs(rng.normal(3_600.0, 2_400.0)))
                ev._scratch["skim"] = float(np.clip(rng.normal(0.09, 0.04), 0.0, 0.35))
        apply_attack_provenance(ev, attack)
        result.events.append(ev)

        ctx.bump(f"emit:{self.rail}")
        return result


def emit_pacs_status(
    ctx: SimContext,
    transfer: CanonicalEvent,
    rng: np.random.Generator,
    *,
    accepted: bool,
) -> CanonicalEvent:
    """The pacs.002-shaped status report. Paired to its pacs.008 by end-to-end id AND rrn."""
    ev = ctx.new_event(
        rail="a2a-credit-transfer", message_kind="credit_transfer_status", tier="A",
        day_index=transfer.day_index,
        hour_ist=min(23.99, transfer.hour_ist + abs(float(rng.normal(0.02, 0.01)))),
        amount_inr=transfer.amount_inr,
    )
    ev.original_auth_event_id = transfer.event_id
    ev.rrn = transfer.rrn
    ev.trace_number = transfer.trace_number
    ev.pacs_end_to_end_id = transfer.pacs_end_to_end_id
    ev.pacs_status_code = "ACSC" if accepted else "RJCT"
    ev.cardholder_id = transfer.cardholder_id
    ev.vpa = transfer.vpa
    ev.beneficiary_id = transfer.beneficiary_id
    ev.payee_vpa = transfer.payee_vpa
    ev.payee_psp_id = transfer.payee_psp_id
    ev.beneficiary_category = transfer.beneficiary_category
    ev.creditor_name_string = transfer.creditor_name_string
    ev.creditor_name_match_score = transfer.creditor_name_match_score
    ev.geo_cell = transfer.geo_cell
    ev.cohort_tag = transfer.cohort_tag
    ev.approved = accepted
    ev.response_code = "approved" if accepted else "declined_do_not_honour"
    ev.response_latency_ms = float(abs(rng.normal(24.0, 9.0)))
    ev.attack_campaign_id = transfer.attack_campaign_id
    ev.attack_family_id = transfer.attack_family_id
    ev.attack_grammar_str = transfer.attack_grammar_str
    ev.attack_cell_id = transfer.attack_cell_id
    ev.attack_stage = transfer.attack_stage
    ev.oracle_is_attack = transfer.oracle_is_attack
    ev.sealed_holdout = transfer.sealed_holdout
    ctx.bump("pacs_status")
    return ev


A2A_EMITTERS = (A2ACreditTransferEmitter(),)
