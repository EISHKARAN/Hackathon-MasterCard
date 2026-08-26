"""The CanonicalEvent schema — one schema for all rails.

TWO RULES THIS MODULE ENFORCES, both of which are commitments rather than conveniences:

1.  **Semantic field-group names on every surface.** `emv_cryptogram_atc`, `threeds_eci`,
    `cvm_result`, `avs_result`, `acceptor_descriptor`. Exact ISO/network field numbering lives
    ONLY in sim/field_map.yaml with a per-entry `verified: true|false`, and never reaches a
    screen. One wrong subelement number spoken confidently to a payments judge costs the room;
    this is the structural protection against that, not a style guide.

2.  **Labels are NEVER a column on the event.** There is no `is_fraud` field below and there
    never will be. Labels live in an append-only table keyed `(event_id, channel, as_of_ts,
    label)` and every training or evaluation row resolves its label through an `as_of` read.
    `attack_campaign_id` and `oracle_is_attack` DO exist, and they are simulator ground truth
    used ONLY by the evaluation harness and the reject-inference validation arm -- never by any
    feature. `tests/test_no_oracle_in_features.py` asserts no registry feature reads them.

Field order is fixed and is the Parquet column order, which is what makes the byte-stable
logical hash meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields as dataclass_fields
from functools import lru_cache
from typing import Any, ClassVar, Mapping

# ---------------------------------------------------------------------------------------
# Enumerations. Strings, not ints: a semantic value that reaches a screen must be readable.
# ---------------------------------------------------------------------------------------

RAILS: tuple[str, ...] = (
    "card-cnp-3ds",
    "card-cnp-keyed",
    "card-cp-emv",
    "card-clearing-dispute",
    "card-token-provisioning",
    "upi-pay",
    "upi-collect",
    "upi-autopay-mandate",
    "a2a-credit-transfer",
    "upi-lite-offline",
    "aeps-microatm",
    "agentic-commerce",
)

MESSAGE_KINDS: tuple[str, ...] = (
    "authorisation",
    "authorisation_advice",
    "reversal",
    "incremental_auth",
    "presentment",
    "refund_credit",
    "chargeback",
    "representment",
    "provisioning_request",
    "collect_request",
    "collect_response",
    "mandate_creation",
    "mandate_debit",
    "pre_debit_notification",
    "credit_transfer",
    "credit_transfer_status",
    "inbound_credit",
    "onward_send",
    "lite_topup",
    "lite_debit",
    "assisted_withdrawal",
    "balance_enquiry",
    "agent_mandate_object",
    "agent_authorisation",
    "onboarding_application",
    "profile_change",
)

#: Semantic entry modes. `pos_entry_mode` never carries a numeric code on any surface.
ENTRY_MODES: tuple[str, ...] = (
    "ecommerce",
    "keyed",
    "magstripe_fallback",
    "chip",
    "contactless",
    "contactless_no_cvm",
    "intent",
    "secure_intent",
    "collect",
    "qr_static",
    "qr_dynamic",
    "biometric_assisted",
    "agent",
    "on_device_ledger",
    "in_app",
    "file_upload",
)

CVM_RESULTS: tuple[str, ...] = ("none", "signature", "online_pin", "offline_pin", "cdcvm", "biometric")

AVS_RESULTS: tuple[str, ...] = ("not_requested", "no_match", "partial_match", "match", "unavailable")

CVV2_RESULTS: tuple[str, ...] = ("not_provided", "no_match", "match", "unavailable")

#: 3DS authentication outcome, semantic. `threeds_eci` is a semantic band, not a raw code.
THREEDS_RESULTS: tuple[str, ...] = (
    "not_applicable",
    "frictionless_success",
    "challenge_success",
    "challenge_abandoned",
    "attempted",
    "failed",
)

THREEDS_ECI_BANDS: tuple[str, ...] = (
    "none",
    "authenticated",
    "attempted",
    "not_authenticated",
)

RESPONSE_CODES: tuple[str, ...] = (
    "approved",
    "approved_partial",
    "declined_insufficient_funds",
    "declined_invalid_card",
    "declined_expired",
    "declined_cvv2_mismatch",
    "declined_avs_mismatch",
    "declined_do_not_honour",
    "declined_risk",
    "declined_velocity",
    "declined_mandate_scope",
    "declined_stand_in",
    "step_up_required",
    "referred",
    "timeout",
)

TOKEN_ASSURANCE: tuple[str, ...] = ("none", "low", "medium", "high")

DISPUTE_REASON_CODES: tuple[str, ...] = (
    "none",
    "fraud_card_absent",
    "fraud_card_present",
    "authorisation_issue",
    "processing_error",
    "goods_not_received",
    "goods_not_as_described",
    "cancelled_recurring",
    "credit_not_processed",
    "duplicate_processing",
)

KYC_TIERS: tuple[str, ...] = ("none", "min_kyc", "full_kyc", "video_kyc")

BENEFICIARY_CATEGORIES: tuple[str, ...] = (
    "unknown",
    "p2p_individual",
    "small_merchant",
    "biller",
    "giftcard",
    "wallet_load",
    "quasi_cash",
    "crypto_onramp",
    "payroll",
    "corporate_vendor",
)

INITIATION_MODES: tuple[str, ...] = (
    "not_applicable",
    "intent",
    "secure_intent",
    "qr_static",
    "qr_dynamic",
    "collect",
    "mandate",
    "in_app",
    "ivr",
)

COHORT_TAGS: tuple[str, ...] = (
    "ordinary",
    # HARD-BENIGN-12 (payer side)
    "hb12_bereavement",
    "hb12_wedding",
    "hb12_relocation",
    "hb12_new_phone_reprovision",
    "hb12_gig_fanin",
    "hb12_festival_travel",
    "hb12_first_high_ticket",
    "hb12_joint_account",
    "hb12_seasonal_merchant_ramp",
    "hb12_student_fee",
    "hb12_nri_remittance",
    "hb12_medical_fd_liquidation",
    # HARD-BENIGN-B (beneficiary side) — the twin that exists because HARD-BENIGN-12 does not
    # cover GATE-B's error victim at all.
    "hbb_new_gig_aggregator_payee",
    "hbb_week_old_small_merchant",
    "hbb_school_fee_collection",
    "hbb_festival_street_vendor",
    "hbb_community_chit_collection",
    "hbb_freelancer_foreign_inbound",
)

HARD_BENIGN_12_TAGS: tuple[str, ...] = tuple(t for t in COHORT_TAGS if t.startswith("hb12_"))
HARD_BENIGN_B_TAGS: tuple[str, ...] = tuple(t for t in COHORT_TAGS if t.startswith("hbb_"))


# ---------------------------------------------------------------------------------------
# The event.
# ---------------------------------------------------------------------------------------

_UNSET_F = -1.0
_UNSET_I = -1

#: THE DECLARED HOUR-OF-DAY CONVENTION. Every `hour_ist` in the stream lies in [0.0, HOUR_MAX].
#:
#: This was an IMPLICIT convention duplicated as a bare `23.99` literal in 14 places, and seven of
#: those were ordering guards shaped `min(23.99, antecedent_hour + delta)`. That shape INVERTS when
#: `antecedent_hour` already exceeds 23.99: it returns a time EARLIER than the antecedent, so a
#: derived message sorts before the message it derives from. `CardTokenProvisioningEmitter` computes
#: `(hour + gap/60) % 24.0`, which lands anywhere in [0, 24) including (23.99, 24) -- and that is
#: exactly how 14 presentments in a 10M-event run ended up timestamped before their own
#: authorisations. Naming the convention as a constant and enforcing it at `SimContext.new_event`
#: (the single chokepoint every event passes through) makes all seven guards sound at once, because
#: no antecedent hour can exceed the ceiling any guard clamps to.
HOUR_MAX: float = 23.99


@dataclass(slots=True)
class CanonicalEvent:
    """One message on any rail.

    Nullability convention: numeric fields that do not apply to a rail carry -1 (sentinel)
    rather than None, and string fields carry "" or an explicit "not_applicable". The reason is
    Parquet-side: a nullable numeric column forces a null mask into the hash and makes the
    byte-stability guarantee depend on pyarrow's null encoding. The sentinel is documented here
    and `SENTINEL_NUMERIC` is exported so features never treat -1 as a real value.
    """

    SENTINEL_NUMERIC: ClassVar[float] = _UNSET_F

    # ---- identity and time -------------------------------------------------------------
    event_id: str
    ts: float                          # sim clock, seconds since epoch
    day_index: int
    hour_ist: float
    dow: int                           # 0 = Monday, matching config/scenario.yaml start_date
    rail: str
    message_kind: str
    tier: str                          # "A" (message-level fidelity) or "B" (thin emitter)

    # ---- money -------------------------------------------------------------------------
    amount_inr: float
    currency: str = "INR"
    settlement_amount_inr: float = _UNSET_F

    # ---- the nine entity keys (canonical; the count is authoritative) -------------------
    # Nine, and any other figure elsewhere in the repo is a typo. The online store's footprint
    # claim is stated as values-per-entity-per-key-type x active entities, never a round total.
    pan_canonical: str = ""            # issuer-only: requires the token-to-PAN map
    token_id: str = ""
    token_requestor_id: str = ""
    device_fingerprint_id: str = ""
    terminal_id: str = ""
    merchant_id: str = ""              # MID
    bin_prefix: str = ""
    vpa: str = ""                      # payer VPA
    beneficiary_id: str = ""

    # ---- actors ------------------------------------------------------------------------
    cardholder_id: str = ""
    acquirer_id: str = ""
    issuer_id: str = ""
    payee_psp_id: str = ""
    agent_identity_id: str = ""
    sim_id: str = ""
    address_id: str = ""

    # ---- acceptor ----------------------------------------------------------------------
    mcc: str = ""
    acceptor_descriptor: str = ""
    acceptor_country: str = "IN"
    geo_cell: str = ""                 # geohash-like cell id
    merchant_age_days: float = _UNSET_F

    # ---- entry and verification --------------------------------------------------------
    pos_entry_mode: str = ""
    cvm_result: str = "none"
    avs_result: str = "not_requested"
    cvv2_result: str = "not_provided"
    terminal_verification_result: str = ""     # semantic summary, never raw bits
    stand_in_indicator: bool = False

    # ---- 3DS authentication block ------------------------------------------------------
    threeds_authentication_result: str = "not_applicable"
    threeds_eci: str = "none"
    threeds_acs_id: str = ""
    threeds_field_population_score: float = _UNSET_F   # share of optional fields populated
    threeds_challenge_requested: bool = False
    threeds_device_channel: str = ""
    threeds_screen_wh: str = ""
    threeds_ua_family: str = ""
    threeds_timezone_offset_min: int = _UNSET_I
    threeds_language: str = ""
    threeds_ip_asn: str = ""

    # ---- EMV cryptogram block ----------------------------------------------------------
    emv_cryptogram_present: bool = False
    emv_cryptogram_atc: int = _UNSET_I
    emv_cryptogram_verified: bool = False
    emv_unpredictable_number: str = ""
    issuer_application_data_consistent: bool = True

    # ---- tokenisation ------------------------------------------------------------------
    token_assurance_level: str = "none"
    provisioning_event_id: str = ""
    provisioning_to_first_spend_minutes: float = _UNSET_F

    # ---- mandate object ----------------------------------------------------------------
    mandate_id: str = ""
    mandate_max_amount_inr: float = _UNSET_F
    mandate_frequency: str = ""
    mandate_permitted_mcc: str = ""
    mandate_debit_count_to_date: int = _UNSET_I
    mandate_created_ts: float = _UNSET_F
    cit_mit_indicator: str = ""        # "CIT" | "MIT" | ""
    pre_debit_notification_sent: bool = False

    # ---- UPI / A2A ---------------------------------------------------------------------
    upi_initiation_mode: str = "not_applicable"
    payee_vpa: str = ""
    payee_name_string: str = ""
    payee_vpa_age_days: float = _UNSET_F
    txn_note: str = ""
    referrer_domain: str = ""
    referrer_domain_age_days: float = _UNSET_F
    collect_request_id: str = ""
    collect_accepted: bool = False
    pacs_end_to_end_id: str = ""
    pacs_status_code: str = ""
    creditor_name_string: str = ""
    creditor_name_match_score: float = _UNSET_F
    remittance_info: str = ""
    beneficiary_category: str = "unknown"
    beneficiary_change_ts: float = _UNSET_F

    # ---- beneficiary-side (GATE-B observables; payer side cannot see these) -------------
    beneficiary_account_age_days: float = _UNSET_F
    beneficiary_inbound_credit_count_24h: int = _UNSET_I
    beneficiary_distinct_payers_24h: int = _UNSET_I
    beneficiary_inflow_24h_inr: float = _UNSET_F
    beneficiary_outflow_24h_inr: float = _UNSET_F
    beneficiary_dwell_seconds: float = _UNSET_F
    beneficiary_onward_send_minutes: float = _UNSET_F
    beneficiary_fanin_degree: int = _UNSET_I
    beneficiary_fanout_degree: int = _UNSET_I
    beneficiary_first_credit_source: str = ""
    beneficiary_kyc_tier: str = "none"

    # ---- lifecycle links --------------------------------------------------------------
    original_auth_event_id: str = ""
    rrn: str = ""                      # retrieval reference, shared across a lifecycle
    trace_number: str = ""
    presentment_age_days: float = _UNSET_F
    auth_to_presentment_ratio: float = _UNSET_F
    incremental_auth_present: bool = False
    reversal_present: bool = False
    refund_amount_inr: float = _UNSET_F
    dispute_reason_code: str = "none"
    dispute_filed_ts: float = _UNSET_F
    representment_filed: bool = False
    representment_won: bool = False

    # ---- device / session -------------------------------------------------------------
    device_age_days: float = _UNSET_F
    device_model: str = ""
    device_os: str = ""
    device_rebinding_event: bool = False
    pin_reset_event: bool = False
    sms_silence_window_minutes: float = _UNSET_F
    session_id: str = ""
    session_duration_minutes: float = _UNSET_F
    in_app_dwell_seconds: float = _UNSET_F
    typing_cadence_score: float = _UNSET_F
    ip_asn: str = ""
    screen_share_app_present: bool = False     # app-SDK signal: OUTSIDE both personae (excluded)
    accessibility_permission: bool = False     # app-SDK signal: OUTSIDE both personae (excluded)

    # ---- agentic (ILLUSTRATIVE field naming; declared so in the UI) ---------------------
    agent_attestation_status: str = "not_applicable"
    agent_endpoint_age_days: float = _UNSET_F
    agent_mandate_signature_valid: bool = False
    agent_quoted_amount_inr: float = _UNSET_F
    agent_human_confirmation_event: bool = False
    agentic_indicator: bool = False

    # ---- credit line -------------------------------------------------------------------
    credit_limit_inr: float = _UNSET_F
    credit_line_activated_ts: float = _UNSET_F

    # ---- onboarding (tabular cohort table; NOT a KYC-origination simulator) ------------
    onboarding_batch_id: str = ""
    onboarding_ts: float = _UNSET_F
    name_ngram_unlikelihood: float = _UNSET_F
    address_geocode_density: float = _UNSET_F
    kyc_tier: str = "none"

    # ---- entity ages (cold-start stratification) ---------------------------------------
    pan_age_days: float = _UNSET_F
    vpa_age_days: float = _UNSET_F
    account_age_days: float = _UNSET_F

    # ---- incumbent policy shadow -------------------------------------------------------
    # The incumbent decides with an EPSILON-RANDOMISED threshold, so propensities are in (0,1)
    # and positivity actually holds. A deterministic rule engine would put propensity in {0,1},
    # leave no overlap, and make the IPW weights undefined -- which would silently void the
    # reject-inference arm rather than make it favourable.
    incumbent_score: float = _UNSET_F
    incumbent_accept_probability: float = _UNSET_F
    incumbent_decision: str = ""       # "accept" | "decline"
    incumbent_rule_fired: str = ""

    # ---- realised response -------------------------------------------------------------
    response_code: str = ""
    response_latency_ms: float = _UNSET_F
    approved: bool = False
    exemption_flag: str = ""
    reconciliation_lag_minutes: float = _UNSET_F

    # ---- two derived flags that must PERSIST to Parquet --------------------------------
    # These were scratch fields, which meant they existed only on the in-memory event and vanished
    # when the stream was written and read back. The batch training path reads Parquet, so a scratch
    # field is a feature that is present in a small in-memory run and silently absent in a real one.
    fd_liquidation_flag: bool = False
    refund_to_different_credential: bool = False

    # ---- cohort and provenance ---------------------------------------------------------
    cohort_tag: str = "ordinary"
    generator: str = "vajra-sim"       # "vajra-sim" | "generator-b"
    rng_stream: str = ""

    # ---- SIMULATOR GROUND TRUTH — evaluation harness only, never a feature -------------
    attack_campaign_id: str = ""
    attack_family_id: str = ""
    attack_grammar_str: str = ""
    attack_cell_id: str = ""
    attack_stage: str = ""
    oracle_is_attack: bool = False
    oracle_value_at_risk_inr: float = 0.0
    sealed_holdout: bool = False
    #: Which ENTITY POOL this event's actors belong to: "train" or "sealed".
    #:
    #: The sealed-family holdout has to be an ENTITY-LEVEL holdout, not a row-level one. Withholding
    #: only the sealed attack ROWS leaves the sealed campaign's cardholders, devices and
    #: beneficiaries in the training set through their BENIGN traffic — and the model then learns
    #: those entities' aggregates, including the run-up to the attack. That is the aggregate leak the
    #: entity audit exists to catch, and the only structural fix is to partition the population.
    entity_pool: str = "train"

    # Extra per-rail scratch that never reaches a feature; kept out of the Parquet schema.
    _scratch: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def as_row(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in dataclass_fields(self) if f.name != "_scratch"}


@lru_cache(maxsize=1)
def canonical_field_order() -> tuple[str, ...]:
    """The fixed Parquet column order. Derived from the dataclass, never restated."""
    return tuple(f.name for f in dataclass_fields(CanonicalEvent) if f.name != "_scratch")


@lru_cache(maxsize=1)
def canonical_field_types() -> Mapping[str, str]:
    """field -> python type name, for the schema report and the field_map consistency test."""
    out: dict[str, str] = {}
    for f in dataclass_fields(CanonicalEvent):
        if f.name == "_scratch":
            continue
        t = f.type
        out[f.name] = t if isinstance(t, str) else getattr(t, "__name__", str(t))
    return out


#: The set every signature resolver checks first.
CANONICAL_FIELDS: frozenset[str] = frozenset(canonical_field_order())

#: Fields that are simulator ORACLE ground truth. No feature may read these, ever.
ORACLE_FIELDS: frozenset[str] = frozenset(
    {
        "attack_campaign_id",
        "attack_family_id",
        "attack_grammar_str",
        "attack_cell_id",
        "attack_stage",
        "oracle_is_attack",
        "oracle_value_at_risk_inr",
        "sealed_holdout",
        "entity_pool",
    }
)

#: Fields that sit OUTSIDE both shipped personae (app-SDK / acquirer-underwriting / bureau).
#: Present because the observables are real; excluded from every scored result.
OUT_OF_PERSONA_FIELDS: frozenset[str] = frozenset(
    {
        "screen_share_app_present",
        "accessibility_permission",
        "typing_cadence_score",
        "agent_human_confirmation_event",
    }
)


def numeric_sentinel_fields() -> tuple[str, ...]:
    """Numeric fields that use the -1 sentinel, so features never treat -1 as a real value."""
    types = canonical_field_types()
    return tuple(
        name
        for name, t in types.items()
        if t in ("float", "int") and name not in ("ts", "day_index", "hour_ist", "dow", "amount_inr", "oracle_value_at_risk_inr")
    )


def field_count() -> int:
    """Machine-counted. Printed by `make sim`; never written as a literal."""
    return len(canonical_field_order())
