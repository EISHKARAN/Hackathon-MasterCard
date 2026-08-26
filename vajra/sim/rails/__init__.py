"""Rail emitters, and the registry that maps a rail id to its emitter.

Tier A rails are emitted at MESSAGE level with hand-written invariants that fail the build.
Tier B rails are thin emitters that carry attack compositions and observable signatures but make
NO claim of message-level fidelity, and the UI says so on the card.

`card-clearing-dispute` deliberately has NO entry in the registry: it is produced only as a
follow-up of an authorisation. Sampling it independently would create presentments with no
antecedent authorisation, which is an F1 violation by construction rather than by accident.
"""

from __future__ import annotations

from typing import Mapping

from sim.rails.a2a import A2A_EMITTERS, emit_pacs_status
from sim.rails.base import (
    AMOUNT_BANDS,
    AuthRecord,
    EmitResult,
    Followup,
    RailEmitter,
    SimContext,
    apply_attack_provenance,
    hug_threshold,
)
from sim.rails.card import (
    CARD_EMITTERS,
    POLICY_THRESHOLDS,
    nearest_threshold,
    schedule_card_lifecycle,
    schedule_refund,
)
from sim.rails.thin import THIN_EMITTERS
from sim.rails.upi import (
    AFA_EXEMPT_BAND_INR,
    UPI_EMITTERS,
    UPI_THRESHOLDS,
    emit_inbound_credit,
    nearest_upi_threshold,
    pick_beneficiary,
)

#: Rails that are SAMPLED directly. Derived rails are absent on purpose.
EMITTERS: Mapping[str, RailEmitter] = {
    e.rail: e for e in (*CARD_EMITTERS, *UPI_EMITTERS, *A2A_EMITTERS, *THIN_EMITTERS)
}

#: Rails that exist only as lifecycle products of another rail.
DERIVED_RAILS: frozenset[str] = frozenset({"card-clearing-dispute"})


def emitter_for(rail: str) -> RailEmitter:
    try:
        return EMITTERS[rail]
    except KeyError as exc:
        if rail in DERIVED_RAILS:
            raise KeyError(
                f"{rail!r} is a DERIVED rail: it is produced only as a follow-up of an "
                f"authorisation, never sampled. Sampling it would create presentments with no "
                f"antecedent authorisation, which is an F1 violation by construction."
            ) from exc
        raise KeyError(f"no emitter registered for rail {rail!r}; registered: {sorted(EMITTERS)}") from exc


def sampled_rails() -> tuple[str, ...]:
    return tuple(sorted(EMITTERS))


__all__ = [
    "AMOUNT_BANDS",
    "AFA_EXEMPT_BAND_INR",
    "AuthRecord",
    "DERIVED_RAILS",
    "EMITTERS",
    "EmitResult",
    "Followup",
    "POLICY_THRESHOLDS",
    "RailEmitter",
    "SimContext",
    "UPI_THRESHOLDS",
    "apply_attack_provenance",
    "emit_inbound_credit",
    "emit_pacs_status",
    "emitter_for",
    "hug_threshold",
    "nearest_threshold",
    "nearest_upi_threshold",
    "pick_beneficiary",
    "sampled_rails",
    "schedule_card_lifecycle",
    "schedule_refund",
]
