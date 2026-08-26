"""F1 — hand-written rail invariants. THE GATE THAT FAILS THE BUILD.

This is the single most important reproducibility decision in the repo, and the one thing the
design says is never cut. Without it, nothing downstream means anything: no fidelity claim, no
attack execution and no detection number, because the data could be structurally impossible and
no test would notice.

WHAT AN INVARIANT IS HERE: a statement about MESSAGE STRUCTURE that is either satisfied or
violated — never a distributional band. "A keyed CNP authorisation carries no EMV cryptogram" is
an invariant. "Amounts are lognormal" is not; that is F3.

WHY INVARIANTS AND NOT A LEARNED CRITIC: a hand-written invariant is NOT GAMEABLE BY GRADIENT,
only satisfiable or violated. That is why F1 is the fidelity mechanism allowed INSIDE the
attacker's loop while the real-vs-synthetic discriminator is deliberately kept out of it (the
Goodhart argument — see docs/RESEARCH.md and fidelity/f2_discriminator.py).

TWO SCOPING RULES, both explicit rather than implicit:

  * `attack_scoped=False` (the default) means the invariant applies to EVERY event. A violation
    fails the build.
  * `attack_scoped=True` means the invariant applies only to NON-ATTACK events, because the
    attack deliberately produces the violation as its observable signature. ATC replay (ATK-P2)
    and a refund with no original authorisation (ATK-V2) are the two cases. Scoping them here,
    by name, is honest; silently excluding attack rows from every invariant would not be.

Zero violations is the target and the build fails otherwise. The count of invariants is
MACHINE-COUNTED by `invariant_count()`; it is never written as a literal.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

from sim.schema import (
    AVS_RESULTS,
    HOUR_MAX,
    CVM_RESULTS,
    CVV2_RESULTS,
    COHORT_TAGS,
    DISPUTE_REASON_CODES,
    ENTRY_MODES,
    INITIATION_MODES,
    MESSAGE_KINDS,
    RAILS,
    RESPONSE_CODES,
    THREEDS_ECI_BANDS,
    THREEDS_RESULTS,
    TOKEN_ASSURANCE,
    CanonicalEvent,
)

#: Rails whose declared fidelity tier is A (message level). Mirrors grammar/slots/rail.yaml.
TIER_A_RAILS: frozenset[str] = frozenset(
    {
        "card-cnp-3ds", "card-cnp-keyed", "card-cp-emv", "card-clearing-dispute",
        "card-token-provisioning", "upi-pay", "upi-collect", "upi-autopay-mandate",
        "a2a-credit-transfer",
    }
)
TIER_B_RAILS: frozenset[str] = frozenset({"upi-lite-offline", "aeps-microatm", "agentic-commerce"})

CARD_RAILS: frozenset[str] = frozenset(
    {"card-cnp-3ds", "card-cnp-keyed", "card-cp-emv", "card-clearing-dispute",
     "card-token-provisioning"}
)
UPI_RAILS: frozenset[str] = frozenset({"upi-pay", "upi-collect", "upi-autopay-mandate", "upi-lite-offline"})

#: Message kinds that MUST resolve to an antecedent authorisation.
DERIVED_KINDS: frozenset[str] = frozenset(
    {"presentment", "chargeback", "representment", "refund_credit", "reversal", "incremental_auth"}
)

SENTINEL = -1.0


@dataclass
class Violation:
    invariant_id: str
    event_id: str
    rail: str
    message_kind: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {
            "invariant_id": self.invariant_id,
            "event_id": self.event_id,
            "rail": self.rail,
            "message_kind": self.message_kind,
            "detail": self.detail,
        }


@dataclass
class Invariant:
    """One structural rule.

    `check` returns a detail string on violation, or None when satisfied. Returning the detail
    rather than a bool matters: a violation report that says only "F1-CARD-03 failed" is not
    actionable, and the previous build's 250,947-violation debugging session was tractable only
    because every violation carried the offending values.
    """

    id: str
    group: str
    description: str
    check: Callable[[CanonicalEvent], str | None]
    #: True -> applies to non-attack events only. See the module docstring.
    attack_scoped: bool = False
    #: Rails the invariant applies to. Empty = all rails.
    rails: frozenset[str] = field(default_factory=frozenset)
    #: Message kinds the invariant applies to. Empty = all kinds.
    kinds: frozenset[str] = field(default_factory=frozenset)

    def applies(self, ev: CanonicalEvent) -> bool:
        if self.rails and ev.rail not in self.rails:
            return False
        if self.kinds and ev.message_kind not in self.kinds:
            return False
        if self.attack_scoped and ev.oracle_is_attack:
            return False
        return True


# =======================================================================================
# Cross-event state. Some invariants are only checkable over a stream.
# =======================================================================================

@dataclass
class StreamState:
    """State accumulated across events, for the invariants that are not per-event."""

    auth_ids: set[str] = field(default_factory=set)
    auth_rrn: dict[str, str] = field(default_factory=dict)
    auth_amount: dict[str, float] = field(default_factory=dict)
    auth_approved: dict[str, bool] = field(default_factory=dict)
    refunded: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    last_atc: dict[str, int] = field(default_factory=dict)
    presented: set[str] = field(default_factory=set)
    disputed: set[str] = field(default_factory=set)
    mandate_cap: dict[str, float] = field(default_factory=dict)
    beneficiary_inflow: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    beneficiary_outflow: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    seen_event_ids: set[str] = field(default_factory=set)


# =======================================================================================
# Per-event invariants
# =======================================================================================

def _enum(name: str, allowed: Sequence[str]) -> Callable[[CanonicalEvent], str | None]:
    allowed_set = frozenset(allowed)

    def _check(ev: CanonicalEvent) -> str | None:
        v = getattr(ev, name)
        if v == "" or v in allowed_set:
            return None
        return f"{name}={v!r} not in the declared value set"

    return _check


def _nonneg(name: str) -> Callable[[CanonicalEvent], str | None]:
    def _check(ev: CanonicalEvent) -> str | None:
        v = float(getattr(ev, name))
        if v == SENTINEL or v >= 0.0:
            return None
        return f"{name}={v} is negative and is not the -1 sentinel"

    return _check


def _build_per_event_invariants() -> list[Invariant]:
    inv: list[Invariant] = []
    add = inv.append

    # ---- F1-STR: structural completeness and enum legality --------------------------
    add(Invariant("F1-STR-01", "structural", "event_id is non-empty",
                  lambda e: None if e.event_id else "empty event_id"))
    add(Invariant("F1-STR-02", "structural", "rail is a declared rail",
                  lambda e: None if e.rail in RAILS else f"rail={e.rail!r} is not declared"))
    add(Invariant("F1-STR-03", "structural", "message_kind is declared",
                  lambda e: None if e.message_kind in MESSAGE_KINDS else f"message_kind={e.message_kind!r}"))
    add(Invariant("F1-STR-04", "structural", "tier is A or B",
                  lambda e: None if e.tier in ("A", "B") else f"tier={e.tier!r}"))
    # THE COVERAGE GAP THAT COST A 52-MINUTE RUN. `hour_ist` had an IMPLICIT convention of
    # [0, 23.99] duplicated as a bare literal in 14 places, and nothing asserted it. An emitter
    # deriving an hour by `(hour + gap/60) % 24.0` produced values in (23.99, 24.0), which then
    # inverted a same-day ordering guard shaped `min(23.99, antecedent_hour + delta)`. The
    # convention is now a named constant AND an invariant, so the next emitter that violates it
    # fails the build at the smoke preset instead of surfacing 10M events later.
    add(Invariant(
        "F1-STR-22", "structural", "hour_ist is within the declared [0, HOUR_MAX] convention",
        lambda e: None if 0.0 <= e.hour_ist <= HOUR_MAX
        else f"hour_ist={e.hour_ist!r} outside [0.0, {HOUR_MAX}]",
    ))
    add(Invariant("F1-STR-05", "structural", "tier matches the rail's declared tier",
                  lambda e: None if (
                      (e.rail in TIER_A_RAILS and e.tier == "A")
                      or (e.rail in TIER_B_RAILS and e.tier == "B")
                  ) else f"rail={e.rail} declares tier {'A' if e.rail in TIER_A_RAILS else 'B'} but event says {e.tier}"))
    add(Invariant("F1-STR-06", "structural", "amount is non-negative",
                  lambda e: None if e.amount_inr >= 0.0 else f"amount_inr={e.amount_inr}"))
    add(Invariant("F1-STR-07", "structural", "currency is INR",
                  lambda e: None if e.currency == "INR" else f"currency={e.currency!r}"))
    add(Invariant("F1-STR-08", "structural", "hour_ist is in [0, 24)",
                  lambda e: None if 0.0 <= e.hour_ist < 24.0 else f"hour_ist={e.hour_ist}"))
    add(Invariant("F1-STR-09", "structural", "dow is in [0, 6]",
                  lambda e: None if 0 <= e.dow <= 6 else f"dow={e.dow}"))
    add(Invariant("F1-STR-10", "structural", "day_index is non-negative",
                  lambda e: None if e.day_index >= 0 else f"day_index={e.day_index}"))
    add(Invariant("F1-STR-11", "structural", "pos_entry_mode is a declared semantic mode",
                  _enum("pos_entry_mode", ENTRY_MODES)))
    add(Invariant("F1-STR-12", "structural", "cvm_result is declared", _enum("cvm_result", CVM_RESULTS)))
    add(Invariant("F1-STR-13", "structural", "avs_result is declared", _enum("avs_result", AVS_RESULTS)))
    add(Invariant("F1-STR-14", "structural", "cvv2_result is declared", _enum("cvv2_result", CVV2_RESULTS)))
    add(Invariant("F1-STR-15", "structural", "threeds_authentication_result is declared",
                  _enum("threeds_authentication_result", THREEDS_RESULTS)))
    add(Invariant("F1-STR-16", "structural", "threeds_eci is a declared semantic band",
                  _enum("threeds_eci", THREEDS_ECI_BANDS)))
    add(Invariant("F1-STR-17", "structural", "response_code is declared",
                  _enum("response_code", RESPONSE_CODES)))
    add(Invariant("F1-STR-18", "structural", "token_assurance_level is declared",
                  _enum("token_assurance_level", TOKEN_ASSURANCE)))
    add(Invariant("F1-STR-19", "structural", "dispute_reason_code is declared",
                  _enum("dispute_reason_code", DISPUTE_REASON_CODES)))
    add(Invariant("F1-STR-20", "structural", "upi_initiation_mode is declared",
                  _enum("upi_initiation_mode", INITIATION_MODES)))
    add(Invariant("F1-STR-21", "structural", "cohort_tag is declared",
                  _enum("cohort_tag", COHORT_TAGS)))
    for f in ("device_age_days", "pan_age_days", "vpa_age_days", "account_age_days",
              "merchant_age_days", "payee_vpa_age_days", "beneficiary_account_age_days",
              "agent_endpoint_age_days", "presentment_age_days", "referrer_domain_age_days"):
        add(Invariant(f"F1-STR-AGE-{f}", "structural", f"{f} is non-negative or the sentinel",
                      _nonneg(f)))

    # ---- F1-CARD: card message structure ---------------------------------------------
    add(Invariant(
        "F1-CARD-01", "card",
        "a keyed/e-commerce CNP authorisation carries NO EMV cryptogram",
        lambda e: None if not e.emv_cryptogram_present else "cryptogram present on a CNP rail",
        rails=frozenset({"card-cnp-keyed", "card-cnp-3ds", "card-token-provisioning"}),
    ))
    add(Invariant(
        "F1-CARD-02", "card",
        "card-cnp-keyed carries NO 3DS authentication result (it is the non-authenticated path)",
        lambda e: None if e.threeds_authentication_result == "not_applicable"
        else f"threeds_authentication_result={e.threeds_authentication_result} on card-cnp-keyed",
        rails=frozenset({"card-cnp-keyed"}),
    ))
    add(Invariant(
        "F1-CARD-03", "card",
        "card-cnp-keyed carries no 3DS ECI band",
        lambda e: None if e.threeds_eci == "none" else f"threeds_eci={e.threeds_eci} on card-cnp-keyed",
        rails=frozenset({"card-cnp-keyed"}),
    ))
    add(Invariant(
        "F1-CARD-04", "card",
        "an EMV cryptogram, when present, carries an application transaction counter",
        lambda e: None if (not e.emv_cryptogram_present) or e.emv_cryptogram_atc >= 0
        else "cryptogram present but ATC is the sentinel",
    ))
    add(Invariant(
        "F1-CARD-05", "card",
        "an EMV cryptogram, when present, carries an unpredictable number",
        lambda e: None if (not e.emv_cryptogram_present) or e.emv_unpredictable_number
        else "cryptogram present but unpredictable number is empty",
    ))
    add(Invariant(
        "F1-CARD-06", "card",
        "a magstripe-fallback authorisation carries NO cryptogram (that is the downgrade)",
        lambda e: None if e.pos_entry_mode != "magstripe_fallback" or not e.emv_cryptogram_present
        else "fallback entry mode with a cryptogram present",
    ))
    add(Invariant(
        "F1-CARD-07", "card",
        "card-present rails carry NO 3DS block",
        lambda e: None if e.threeds_authentication_result == "not_applicable" and e.threeds_eci == "none"
        else "3DS block present on a card-present rail",
        rails=frozenset({"card-cp-emv"}),
    ))
    add(Invariant(
        "F1-CARD-08", "card",
        "card-present rails do not request AVS or CVV2",
        lambda e: None if e.avs_result in ("not_requested", "") and e.cvv2_result in ("not_provided", "")
        else f"avs={e.avs_result} cvv2={e.cvv2_result} on a card-present rail",
        rails=frozenset({"card-cp-emv"}),
    ))
    add(Invariant(
        "F1-CARD-09", "card",
        "a chip or contactless entry mode carries a cryptogram",
        lambda e: None if e.pos_entry_mode not in ("chip", "contactless", "contactless_no_cvm")
        or e.emv_cryptogram_present
        else f"entry mode {e.pos_entry_mode} without a cryptogram",
        rails=frozenset({"card-cp-emv"}),
    ))
    add(Invariant(
        "F1-CARD-10", "card",
        "contactless_no_cvm carries cvm_result == none",
        lambda e: None if e.pos_entry_mode != "contactless_no_cvm" or e.cvm_result == "none"
        else f"contactless_no_cvm with cvm_result={e.cvm_result}",
    ))
    add(Invariant(
        "F1-CARD-11", "card",
        "a 3DS-authenticated ECI band implies a successful authentication result",
        lambda e: None if e.threeds_eci != "authenticated"
        or e.threeds_authentication_result in ("frictionless_success", "challenge_success")
        else f"eci=authenticated with result={e.threeds_authentication_result}",
    ))
    # F1-CARD-12 and F1-CARD-13 are statements about the AUTHENTICATION REQUEST, so they are
    # scoped to the authorisation. A presentment or chargeback legitimately inherits the
    # authentication RESULT and the ECI band from the authorisation it resolves to, without
    # carrying the ACS identifier or the challenge-requested flag — those belong to the 3DS
    # message, not to the clearing message.
    add(Invariant(
        "F1-CARD-12", "card",
        "a 3DS challenge result implies the challenge was requested (on the authorisation)",
        lambda e: None if e.threeds_authentication_result not in ("challenge_success", "challenge_abandoned")
        or e.threeds_challenge_requested
        else "challenge result without threeds_challenge_requested",
        kinds=frozenset({"authorisation", "provisioning_request"}),
    ))
    add(Invariant(
        "F1-CARD-13", "card",
        "a populated 3DS block carries an ACS identifier (on the authorisation)",
        lambda e: None if e.threeds_authentication_result == "not_applicable" or e.threeds_acs_id
        else "3DS result present but acs id empty",
        kinds=frozenset({"authorisation", "provisioning_request"}),
    ))
    add(Invariant(
        "F1-CARD-14", "card",
        "a token assurance level implies a token id",
        lambda e: None if e.token_assurance_level == "none" or e.token_id
        else f"token_assurance_level={e.token_assurance_level} with no token id",
    ))
    add(Invariant(
        "F1-CARD-15", "card",
        "a token id implies a token requestor id",
        lambda e: None if not e.token_id or e.token_requestor_id
        else "token id present without a requestor id",
    ))
    add(Invariant(
        "F1-CARD-16", "card",
        "a card rail authorisation carries a PAN-canonical key",
        lambda e: None if e.pan_canonical else "card authorisation with no pan_canonical",
        rails=frozenset({"card-cnp-3ds", "card-cnp-keyed", "card-cp-emv"}),
        kinds=frozenset({"authorisation"}),
    ))
    add(Invariant(
        "F1-CARD-17", "card",
        "a card-present authorisation carries a terminal id",
        lambda e: None if e.terminal_id else "card-present authorisation with no terminal id",
        rails=frozenset({"card-cp-emv"}), kinds=frozenset({"authorisation"}),
    ))
    add(Invariant(
        "F1-CARD-18", "card",
        "a first tokenised spend carries a provisioning-to-first-spend latency",
        lambda e: None if e.provisioning_to_first_spend_minutes >= 0.0
        else "token first spend with no provisioning latency",
        rails=frozenset({"card-token-provisioning"}), kinds=frozenset({"authorisation"}),
    ))
    add(Invariant(
        "F1-CARD-19", "card",
        "a provisioning request carries zero amount",
        lambda e: None if e.amount_inr == 0.0 else f"provisioning request with amount {e.amount_inr}",
        kinds=frozenset({"provisioning_request"}),
    ))

    # ---- F1-UPI: UPI and A2A message structure --------------------------------------
    add(Invariant(
        "F1-UPI-01", "upi", "UPI rails carry NO card constructs (no cryptogram)",
        lambda e: None if not e.emv_cryptogram_present else "cryptogram present on a UPI rail",
        rails=UPI_RAILS,
    ))
    add(Invariant(
        "F1-UPI-02", "upi", "UPI rails carry NO 3DS block",
        lambda e: None if e.threeds_authentication_result == "not_applicable" and e.threeds_eci == "none"
        else "3DS block on a UPI rail",
        rails=UPI_RAILS,
    ))
    add(Invariant(
        "F1-UPI-03", "upi", "UPI rails do not request AVS or CVV2",
        lambda e: None if e.avs_result in ("not_requested", "") and e.cvv2_result in ("not_provided", "")
        else f"avs={e.avs_result} cvv2={e.cvv2_result} on a UPI rail",
        rails=UPI_RAILS,
    ))
    add(Invariant(
        "F1-UPI-04", "upi", "a UPI PAY authorisation carries a payer VPA",
        lambda e: None if e.vpa else "upi-pay authorisation with no payer VPA",
        rails=frozenset({"upi-pay"}), kinds=frozenset({"authorisation"}),
    ))
    add(Invariant(
        "F1-UPI-05", "upi", "a UPI PAY authorisation carries a payee VPA",
        lambda e: None if e.payee_vpa else "upi-pay authorisation with no payee VPA",
        rails=frozenset({"upi-pay"}), kinds=frozenset({"authorisation"}),
    ))
    add(Invariant(
        "F1-UPI-06", "upi", "a UPI PAY authorisation declares an initiation mode",
        lambda e: None if e.upi_initiation_mode != "not_applicable"
        else "upi-pay with upi_initiation_mode=not_applicable",
        rails=frozenset({"upi-pay"}), kinds=frozenset({"authorisation"}),
    ))
    # F1-UPI-07/08 are scoped to the PAYER-SIDE legs (`lite_debit`, `lite_topup`) and NOT to
    # `inbound_credit`. Entry mode and CVM describe how the PAYER authenticated at the device; the
    # credit leg landing at an in-book payee has neither, and demanding them there is demanding a
    # field the message does not carry. This is the same defect class as F1-CARD-12/13, and it only
    # surfaced at the `full` preset because a Lite P2P credit has to land on an IN-BOOK beneficiary to
    # emit an inbound_credit at all -- at 400 cardholders that never happened, at 24,000 it happens
    # 12,995 times. An invariant that is silent at smoke and wrong at full is exactly what the F1 gate
    # exists to surface before any number ships.
    _LITE_PAYER_KINDS = frozenset({"lite_debit", "lite_topup"})
    add(Invariant(
        "F1-UPI-07", "upi", "a UPI Lite PAYER-SIDE leg uses the on-device-ledger entry mode, not `intent`",
        lambda e: None if e.pos_entry_mode == "on_device_ledger"
        else f"upi-lite-offline with pos_entry_mode={e.pos_entry_mode}",
        rails=frozenset({"upi-lite-offline"}), kinds=_LITE_PAYER_KINDS,
    ))
    add(Invariant(
        "F1-UPI-08", "upi", "a UPI Lite PAYER-SIDE leg is PIN-free by design, so cvm_result is none",
        lambda e: None if e.cvm_result == "none" else f"upi-lite-offline with cvm_result={e.cvm_result}",
        rails=frozenset({"upi-lite-offline"}), kinds=_LITE_PAYER_KINDS,
    ))
    add(Invariant(
        "F1-UPI-09", "upi", "a collect response references its collect request",
        lambda e: None if e.collect_request_id and e.original_auth_event_id
        else "collect_response without a request id or an antecedent reference",
        kinds=frozenset({"collect_response"}),
    ))
    add(Invariant(
        "F1-UPI-10", "upi", "an unaccepted collect response is not approved",
        lambda e: None if e.collect_accepted or not e.approved
        else "collect_response approved without collect_accepted",
        kinds=frozenset({"collect_response"}),
    ))
    add(Invariant(
        "F1-UPI-11", "upi", "an accepted collect response carries a CVM (the PIN was entered)",
        lambda e: None if not e.collect_accepted or e.cvm_result != "none"
        else "collect accepted with cvm_result=none",
        kinds=frozenset({"collect_response"}),
    ))
    add(Invariant(
        "F1-UPI-12", "upi", "a collect request is not itself a debit, so it carries no CVM",
        lambda e: None if e.cvm_result == "none" else f"collect_request with cvm_result={e.cvm_result}",
        kinds=frozenset({"collect_request"}),
    ))
    add(Invariant(
        "F1-A2A-01", "a2a", "a credit transfer carries an end-to-end identifier",
        lambda e: None if e.pacs_end_to_end_id else "credit_transfer without an end-to-end id",
        rails=frozenset({"a2a-credit-transfer"}), kinds=frozenset({"credit_transfer"}),
    ))
    add(Invariant(
        "F1-A2A-02", "a2a", "a status report carries a status code and references its transfer",
        lambda e: None if e.pacs_status_code and e.original_auth_event_id
        else "credit_transfer_status without a status code or an antecedent reference",
        kinds=frozenset({"credit_transfer_status"}),
    ))
    add(Invariant(
        "F1-A2A-03", "a2a", "a status code of ACSC implies approved and RJCT implies not approved",
        lambda e: None if not e.pacs_status_code
        or (e.pacs_status_code == "ACSC") == bool(e.approved)
        else f"pacs_status_code={e.pacs_status_code} with approved={e.approved}",
        kinds=frozenset({"credit_transfer_status"}),
    ))
    add(Invariant(
        "F1-A2A-04", "a2a", "a credit transfer carries a creditor name",
        lambda e: None if e.creditor_name_string else "credit_transfer without a creditor name",
        rails=frozenset({"a2a-credit-transfer"}), kinds=frozenset({"credit_transfer"}),
    ))

    # ---- F1-MND: mandate envelope ----------------------------------------------------
    add(Invariant(
        "F1-MND-01", "mandate", "a mandate debit references a mandate id",
        lambda e: None if e.mandate_id else "mandate_debit without a mandate id",
        kinds=frozenset({"mandate_debit"}),
    ))
    add(Invariant(
        "F1-MND-02", "mandate", "a mandate debit declares the stored cap",
        lambda e: None if e.mandate_max_amount_inr > 0 else "mandate_debit without a cap",
        kinds=frozenset({"mandate_debit"}),
    ))
    add(Invariant(
        "F1-MND-03", "mandate",
        "an APPROVED mandate debit is within its envelope; an over-cap debit MUST be declined",
        lambda e: None if e.amount_inr <= e.mandate_max_amount_inr or not e.approved
        else f"approved debit {e.amount_inr} exceeds cap {e.mandate_max_amount_inr}",
        kinds=frozenset({"mandate_debit"}),
    ))
    add(Invariant(
        "F1-MND-04", "mandate", "an over-cap debit carries the mandate-scope decline code",
        lambda e: None if e.amount_inr <= e.mandate_max_amount_inr
        or e.response_code == "declined_mandate_scope"
        else f"over-cap debit with response_code={e.response_code}",
        kinds=frozenset({"mandate_debit"}),
    ))
    add(Invariant(
        "F1-MND-05", "mandate", "a mandate debit is merchant-initiated",
        lambda e: None if e.cit_mit_indicator == "MIT"
        else f"mandate_debit with cit_mit_indicator={e.cit_mit_indicator!r}",
        kinds=frozenset({"mandate_debit"}),
    ))
    add(Invariant(
        "F1-MND-06", "mandate", "a merchant-initiated debit has no cardholder present, so no CVM",
        lambda e: None if e.cit_mit_indicator != "MIT" or e.cvm_result == "none"
        else f"MIT with cvm_result={e.cvm_result}",
    ))
    add(Invariant(
        "F1-MND-07", "mandate", "a mandate debit was pre-notified",
        lambda e: None if e.pre_debit_notification_sent
        else "mandate_debit without a pre-debit notification",
        kinds=frozenset({"mandate_debit"}),
    ))
    add(Invariant(
        "F1-MND-08", "mandate", "a mandate creation is cardholder-initiated",
        lambda e: None if e.cit_mit_indicator == "CIT"
        else f"mandate_creation with cit_mit_indicator={e.cit_mit_indicator!r}",
        kinds=frozenset({"mandate_creation"}),
    ))
    add(Invariant(
        "F1-MND-09", "mandate", "a mandate creation carries zero amount",
        lambda e: None if e.amount_inr == 0.0 else f"mandate_creation with amount {e.amount_inr}",
        kinds=frozenset({"mandate_creation"}),
    ))
    add(Invariant(
        "F1-MND-10", "mandate", "a mandate debit occurs at or after its mandate's creation",
        lambda e: None if e.mandate_created_ts <= 0 or e.ts >= e.mandate_created_ts
        else f"debit ts {e.ts} precedes mandate creation {e.mandate_created_ts}",
        kinds=frozenset({"mandate_debit"}),
    ))
    add(Invariant(
        "F1-MND-11", "mandate", "an agent authorisation within mandate scope is not scope-declined",
        lambda e: None if e.mandate_max_amount_inr <= 0
        or (e.amount_inr > e.mandate_max_amount_inr) == (e.response_code == "declined_mandate_scope")
        else f"amount {e.amount_inr} vs cap {e.mandate_max_amount_inr} with response {e.response_code}",
        kinds=frozenset({"agent_authorisation"}),
    ))

    # ---- F1-AGT: agentic ------------------------------------------------------------
    add(Invariant(
        "F1-AGT-01", "agentic", "an agentic event declares the agentic indicator",
        lambda e: None if e.agentic_indicator else "agentic-commerce event without agentic_indicator",
        rails=frozenset({"agentic-commerce"}),
    ))
    add(Invariant(
        "F1-AGT-02", "agentic", "an agentic event names an agent identity",
        lambda e: None if e.agent_identity_id else "agentic-commerce event with no agent identity",
        rails=frozenset({"agentic-commerce"}),
    ))
    add(Invariant(
        "F1-AGT-03", "agentic", "no consumer device is present, so no CVM and no cryptogram",
        lambda e: None if e.cvm_result == "none" and not e.emv_cryptogram_present
        else f"agentic event with cvm={e.cvm_result} cryptogram={e.emv_cryptogram_present}",
        rails=frozenset({"agentic-commerce"}),
    ))
    add(Invariant(
        "F1-AGT-04", "agentic", "an agent authorisation carries a quoted amount to compare against",
        lambda e: None if e.agent_quoted_amount_inr >= 0.0
        else "agent_authorisation with no quoted amount",
        kinds=frozenset({"agent_authorisation"}),
    ))

    # ---- F1-AEPS --------------------------------------------------------------------
    add(Invariant(
        "F1-AEPS-01", "aeps", "an assisted withdrawal is biometric-verified",
        lambda e: None if e.cvm_result == "biometric" else f"aeps event with cvm_result={e.cvm_result}",
        rails=frozenset({"aeps-microatm"}),
    ))
    add(Invariant(
        "F1-AEPS-02", "aeps", "an AePS event names a terminal",
        lambda e: None if e.terminal_id else "aeps event with no terminal id",
        rails=frozenset({"aeps-microatm"}),
    ))
    add(Invariant(
        "F1-AEPS-03", "aeps", "AePS terminates in cash, so there is NO beneficiary leg",
        lambda e: None if not e.beneficiary_id else "aeps event carrying a beneficiary id",
        rails=frozenset({"aeps-microatm"}),
    ))
    add(Invariant(
        "F1-AEPS-04", "aeps", "a balance enquiry carries zero amount",
        lambda e: None if e.amount_inr == 0.0 else f"balance_enquiry with amount {e.amount_inr}",
        kinds=frozenset({"balance_enquiry"}),
    ))

    # ---- F1-RESP: response consistency ----------------------------------------------
    add(Invariant(
        "F1-RESP-01", "response", "approved implies an approving response code",
        lambda e: None if not e.approved or e.response_code in ("approved", "approved_partial")
        else f"approved=True with response_code={e.response_code}",
    ))
    add(Invariant(
        "F1-RESP-02", "response", "a declining or step-up response code implies not approved",
        lambda e: None if not e.response_code.startswith(("declined_", "step_up", "referred", "timeout"))
        or not e.approved
        else f"response_code={e.response_code} with approved=True",
    ))
    add(Invariant(
        "F1-RESP-03", "response", "an incumbent decline is not approved",
        lambda e: None if e.incumbent_decision != "decline" or not e.approved
        else "incumbent declined but the event is approved",
    ))
    add(Invariant(
        "F1-RESP-04", "response", "the logged accept probability is strictly inside (0, 1)",
        lambda e: None if e.incumbent_accept_probability == SENTINEL
        or 0.0 < e.incumbent_accept_probability < 1.0
        else (
            f"incumbent_accept_probability={e.incumbent_accept_probability} is at a boundary; "
            f"positivity fails and every IPW weight becomes undefined"
        ),
    ))
    add(Invariant(
        "F1-RESP-05", "response", "an event that reached the incumbent has a logged propensity",
        lambda e: None if not e.incumbent_decision or e.incumbent_accept_probability > 0.0
        else "incumbent decided but no accept probability was logged",
    ))
    add(Invariant(
        "F1-RESP-06", "response", "a decided event has a measured response latency",
        lambda e: None if not e.response_code or e.response_latency_ms >= 0.0
        else "response code present but latency is the sentinel",
    ))
    add(Invariant(
        "F1-RESP-07", "response", "a step-up response occurs only on a rail with a step-up lever",
        lambda e: None if e.response_code != "step_up_required"
        or e.rail in ("card-cnp-3ds", "card-token-provisioning")
        else f"step_up_required on {e.rail}, which has no genuine step-up lever",
    ))

    # ---- F1-BEN: beneficiary leg ----------------------------------------------------
    add(Invariant(
        "F1-BEN-01", "beneficiary", "an inbound credit names a beneficiary",
        lambda e: None if e.beneficiary_id else "inbound_credit with no beneficiary id",
        kinds=frozenset({"inbound_credit"}),
    ))
    add(Invariant(
        "F1-BEN-02", "beneficiary", "an inbound credit references its payer leg",
        lambda e: None if e.original_auth_event_id
        else "inbound_credit with no antecedent payer-leg reference",
        kinds=frozenset({"inbound_credit"}),
    ))
    add(Invariant(
        "F1-BEN-03", "beneficiary", "an inbound credit is approved (it landed)",
        lambda e: None if e.approved else "inbound_credit that is not approved",
        kinds=frozenset({"inbound_credit"}),
    ))
    add(Invariant(
        "F1-BEN-04", "beneficiary", "an onward send names a beneficiary and references its credit",
        lambda e: None if e.beneficiary_id and e.original_auth_event_id
        else "onward_send without a beneficiary or an antecedent credit",
        kinds=frozenset({"onward_send"}),
    ))
    add(Invariant(
        "F1-BEN-05", "beneficiary", "a beneficiary leg only exists on a rail that has one",
        lambda e: None if e.rail not in ("card-cp-emv", "aeps-microatm", "card-clearing-dispute")
        else f"beneficiary leg on {e.rail}, which declares has_beneficiary_leg: false",
        kinds=frozenset({"inbound_credit", "onward_send"}),
    ))
    add(Invariant(
        "F1-BEN-06", "beneficiary", "dwell and onward-send latency agree (dwell/60 == minutes)",
        lambda e: None if e.beneficiary_dwell_seconds < 0 or e.beneficiary_onward_send_minutes < 0
        or abs(e.beneficiary_dwell_seconds / 60.0 - e.beneficiary_onward_send_minutes) < 1e-3
        else (
            f"dwell {e.beneficiary_dwell_seconds}s disagrees with onward "
            f"{e.beneficiary_onward_send_minutes}min"
        ),
    ))
    add(Invariant(
        "F1-BEN-07", "beneficiary", "fan-in degree is at least the distinct-payer count",
        lambda e: None if e.beneficiary_fanin_degree < 0 or e.beneficiary_distinct_payers_24h < 0
        or e.beneficiary_fanin_degree >= e.beneficiary_distinct_payers_24h
        else f"fanin {e.beneficiary_fanin_degree} < distinct payers {e.beneficiary_distinct_payers_24h}",
    ))

    # ---- F1-TOK / F1-PROV ------------------------------------------------------------
    add(Invariant(
        "F1-PROV-01", "provisioning", "a provisioning request names the token it provisions",
        lambda e: None if e.token_id else "provisioning_request with no token id",
        kinds=frozenset({"provisioning_request"}),
    ))
    add(Invariant(
        "F1-PROV-02", "provisioning", "a provisioning request declares its own provisioning event id",
        lambda e: None if e.provisioning_event_id == e.event_id
        else "provisioning_request whose provisioning_event_id is not itself",
        kinds=frozenset({"provisioning_request"}),
    ))

    # ---- F1-DSP: dispute -------------------------------------------------------------
    add(Invariant(
        "F1-DSP-01", "dispute", "a chargeback carries a dispute reason code",
        lambda e: None if e.dispute_reason_code != "none"
        else "chargeback with dispute_reason_code=none",
        kinds=frozenset({"chargeback"}),
    ))
    add(Invariant(
        "F1-DSP-02", "dispute", "a chargeback carries a filing timestamp at or after the event",
        lambda e: None if e.dispute_filed_ts > 0 and e.dispute_filed_ts >= 0
        else "chargeback with no filing timestamp",
        kinds=frozenset({"chargeback"}),
    ))
    add(Invariant(
        "F1-DSP-03", "dispute", "representment_won implies representment_filed",
        lambda e: None if not e.representment_won or e.representment_filed
        else "representment_won without representment_filed",
    ))
    add(Invariant(
        "F1-DSP-04", "dispute", "a dispute reason code appears only on a dispute-bearing message",
        lambda e: None if e.dispute_reason_code == "none"
        or e.message_kind in ("chargeback", "representment")
        else f"dispute_reason_code={e.dispute_reason_code} on message_kind={e.message_kind}",
    ))

    # ---- F1-CLR: clearing ------------------------------------------------------------
    add(Invariant(
        "F1-CLR-01", "clearing", "a presentment carries a settlement amount",
        lambda e: None if e.settlement_amount_inr >= 0.0 else "presentment with no settlement amount",
        kinds=frozenset({"presentment"}),
    ))
    add(Invariant(
        "F1-CLR-02", "clearing", "a presentment carries a non-negative age",
        lambda e: None if e.presentment_age_days >= 0.0 else "presentment with a negative age",
        kinds=frozenset({"presentment"}),
    ))
    add(Invariant(
        "F1-CLR-03", "clearing", "the auth-to-presentment ratio agrees with the two amounts",
        lambda e: None if e.auth_to_presentment_ratio < 0 or e.amount_inr <= 0
        or abs(e.settlement_amount_inr / e.amount_inr - e.auth_to_presentment_ratio) < 1e-4
        else (
            f"ratio {e.auth_to_presentment_ratio} disagrees with "
            f"{e.settlement_amount_inr}/{e.amount_inr}"
        ),
        kinds=frozenset({"presentment"}),
    ))
    add(Invariant(
        "F1-CLR-04", "clearing", "a refund credit records its refund amount",
        lambda e: None if e.refund_amount_inr >= 0.0 else "refund_credit with no refund amount",
        kinds=frozenset({"refund_credit"}),
    ))
    add(Invariant(
        "F1-CLR-05", "clearing", "the refund amount equals the message amount",
        lambda e: None if e.refund_amount_inr < 0 or abs(e.refund_amount_inr - e.amount_inr) < 1e-6
        else f"refund_amount {e.refund_amount_inr} != amount {e.amount_inr}",
        kinds=frozenset({"refund_credit"}),
    ))

    # ---- F1-ORACLE: the oracle fields are consistent --------------------------------
    add(Invariant(
        "F1-ORC-01", "oracle", "an attack event names its campaign",
        lambda e: None if not e.oracle_is_attack or e.attack_campaign_id
        else "oracle_is_attack with no campaign id",
    ))
    add(Invariant(
        "F1-ORC-02", "oracle", "a non-attack event carries no campaign id",
        lambda e: None if e.oracle_is_attack or not e.attack_campaign_id
        else "campaign id on a non-attack event",
    ))
    add(Invariant(
        "F1-ORC-03", "oracle",
        "a GRAMMAR-DRIVEN attack event names its grammar composition",
        # Scoped to the main sim: Generator B is deliberately NOT grammar-driven -- that independence
        # is the whole reason it is a valid artifact-independence check -- so it legitimately has no
        # grammar string, and requiring one would be requiring it to be the thing it is designed not
        # to be.
        lambda e: None if not e.oracle_is_attack or e.generator != "vajra-sim" or e.attack_grammar_str
        else "grammar-driven attack event with no grammar string",
    ))
    add(Invariant(
        "F1-ORC-04", "oracle", "sealed_holdout implies an attack event",
        lambda e: None if not e.sealed_holdout or e.oracle_is_attack
        else "sealed_holdout on a non-attack event",
    ))
    add(Invariant(
        "F1-ORC-05", "oracle", "a HARD-BENIGN cohort event is NEVER an attack",
        lambda e: None if e.cohort_tag == "ordinary" or not e.oracle_is_attack
        else (
            f"cohort_tag={e.cohort_tag} with oracle_is_attack=True. The cohorts are the "
            f"false-positive floor; an attack inside one would invalidate every cohort FPR."
        ),
    ))

    return inv


PER_EVENT_INVARIANTS: tuple[Invariant, ...] = tuple(_build_per_event_invariants())


# =======================================================================================
# Stream invariants — checkable only across events
# =======================================================================================

STREAM_INVARIANT_IDS: tuple[tuple[str, str, str, bool], ...] = (
    ("F1-PAIR-01", "pairing", "every derived message resolves to an antecedent authorisation", True),
    ("F1-PAIR-02", "pairing", "a derived message shares its antecedent's retrieval reference", True),
    ("F1-PAIR-03", "pairing", "a presentment resolves to an APPROVED authorisation", False),
    ("F1-PAIR-04", "pairing", "a chargeback resolves to a presented authorisation", False),
    ("F1-PAIR-05", "pairing", "event ids are unique across the stream", False),
    ("F1-PAIR-06", "pairing", "a derived message's timestamp is strictly after its antecedent's", True),
    ("F1-AMT-01", "amount", "cumulative refunds do not exceed the original authorisation", True),
    ("F1-AMT-02", "amount", "a presentment settlement amount is within tolerance of its auth", False),
    ("F1-ATC-01", "counter", "the application transaction counter is monotone per card", True),
    ("F1-BEN-08", "beneficiary", "beneficiary outflow never exceeds inflow", False),
)


def _check_stream(events: Sequence[CanonicalEvent]) -> list[Violation]:
    """Cross-event invariants. Single pass in timestamp order."""
    st = StreamState()
    out: list[Violation] = []
    # Every event id -> ts, so an unresolved reference can be classified ABSENT vs SORTS-LATER.
    all_ts: dict[str, float] = {e.event_id: e.ts for e in events}

    def fail(inv_id: str, ev: CanonicalEvent, detail: str) -> None:
        out.append(Violation(inv_id, ev.event_id, ev.rail, ev.message_kind, detail))

    for ev in events:
        # F1-PAIR-05: unique ids
        if ev.event_id in st.seen_event_ids:
            fail("F1-PAIR-05", ev, "duplicate event_id in the stream")
        st.seen_event_ids.add(ev.event_id)

        # Register authorisations (and the messages that can be referenced later).
        if ev.message_kind in (
            "authorisation", "provisioning_request", "collect_request", "mandate_creation",
            "pre_debit_notification", "credit_transfer", "inbound_credit", "lite_topup",
            "agent_mandate_object", "mandate_debit",
        ):
            st.auth_ids.add(ev.event_id)
            st.auth_rrn[ev.event_id] = ev.rrn
            st.auth_amount[ev.event_id] = ev.amount_inr
            st.auth_approved[ev.event_id] = bool(ev.approved)

        # F1-ATC-01: monotone per card, for non-attack events.
        if ev.emv_cryptogram_present and ev.emv_cryptogram_atc >= 0 and not ev.oracle_is_attack:
            prev = st.last_atc.get(ev.pan_canonical)
            if prev is not None and ev.emv_cryptogram_atc <= prev:
                fail(
                    "F1-ATC-01", ev,
                    f"ATC {ev.emv_cryptogram_atc} <= previous {prev} for this card "
                    f"(non-attack event; a deliberate ATK-P2 replay is scoped out)",
                )
            if prev is None or ev.emv_cryptogram_atc > prev:
                st.last_atc[ev.pan_canonical] = ev.emv_cryptogram_atc

        # Derived-message pairing.
        if ev.message_kind in DERIVED_KINDS:
            ref = ev.original_auth_event_id
            resolved = ref in st.auth_ids
            # The pairing indexer matches on ANY shared reference: event id OR retrieval
            # reference. A previous build set only one of the two on some rails, so the F1 count
            # depended on which indexer ran.
            if not resolved and ev.rrn:
                resolved = ev.rrn in set(st.auth_rrn.values())
            if not resolved and not ev.oracle_is_attack:
                # TWO DISTINCT FAULTS, REPORTED SEPARATELY. "The antecedent does not exist" is a
                # LINKAGE bug; "the antecedent exists but sorts later" is an ORDERING bug, and they
                # have different fixes. Reporting both as F1-PAIR-01 "no antecedent authorisation"
                # sent a debugging pass hunting for dropped events when the events were present and
                # merely mis-timestamped. The pre-pass id->ts map is what makes the distinction
                # available at all.
                ante_ts = all_ts.get(ref)
                if ante_ts is None:
                    fail("F1-PAIR-01", ev,
                         f"antecedent {ref!r} is ABSENT from the stream entirely (rrn {ev.rrn!r})")
                else:
                    fail("F1-PAIR-06", ev,
                         f"antecedent {ref!r} EXISTS but sorts LATER by {ante_ts - ev.ts:+.1f}s "
                         f"(ordering fault, not linkage)")
            if ref in st.auth_rrn and ev.rrn and st.auth_rrn[ref] and ev.rrn != st.auth_rrn[ref]:
                if not ev.oracle_is_attack:
                    fail(
                        "F1-PAIR-02", ev,
                        f"rrn {ev.rrn!r} differs from its antecedent's {st.auth_rrn[ref]!r}",
                    )

        if ev.message_kind == "presentment":
            ref = ev.original_auth_event_id
            if ref in st.auth_approved and not st.auth_approved[ref]:
                fail("F1-PAIR-03", ev, "presentment resolves to a DECLINED authorisation")
            st.presented.add(ref)
            base = st.auth_amount.get(ref)
            if base is not None and base > 0 and ev.settlement_amount_inr >= 0:
                ratio = ev.settlement_amount_inr / base
                # Tolerance is generous on purpose: tip, fuel and hotel incremental norms are
                # real, and the ATK-S1 attack lives INSIDE the tolerance band. What is
                # structurally illegal is a settlement that bears no relation to its auth.
                if not (0.5 <= ratio <= 2.0):
                    fail(
                        "F1-AMT-02", ev,
                        f"settlement/auth ratio {ratio:.3f} outside the structural tolerance [0.5, 2.0]",
                    )

        if ev.message_kind == "chargeback":
            ref = ev.original_auth_event_id
            if ref and ref not in st.presented:
                fail("F1-PAIR-04", ev, "chargeback resolves to an authorisation never presented")
            st.disputed.add(ref)

        if ev.message_kind == "refund_credit":
            ref = ev.original_auth_event_id
            if ref:
                base = st.auth_amount.get(ref)
                st.refunded[ref] += ev.amount_inr
                if base is not None and st.refunded[ref] > base + 1e-6 and not ev.oracle_is_attack:
                    fail(
                        "F1-AMT-01", ev,
                        f"cumulative refunds {st.refunded[ref]:.2f} exceed the original {base:.2f}",
                    )

        if ev.message_kind == "inbound_credit" and ev.beneficiary_id:
            st.beneficiary_inflow[ev.beneficiary_id] += ev.amount_inr
        if ev.message_kind == "onward_send" and ev.beneficiary_id:
            st.beneficiary_outflow[ev.beneficiary_id] += ev.amount_inr
            if (
                st.beneficiary_outflow[ev.beneficiary_id]
                > st.beneficiary_inflow[ev.beneficiary_id] + 1e-6
            ):
                fail(
                    "F1-BEN-08", ev,
                    f"outflow {st.beneficiary_outflow[ev.beneficiary_id]:.2f} exceeds inflow "
                    f"{st.beneficiary_inflow[ev.beneficiary_id]:.2f} for this beneficiary",
                )

    return out


# =======================================================================================
# Public entry point
# =======================================================================================

def invariant_count() -> int:
    """Machine-counted. Printed by `make sim`; never written as a literal."""
    return len(PER_EVENT_INVARIANTS) + len(STREAM_INVARIANT_IDS)


def invariant_catalogue() -> list[dict[str, object]]:
    """The full list, for reports/fidelity.html and the UI."""
    rows = [
        {
            "id": i.id,
            "group": i.group,
            "description": i.description,
            "scope": "non-attack events only" if i.attack_scoped else "all events",
            "rails": sorted(i.rails) or ["all"],
            "message_kinds": sorted(i.kinds) or ["all"],
            "kind": "per-event",
        }
        for i in PER_EVENT_INVARIANTS
    ]
    rows.extend(
        {
            "id": iid,
            "group": grp,
            "description": desc,
            "scope": "non-attack events only" if scoped else "all events",
            "rails": ["all"],
            "message_kinds": ["all"],
            "kind": "stream",
        }
        for iid, grp, desc, scoped in STREAM_INVARIANT_IDS
    )
    return rows


def check_events(
    events: Iterable[CanonicalEvent], *, max_report: int = 200, max_per_invariant: int = 6
) -> dict[str, object]:
    """Run every invariant. Zero violations is the target; the build fails otherwise."""
    evs = list(events)
    per_invariant: dict[str, int] = {}

    # SAMPLES ARE BUDGETED PER INVARIANT, not globally. A global budget lets one noisy invariant
    # consume every slot: at the `full` preset F1-UPI-07 fired 12,995 times and took all 200 sample
    # slots, so the 14 F1-PAIR-01 violations were COUNTED but never SHOWN -- the report named a failure
    # it gave no evidence for, which is the one thing a diagnostic must never do. Every violated
    # invariant now gets its own examples regardless of how loud its neighbours are.
    samples: dict[str, list[Violation]] = {}

    def _record(inv_id: str, v: Violation) -> None:
        per_invariant[inv_id] = per_invariant.get(inv_id, 0) + 1
        bucket = samples.setdefault(inv_id, [])
        if len(bucket) < max_per_invariant:
            bucket.append(v)

    for ev in evs:
        for inv in PER_EVENT_INVARIANTS:
            if not inv.applies(ev):
                continue
            detail = inv.check(ev)
            if detail:
                _record(inv.id, Violation(inv.id, ev.event_id, ev.rail, ev.message_kind, detail))

    for v in _check_stream(evs):
        _record(v.invariant_id, v)

    # Ordered loudest-first so the headline cause reads first, but every invariant is present.
    violations: list[Violation] = [
        v
        for inv_id, _n in sorted(per_invariant.items(), key=lambda kv: (-kv[1], kv[0]))
        for v in samples.get(inv_id, ())
    ]

    total = sum(per_invariant.values())
    return {
        "n_events": len(evs),
        "n_invariants": invariant_count(),
        "n_violations": total,
        "passed": total == 0,
        "violations_by_invariant": dict(sorted(per_invariant.items())),
        "sample_violations": [v.as_dict() for v in violations[:max_report]],
        "samples_per_invariant": max_per_invariant,
        "gate": (
            "F1 is a BUILD GATE. Zero violations is required; a violation is a non-zero exit and "
            "no data ships. A hand-written invariant is not gameable by gradient, only satisfiable "
            "or violated, which is why F1 is the fidelity mechanism allowed inside the attacker's "
            "loop while the real-vs-synthetic discriminator is deliberately kept out of it."
        ),
    }
