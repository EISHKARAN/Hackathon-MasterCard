"""G0 — invariant guards. A compiled decision table, ZERO ML, fully explainable.

WHAT G0 IS FOR, and it is two things:

1.  **The permanent kill-switch fallback.** If every model is rolled back or disabled, the system
    must still refuse the impossible. G0 has no model dependency, so "kill switch to G0-only" is a
    real fallback rather than an outage.
2.  **Structural refusal, not risk scoring.** G0 fires on structural IMPOSSIBILITIES and hard
    policy violations — a keyed authorisation carrying an EMV cryptogram, a merchant-initiated
    transaction with no original-transaction reference, a mandate-scope violation against the
    stored mandate object, a counter regression, a refund with no retrieval reference. It never
    fires on "this looks risky".

WHY A DECISION AN AUDITOR CAN READ IN ONE LINE IS WORTH MORE THAN A PROBABILITY: because a
structural refusal is defensible without reference to a model, a threshold, or a training set. It
is also the only part of the stack that catches a NOVEL attack which violates message coherence,
regardless of whether we ever imagined it.

Every guard maps to exactly one reason code in governance/reason_codes.yaml, so a G0 refusal is
always explainable in the fixed vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

import numpy as np

#: Guard id -> (reason code, predicate over the event columns, human description).
#: The predicate receives a mapping of column name -> value for ONE event.
GuardFn = Callable[[Mapping[str, object]], bool]


@dataclass(frozen=True)
class Guard:
    id: str
    reason_code: str
    description: str
    predicate: GuardFn
    #: Structural refusals are hard. `advisory=True` guards raise a reason code without forcing a
    #: decline, which is how the collect-fanout guard behaves: it suppresses rather than declines.
    advisory: bool = False
    action_override: str | None = None


def _b(v: object) -> bool:
    return bool(v)


def _f(v: object, default: float = -1.0) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _s(v: object) -> str:
    return "" if v is None else str(v)


_CNP_RAILS = frozenset({"card-cnp-keyed", "card-cnp-3ds", "card-token-provisioning"})
_NON_3DS_RAILS = frozenset(
    {"card-cnp-keyed", "card-cp-emv", "upi-pay", "upi-collect", "upi-autopay-mandate",
     "a2a-credit-transfer", "upi-lite-offline", "aeps-microatm", "agentic-commerce"}
)


GUARDS: tuple[Guard, ...] = (
    Guard(
        "G0-01", "G0_CRYPTOGRAM_ON_KEYED",
        "EMV cryptogram present on a card-not-present rail",
        lambda e: _s(e["rail"]) in _CNP_RAILS and _b(e["emv_cryptogram_present"]),
    ),
    Guard(
        "G0-02", "G0_THREEDS_ON_NON_CNP",
        "3DS authentication result present on a rail that cannot carry one",
        lambda e: _s(e["rail"]) in _NON_3DS_RAILS
        and _s(e["threeds_authentication_result"]) not in ("", "not_applicable"),
    ),
    Guard(
        "G0-03", "G0_MIT_WITHOUT_ORIGINAL",
        "Merchant-initiated transaction with no original-transaction reference",
        lambda e: _s(e["cit_mit_indicator"]) == "MIT"
        and not _s(e["original_auth_event_id"])
        and not _s(e["mandate_id"]),
    ),
    Guard(
        "G0-04", "G0_MANDATE_SCOPE_VIOLATION",
        "Debit exceeds the stored mandate envelope",
        lambda e: _f(e["mandate_max_amount_inr"]) > 0
        and _f(e["amount_inr"]) > _f(e["mandate_max_amount_inr"]) + 1e-6,
    ),
    Guard(
        "G0-05", "G0_CRYPTOGRAM_UNVERIFIED",
        "Cryptogram present but failed verification",
        lambda e: _b(e["emv_cryptogram_present"]) and not _b(e["emv_cryptogram_verified"]),
    ),
    Guard(
        "G0-06", "G0_REFUND_NO_ORIGINAL",
        "Refund or credit with no matching retrieval reference",
        lambda e: _s(e["message_kind"]) == "refund_credit"
        and not _s(e["original_auth_event_id"])
        and not _s(e["rrn"]),
    ),
    Guard(
        "G0-07", "G0_REFUND_EXCEEDS_ORIGINAL",
        "Refund amount exceeds the message amount it resolves to",
        lambda e: _s(e["message_kind"]) == "refund_credit"
        and _f(e["refund_amount_inr"]) > 0
        and _f(e["refund_amount_inr"]) > _f(e["amount_inr"]) + 1e-6,
    ),
    Guard(
        "G0-08", "G0_AGENT_OVER_MANDATE",
        "Agent-initiated amount exceeds the quoted amount",
        lambda e: _s(e["message_kind"]) == "agent_authorisation"
        and _f(e["agent_quoted_amount_inr"]) > 0
        and _f(e["amount_inr"]) > _f(e["agent_quoted_amount_inr"]) * 1.001,
        action_override="mandate_refuse",
    ),
    Guard(
        "G0-09", "G0_COLLECT_FANOUT",
        "Collect request fanned from one payee to many unrelated payers",
        # Advisory + suppress rather than decline: on this rail the correct response is to withhold
        # the request at the payer PSP, not to decline a payment the payer has not made yet.
        lambda e: _s(e["message_kind"]) == "collect_request"
        and _f(e.get("_collect_fanout_1h", -1.0)) >= 25.0,
        advisory=True,
        action_override="collect_suppress",
    ),
    Guard(
        "G0-10", "G0_ATC_REGRESSION",
        "Application transaction counter regressed or duplicated for this card",
        # Needs cross-event state, supplied by the caller as `_atc_regressed`.
        lambda e: _b(e.get("_atc_regressed", False)),
    ),
)


@dataclass
class G0Result:
    fired: tuple[str, ...]
    reason_codes: tuple[str, ...]
    refuse: bool
    action_override: str | None

    @property
    def guard_rule(self) -> str | None:
        return self.fired[0] if self.fired else None


class G0Guards:
    """The compiled decision table. Stateful only for the ATC and collect-fanout counters."""

    def __init__(self, collect_fanout_threshold: float = 25.0) -> None:
        self.collect_fanout_threshold = float(collect_fanout_threshold)
        self._last_atc: dict[str, int] = {}
        self._collect_payees: dict[tuple[str, int], set[str]] = {}

    def guard_count(self) -> int:
        return len(GUARDS)

    def prepare(self, row: dict[str, object]) -> dict[str, object]:
        """Complete the row against canonical schema defaults, then attach two cross-event signals.

        Completing against the SCHEMA (not a feature pipeline) is what makes G0 a real kill switch: it
        must be TOTAL — never crash on a partial row — because the whole point of "kill switch to
        G0-only" is that it keeps working when everything else is disabled. Completing from
        `CanonicalEvent` defaults introduces no feature-pipeline dependency, so the design constraint
        holds while the guard stops being brittle.

        Kept separate from `evaluate` so the inline scorer can share one prepared row between G0 and
        the feature builder rather than recomputing state.
        """
        from sim.schema import CanonicalEvent

        complete = CanonicalEvent(
            event_id=str(row.get("event_id", "")), ts=float(row.get("ts", 0.0) or 0.0),
            day_index=int(row.get("day_index", 0) or 0), hour_ist=float(row.get("hour_ist", 12.0) or 12.0),
            dow=int(row.get("dow", 0) or 0), rail=str(row.get("rail", "upi-pay") or "upi-pay"),
            message_kind=str(row.get("message_kind", "authorisation") or "authorisation"),
            tier=str(row.get("tier", "A") or "A"), amount_inr=float(row.get("amount_inr", 0.0) or 0.0),
        ).as_row()
        # The caller's values win where present; schema defaults fill the rest.
        for k, v in row.items():
            if k in complete:
                complete[k] = v
        row = complete
        # ATC regression / duplication, per card.
        row["_atc_regressed"] = False
        if _b(row.get("emv_cryptogram_present")):
            atc = int(_f(row.get("emv_cryptogram_atc"), -1))
            pan = _s(row.get("pan_canonical"))
            if atc >= 0 and pan:
                prev = self._last_atc.get(pan)
                if prev is not None and atc <= prev:
                    row["_atc_regressed"] = True
                else:
                    self._last_atc[pan] = atc

        # Collect fan-out: distinct payers this payee has requested from, this hour.
        row["_collect_fanout_1h"] = -1.0
        if _s(row.get("message_kind")) == "collect_request":
            payee = _s(row.get("payee_vpa"))
            hour_bucket = int(_f(row.get("ts"), 0.0) // 3600.0)
            if payee:
                key = (payee, hour_bucket)
                s = self._collect_payees.setdefault(key, set())
                s.add(_s(row.get("cardholder_id")))
                row["_collect_fanout_1h"] = float(len(s))
        return row

    def evaluate(self, row: Mapping[str, object]) -> G0Result:
        fired: list[str] = []
        codes: list[str] = []
        refuse = False
        override: str | None = None
        for g in GUARDS:
            try:
                hit = bool(g.predicate(row))
            except KeyError as exc:
                raise KeyError(
                    f"guard {g.id} reads column {exc} which is absent from the prepared row. G0 "
                    f"must be evaluable from the canonical schema alone — it is the kill-switch "
                    f"fallback and cannot depend on a feature pipeline."
                ) from exc
            if not hit:
                continue
            fired.append(g.id)
            codes.append(g.reason_code)
            if g.action_override and override is None:
                override = g.action_override
            if not g.advisory:
                refuse = True
        return G0Result(tuple(fired), tuple(codes), refuse, override)

    def catalogue(self) -> list[dict[str, object]]:
        """For the UI and reports: the whole table, readable in one screen."""
        return [
            {
                "id": g.id,
                "reason_code": g.reason_code,
                "description": g.description,
                "advisory": g.advisory,
                "action_override": g.action_override,
                "kind": "structural impossibility or hard policy violation, never a risk score",
            }
            for g in GUARDS
        ]


def evaluate_batch(rows: Sequence[Mapping[str, object]]) -> tuple[np.ndarray, list[G0Result]]:
    """Evaluate G0 over a batch. Returns (refuse_mask, results)."""
    g0 = G0Guards()
    results: list[G0Result] = []
    for r in rows:
        results.append(g0.evaluate(g0.prepare(dict(r))))
    return np.asarray([r.refuse for r in results], dtype=bool), results
