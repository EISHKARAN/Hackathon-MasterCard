"""Entity types and the World container.

Every identifier here is WHOLLY SYNTHETIC by construction:

*   card numbers use a **reserved non-routable issuer prefix** and are never Luhn-valid, so a
    VAJRA PAN cannot be mistaken for or used as a real one;
*   VPAs, IFSC-shaped codes and mobile numbers come from reserved/synthetic handle spaces;
*   there is no real cardholder PII anywhere, ever.

`tests/test_synthetic_identifiers.py` asserts these properties over a generated world rather
than trusting this docstring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

#: Reserved, deliberately non-routable BIN prefixes. The 999xxx space is not an assigned IIN
#: range in any scheme we are aware of, and we additionally break the Luhn check digit so a
#: generated PAN cannot be presented anywhere as a card number.
RESERVED_BIN_PREFIXES: tuple[str, ...] = (
    "999100",
    "999101",
    "999102",
    "999200",
    "999201",
    "999300",
    "999400",
    "999500",
)

#: Synthetic VPA handle space. Not a real PSP handle.
SYNTHETIC_VPA_HANDLES: tuple[str, ...] = (
    "@vajrasim",
    "@vjbank",
    "@vjpsp",
    "@vjwallet",
)


@dataclass(slots=True)
class Device:
    id: str
    model: str
    os: str
    first_seen_day: int
    asn: str
    #: Shared across a family / gig cluster. Benign density that LOOKS like fraud.
    shared_with: list[str] = field(default_factory=list)
    #: True when the device attribute bundle is deliberately implausible (ATK-G5 signature).
    cloned_bundle: bool = False


@dataclass(slots=True)
class Token:
    id: str
    pan_canonical: str
    requestor_id: str
    assurance: str
    provisioned_day: int
    device_id: str


@dataclass(slots=True)
class Cardholder:
    id: str
    pan_canonical: str
    bin_prefix: str
    vpa: str
    issuer_id: str
    open_day: int
    devices: list[str] = field(default_factory=list)
    tokens: list[str] = field(default_factory=list)
    beneficiaries: list[str] = field(default_factory=list)
    address_id: str = ""
    sim_id: str = ""
    geo_cell: str = ""
    credit_limit_inr: float = -1.0
    kyc_tier: str = "full_kyc"
    #: Lifecycle state, so account age is not a monotone proxy for activity.
    state: str = "active"          # active | dormant | closed
    dormant_since_day: int = -1
    #: Benign structural tags. These are the reason a graph feature cannot simply key on
    #: "shares a device" — real families, gig workers and joint accounts do too.
    benign_tags: list[str] = field(default_factory=list)
    cohort_tag: str = "ordinary"
    #: "train" or "sealed". Sealed-pool actors are the ENTITY-LEVEL holdout: their rows -- benign as
    #: well as attack -- are excluded from training, so no aggregate can cross the boundary.
    pool: str = "train"


@dataclass(slots=True)
class Merchant:
    id: str
    mcc: str
    descriptor: str
    acquirer_id: str
    onboard_day: int
    geo_cell: str
    terminals: list[str] = field(default_factory=list)
    #: Zipf rank, 0 = most popular. The concentration curve F5 checks is a property of this.
    popularity_rank: int = 0
    is_payfac_submerchant: bool = False
    country: str = "IN"


@dataclass(slots=True)
class Terminal:
    id: str
    merchant_id: str
    #: Terminals that still accept fallback are the ATK-P1 population.
    accepts_fallback: bool = False
    accepts_no_cvm_contactless: bool = True
    geo_cell: str = ""


@dataclass(slots=True)
class Beneficiary:
    """A receiving account. THE enforceable control point for authorised push payments.

    This is the one node in the graph that is reused across victims, that has a measurable age,
    and that must eventually move money onward. GATE-B scores it.
    """

    id: str
    payee_vpa: str
    payee_name: str
    psp_id: str
    open_day: int
    category: str = "p2p_individual"
    kyc_tier: str = "full_kyc"
    onboarding_batch_id: str = ""
    geo_cell: str = ""
    #: Running beneficiary-side state the inbound-credit scorer reads. Updated by the engine.
    inflow_inr: float = 0.0
    outflow_inr: float = 0.0
    payer_ids: set[str] = field(default_factory=set)
    first_credit_ts: float = -1.0
    last_credit_ts: float = -1.0
    first_credit_source: str = ""
    frozen_until_ts: float = -1.0
    held_amount_inr: float = 0.0
    benign_tags: list[str] = field(default_factory=list)
    cohort_tag: str = "ordinary"
    pool: str = "train"

    @property
    def in_out_skew(self) -> float:
        """|inflow - outflow| / inflow. A TIGHT skew is a mule signature.

        The threshold is a swept simulator parameter, not an empirical constant, and it is also
        an exact description of a legitimate new receiver — which is why HARD-BENIGN-B exists.
        """
        if self.inflow_inr <= 0:
            return -1.0
        return abs(self.inflow_inr - self.outflow_inr) / self.inflow_inr


@dataclass(slots=True)
class Mandate:
    id: str
    cardholder_id: str
    payee_id: str
    max_amount_inr: float
    frequency: str
    permitted_mcc: str
    created_ts: float
    debit_count: int = 0
    cumulative_inr: float = 0.0
    revoked: bool = False


@dataclass(slots=True)
class OnboardingBatch:
    """A batch of onboardings. The unit the cohort-statistics scorer operates on.

    We score the STATISTICAL FOOTPRINT OF A BATCH. We do not attempt liveness or document
    forensics and we produce no bypass knowledge — the design-only signals are listed in
    grammar/seeds.yaml under ATK-K3 and badged design-only in the UI.
    """

    id: str
    day: int
    beneficiary_ids: list[str] = field(default_factory=list)
    device_models: list[str] = field(default_factory=list)
    asns: list[str] = field(default_factory=list)
    is_attack_cohort: bool = False


@dataclass(slots=True)
class World:
    """Everything the event loop draws from. Built once, deterministically."""

    cardholders: dict[str, Cardholder] = field(default_factory=dict)
    devices: dict[str, Device] = field(default_factory=dict)
    tokens: dict[str, Token] = field(default_factory=dict)
    merchants: dict[str, Merchant] = field(default_factory=dict)
    terminals: dict[str, Terminal] = field(default_factory=dict)
    beneficiaries: dict[str, Beneficiary] = field(default_factory=dict)
    mandates: dict[str, Mandate] = field(default_factory=dict)
    onboarding_batches: dict[str, OnboardingBatch] = field(default_factory=dict)
    acquirers: list[str] = field(default_factory=list)
    issuers: list[str] = field(default_factory=list)
    psps: list[str] = field(default_factory=list)
    geo_cells: list[str] = field(default_factory=list)
    mcc_pool: list[str] = field(default_factory=list)
    #: Merchant ids ordered by Zipf popularity, so every rail samples the SAME pool.
    #: (A previous build minted merchant ids ad hoc inside the UPI and clearing emitters, which
    #: destroyed the cross-rail concentration curve F5 checks. One pool, sampled everywhere.)
    merchant_sampling_order: list[str] = field(default_factory=list)
    merchant_sampling_weights: list[float] = field(default_factory=list)

    def cardholder_ids(self) -> list[str]:
        return list(self.cardholders.keys())

    def active_cardholders(self, day: int, pool: str | None = None) -> list[str]:
        return [
            cid
            for cid, ch in self.cardholders.items()
            if ch.state == "active" and ch.open_day <= day and (pool is None or ch.pool == pool)
        ]

    def cardholders_in_pool(self, pool: str) -> list[str]:
        return [cid for cid, ch in self.cardholders.items() if ch.pool == pool]

    def summary(self) -> dict[str, int]:
        return {
            "cardholders": len(self.cardholders),
            "devices": len(self.devices),
            "tokens": len(self.tokens),
            "merchants": len(self.merchants),
            "terminals": len(self.terminals),
            "beneficiaries": len(self.beneficiaries),
            "mandates": len(self.mandates),
            "onboarding_batches": len(self.onboarding_batches),
            "acquirers": len(self.acquirers),
            "issuers": len(self.issuers),
            "psps": len(self.psps),
            "geo_cells": len(self.geo_cells),
        }


def all_entity_ids(world: World) -> Iterable[str]:
    """Every entity id, for the leakage audit's entity-disjointness assertion."""
    yield from world.cardholders
    yield from world.devices
    yield from world.tokens
    yield from world.merchants
    yield from world.terminals
    yield from world.beneficiaries
    yield from world.mandates
