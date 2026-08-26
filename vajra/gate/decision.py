"""The `Decision` contract — what GATE emits, and the reason-code vocabulary.

ONE RULE THAT LOOKS TRIVIAL AND IS NOT: **the score is never rounded on the wire.**

A real fused score of 2.175e-12 rendered as "0.0000" looks exactly like a broken model, and a
previous build spent a debugging session on a model that was working correctly and displaying
wrongly. `as_dict()` emits the float unrounded and the UI formats it in scientific notation below
its display precision. Rounding here would move a presentation choice into the data contract.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal, Mapping, Sequence

import yaml

from core.paths import paths

Persona = Literal["GATE-I", "GATE-B"]

#: Actions, per-rail. `step_up` is deliberately NOT universal: on UPI the PIN already IS the
#: additional factor and added friction is bounded by NPCI UX rules [VERIFY scope], so the UPI
#: response is an interstitial, a cooling delay or a hold — never a second auth factor.
ACTIONS: tuple[str, ...] = (
    "approve",
    "friction",              # generic friction; the rail ladder names the concrete form
    "threeds_challenge",     # card CNP only — the one genuine step-up lever in the stack
    "interstitial",          # UPI scam-intervention interstitial
    "cooling_delay",         # UPI cooling delay
    "review",                # route to the human queue
    "refer",                 # card present: refer to issuer
    "decline",
    "collect_suppress",      # withhold the collect request at the payer PSP
    "hold",                  # beneficiary-side bounded hold
    "freeze_recommend",      # beneficiary-side freeze RECOMMENDATION, with auto-release
    "mandate_refuse",        # mandate-conformance refusal
    "name_mismatch_warn",    # A2A confirmation-of-payee warning
)

#: The three action bands the metrics table decomposes recall into, plus approve.
BANDS: tuple[str, ...] = ("approve", "friction", "review", "auto_decline")


@lru_cache(maxsize=1)
def reason_code_catalogue() -> dict[str, dict[str, str]]:
    with (paths.governance / "reason_codes.yaml").open("r", encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    out: dict[str, dict[str, str]] = {}
    for entry in doc["codes"]:
        cid = entry["id"]
        if cid in out:
            raise ValueError(f"governance/reason_codes.yaml: duplicate code {cid!r}")
        for required in ("text", "source", "family", "actionable"):
            if not str(entry.get(required, "")).strip():
                raise ValueError(
                    f"reason code {cid!r} is missing {required!r}. A code a reviewer cannot act "
                    f"on is noise in a queue, and `actionable` is what stops us shipping one."
                )
        out[cid] = {k: " ".join(str(v).split()) for k, v in entry.items() if k != "id"}
    return out


def reason_code_count() -> int:
    """Machine-counted. The design's ~40 is a budget."""
    return len(reason_code_catalogue())


def validate_reason_codes(codes: Sequence[str]) -> None:
    """Raise on any code outside the vocabulary.

    Called on every Decision construction. A typo must be a hard failure, not an unreadable
    queue entry six months later.
    """
    cat = reason_code_catalogue()
    unknown = [c for c in codes if c not in cat]
    if unknown:
        raise KeyError(
            f"reason codes {unknown} are not in governance/reason_codes.yaml. Free text is not "
            f"acceptable in a review queue: a fixed vocabulary is what makes disposition "
            f"consistent across analysts and auditable after the fact."
        )


@dataclass(slots=True)
class Decision:
    """One scoring decision. The contract in docs/CONTRACTS.md section 4."""

    event_id: str
    persona: str
    score: float
    action: str
    band: str
    latency_ms: float
    reason_codes: tuple[str, ...] = ()
    component_scores: Mapping[str, float] = field(default_factory=dict)
    attribution: Mapping[str, float] = field(default_factory=dict)
    conformal_p: float | None = None
    abstained: bool = False
    guard_rule: str | None = None
    #: Set when the decision was made in a degraded mode, so a report can separate them.
    degraded_mode: str = ""
    #: The model version that produced it. Author-an-Attack scores against a PINNED version and
    #: prints it on screen, so a judge can see it is not the model we just retrained.
    model_version: str = ""
    #: GATE-B only: the freeze-recommendation payload, with a BOUNDED hold and an auto-release
    #: rule. A wrongly frozen receiver is a worse harm than a declined payer, so the payload has
    #: to say when the money moves anyway.
    freeze_payload: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.persona not in ("GATE-I", "GATE-B"):
            raise ValueError(f"persona must be GATE-I or GATE-B, got {self.persona!r}")
        if self.action not in ACTIONS:
            raise ValueError(f"action {self.action!r} is not in the declared set {ACTIONS}")
        if self.band not in BANDS:
            raise ValueError(f"band {self.band!r} is not in {BANDS}")
        validate_reason_codes(self.reason_codes)

    def as_dict(self) -> dict[str, Any]:
        """Serialise. THE SCORE IS NOT ROUNDED — see the module docstring."""
        return {
            "event_id": self.event_id,
            "persona": self.persona,
            "score": float(self.score),
            "action": self.action,
            "band": self.band,
            "latency_ms": float(self.latency_ms),
            "reason_codes": list(self.reason_codes),
            "reason_texts": [reason_code_catalogue()[c]["text"] for c in self.reason_codes],
            "component_scores": {k: float(v) for k, v in self.component_scores.items()},
            "attribution": {k: float(v) for k, v in self.attribution.items()},
            "conformal_p": None if self.conformal_p is None else float(self.conformal_p),
            "abstained": bool(self.abstained),
            "guard_rule": self.guard_rule,
            "degraded_mode": self.degraded_mode,
            "model_version": self.model_version,
            "freeze_payload": dict(self.freeze_payload) if self.freeze_payload else None,
        }

    def explain(self) -> list[dict[str, str]]:
        """The reviewer-facing explanation: code, text, and what to DO about it."""
        cat = reason_code_catalogue()
        return [
            {
                "code": c,
                "text": cat[c]["text"],
                "source": cat[c]["source"],
                "actionable": cat[c]["actionable"],
            }
            for c in self.reason_codes
        ]


def freeze_recommendation(
    beneficiary_id: str,
    *,
    score: float,
    max_hold_hours: int,
    auto_release: bool,
    golden_hour_target_minutes: int,
    reason_codes: Sequence[str],
    inflow_at_risk_inr: float,
) -> dict[str, Any]:
    """The NCRP/CFCFRMS-SHAPED freeze recommendation payload.

    SHAPED, NOT CONFORMANT, and we call it that: the real mechanics are [VERIFY]. Two properties
    are load-bearing and are ours rather than borrowed:

    *   a **bounded maximum hold**, and
    *   an **explicit auto-release rule**.

    A wrongly frozen legitimate receiver is a materially worse harm than a declined payer, so the
    payload must state when the money moves anyway. A freeze with no release condition is not a
    control, it is a confiscation.
    """
    return {
        "beneficiary_id": beneficiary_id,
        "recommendation": "hold_and_escalate",
        "score": float(score),
        "reason_codes": list(reason_codes),
        "inflow_at_risk_inr": float(inflow_at_risk_inr),
        "max_hold_hours": int(max_hold_hours),
        "auto_release_unless_escalated": bool(auto_release),
        "auto_release_note": (
            f"If no human escalation is recorded within {max_hold_hours}h, THE HOLD RELEASES "
            f"AUTOMATICALLY and the funds move. This is a bounded hold, not a freeze."
        ),
        "golden_hour_target_minutes": int(golden_hour_target_minutes),
        "payload_conformance": (
            "SHAPED, NOT CONFORMANT. NCRP/CFCFRMS alert-payload mechanics and the golden-hour "
            "freeze process are [VERIFY]; this is a payload of the right shape, described as "
            "shaped rather than as conformant."
        ),
    }


def hash_chain_entry(previous_hash: str, decision: Decision) -> tuple[str, dict[str, Any]]:
    """One append-only, hash-chained decision-log entry.

    The chain is the regulator-facing artifact: a decision cannot be altered after the fact
    without breaking every subsequent link. Governance ships as artefacts, not assurances.
    """
    body = decision.as_dict()
    payload = json.dumps({"prev": previous_hash, "decision": body}, sort_keys=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest, {"prev": previous_hash, "hash": digest, "decision": body}
