"""What the attacker is allowed to observe. THE HARD CONSTRAINT OF THE WHOLE RED SIDE.

`AttackerObservation` has EXACTLY the fields a real adversary observes and NOTHING ELSE. It has no
score, no conformal p-value, no feature vector and no attribution.

WHY THIS IS A MODULE AND NOT A CONVENTION: without it, "the attacker observes only what an attacker
observes" is a sentence in a document rather than a property of the system, and every time-to-evade
number would be measuring an attacker with oracle access into the defender. So the field set is
frozen, `tests/test_attacker_observability.py` asserts it EXACTLY, and adding a field that carries
defender-internal information fails the build.

THE BENEFICIARY-SIDE HALF IS LOAD-BEARING, not decoration. A payer-side-only observation vector would
close the loop around half the system, and the mule-layering families are precisely the ones that
would adapt against a beneficiary gate. An adversarially unstressed GATE-B number is the first thing
an adversarial-ML judge would find. If this half is cut for time, every GATE-B number is labelled
NON-ADVERSARIAL wherever it appears.
"""

from __future__ import annotations

from dataclasses import dataclass, fields as dataclass_fields
from typing import Any

#: The EXACT permitted field set. The test compares against this, so the list is the contract.
PERMITTED_FIELDS: frozenset[str] = frozenset(
    {
        # payer side — what a merchant/attacker sees back from an authorisation
        "approved",
        "declined",
        "stepped_up",
        "reason_code",
        "response_latency_ms",
        # beneficiary side — what a real mule operator sees
        "credit_landed",
        "credit_held",
        "onward_send_blocked",
        "account_frozen",
        "seconds_to_freeze",
        # the attacker's own accounting, which it obviously knows
        "amount_inr",
        "value_retained_inr",
        "spend_inr",
    }
)

#: Field names that would leak defender internals. Checked by the test, and listed here so the
#: prohibition is explicit rather than implied by absence.
FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "score",
    "conformal",
    "p_value",
    "attribution",
    "shap",
    "feature",
    "band",
    "threshold",
    "abstain",
    "label",
    "oracle",
    "is_fraud",
)


@dataclass(frozen=True, slots=True)
class AttackerObservation:
    """One step of attacker-visible feedback.

    Every field here is something an adversary genuinely learns by running the transaction. Nothing
    here is something only the defender knows.
    """

    # ---- payer side ------------------------------------------------------------------
    approved: bool = False
    declined: bool = False
    stepped_up: bool = False
    #: The reason code the network/issuer returned. An attacker DOES see this, and reading it is the
    #: whole ATK-C1 mechanism — which is why degrading reason-code specificity is a real defence.
    reason_code: str = ""
    response_latency_ms: float = -1.0

    # ---- beneficiary side ------------------------------------------------------------
    credit_landed: bool = False
    credit_held: bool = False
    onward_send_blocked: bool = False
    account_frozen: bool = False
    seconds_to_freeze: float = -1.0

    # ---- the attacker's own books ----------------------------------------------------
    amount_inr: float = 0.0
    value_retained_inr: float = 0.0
    spend_inr: float = 0.0

    # ---- derived, from the fields above only -----------------------------------------
    @property
    def adverse(self) -> bool:
        """Did anything bad happen from the attacker's point of view?

        Deliberately NOT "was I detected": at a 0.1% base rate any multi-transaction campaign draws
        some declines, so a decline-based notion of detection fires either always or never.
        """
        return bool(
            self.declined or self.stepped_up or self.credit_held
            or self.onward_send_blocked or self.account_frozen
        )

    @property
    def ruin_event(self) -> str:
        """The NAMED observable ruin trigger, or "".

        Only two events count, and both are things the attacker can actually see: a beneficiary-side
        freeze, or funds blocked from moving onward. An analyst-confirmed fraud disposition is the
        third trigger in `config/cost_matrix.yaml`, and it reaches the agent through the environment
        rather than through this observation, because an attacker does not see a disposition directly.
        """
        if self.account_frozen:
            return "beneficiary_freeze"
        if self.onward_send_blocked:
            return "onward_send_blocked"
        return ""

    def as_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in dataclass_fields(self)}


def observation_field_names() -> frozenset[str]:
    return frozenset(f.name for f in dataclass_fields(AttackerObservation))


def assert_observability_contract() -> None:
    """Raise if the observation carries anything defender-internal. Called at import by the test."""
    names = observation_field_names()
    extra = names - PERMITTED_FIELDS
    missing = PERMITTED_FIELDS - names
    if extra or missing:
        raise AssertionError(
            f"AttackerObservation's field set has drifted from the contract in "
            f"attack/rl/observation.py. Unexpected: {sorted(extra)}. Missing: {sorted(missing)}. "
            f"This is the constraint that makes every time-to-evade number meaningful; a field "
            f"carrying defender-internal information would silently turn the attacker into an "
            f"oracle-access adversary."
        )
    for n in names:
        for bad in FORBIDDEN_SUBSTRINGS:
            if bad in n.lower():
                raise AssertionError(
                    f"AttackerObservation field {n!r} contains the forbidden substring {bad!r}. "
                    f"The attacker may not observe defender internals."
                )
