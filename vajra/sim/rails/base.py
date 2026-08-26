"""Shared emitter context, lifecycle scheduling, and id minting.

THE DESIGN RULE THIS FILE ENFORCES: **structural legality is produced, not patched.** Every F1
invariant that can be satisfied by construction is satisfied here rather than checked later. A
previous build discovered 250,947 F1 violations across ~12 generator bugs precisely because rails
minted their own references and their own merchant ids; the fixes all amounted to routing through
one place. This is that place.

Concretely, four things live here and nowhere else:

*   **Reference minting.** `mint_rrn`, `mint_trace`, `mint_event_id`. A follow-up message
    (presentment, refund, chargeback, representment, reversal) inherits its antecedent's `rrn`
    AND sets `original_auth_event_id`. The pairing indexer matches on ANY shared reference, so
    both are set on every derived message.
*   **The merchant pool.** `sample_merchant` draws from `world.merchant_sampling_order` with the
    Zipf weights. NO EMITTER MAY MINT A MERCHANT ID. That is what broke the cross-rail
    concentration curve before.
*   **ATC state.** `next_atc` is monotone per PAN, so the ATC-monotonicity invariant cannot be
    violated by ordinary emission — only by a deliberate ATK-P2 replay, which asks for it
    explicitly via `replay_atc`.
*   **Follow-up scheduling.** Emitters return `Followup` records; the engine runs them at their
    due day. An emitter never reaches forward in time itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import numpy as np

from core.config import Config
from sim.calendar import Calendar
from sim.graph.entities import World
from sim.habits import Habit
from sim.schema import HOUR_MAX, CanonicalEvent

#: Amount bands the bandit's `amount_band` arm maps onto. Shared so the arm and the emitter
#: cannot disagree about what "mid" means.
AMOUNT_BANDS: dict[str, tuple[float, float]] = {
    "micro": (5.0, 200.0),
    "low": (200.0, 2_000.0),
    "mid": (2_000.0, 20_000.0),
    "high": (20_000.0, 100_000.0),
    "very_high": (100_000.0, 500_000.0),
}


@dataclass
class Followup:
    """A message scheduled for a later day.

    `builder` is called with the SimContext at the due day and returns events. Holding a
    callable rather than a pre-built event matters: the follow-up must observe state as it is at
    T+N (was the auth reversed? has the mandate been revoked?), not as it was at T+0.
    """

    due_day: int
    kind: str
    builder: Callable[["SimContext"], list[CanonicalEvent]]
    #: Carried for the engine's report, so a dropped follow-up is visible rather than silent.
    origin_event_id: str = ""


@dataclass
class EmitResult:
    events: list[CanonicalEvent] = field(default_factory=list)
    followups: list[Followup] = field(default_factory=list)

    def extend(self, other: "EmitResult") -> "EmitResult":
        self.events.extend(other.events)
        self.followups.extend(other.followups)
        return self


@dataclass
class AuthRecord:
    """The minimum an antecedent authorisation must remember for its lifecycle to be legal."""

    event_id: str
    rrn: str
    trace_number: str
    day_index: int
    #: IST hour of the authorisation. Needed so a SAME-DAY follow-up can be scheduled strictly
    #: after it: the stream is sorted by timestamp at the end, and a presentment drawn at an
    #: early hour would otherwise precede an authorisation drawn at a late one.
    hour_ist: float
    ts: float
    rail: str
    amount_inr: float
    approved: bool
    cardholder_id: str
    merchant_id: str
    mcc: str
    pan_canonical: str
    token_id: str
    #: Carried through the clearing chain: a presentment on a tokenised authorisation genuinely
    #: does bear the token requestor, and "a token id implies a requestor id" is an invariant.
    token_requestor_id: str
    threeds_result: str
    threeds_eci: str
    cohort_tag: str
    attack_campaign_id: str
    attack_family_id: str
    attack_grammar_str: str
    attack_cell_id: str
    oracle_is_attack: bool
    #: Cumulative refunded amount, so "refund <= original (cumulative across partials)" holds.
    refunded_inr: float = 0.0
    reversed_: bool = False
    presented: bool = False
    disputed: bool = False


class SimContext:
    """Mutable simulation state shared by every emitter. One instance per run."""

    def __init__(
        self,
        world: World,
        habits: dict[str, Habit],
        calendar: Calendar,
        cfg: Config,
        rng: np.random.Generator,
    ) -> None:
        self.world = world
        self.habits = habits
        self.calendar = calendar
        self.cfg = cfg
        self.rng = rng

        self.day = 0
        self._seq = 0
        self._rrn_seq = 0
        self._trace_seq = 0

        #: PAN -> last issued application transaction counter. Monotone by construction.
        self._atc: dict[str, int] = {}
        #: event_id -> AuthRecord, for every authorisation that could be referenced later.
        self.auth_index: dict[str, AuthRecord] = {}
        #: rrn -> event_id, the second pairing key.
        self.rrn_index: dict[str, str] = {}
        #: cardholder -> ordered list of auth event ids, for retry-chain and sequence features.
        self.auth_history: dict[str, list[str]] = {}
        #: Per-cardholder AVS probe state, so an AVS trajectory is a real trajectory.
        self.avs_state: dict[str, str] = {}
        #: Provisioning events, so provisioning_to_first_spend_minutes resolves.
        self.provisioning_ts: dict[str, float] = {}
        #: Beneficiary running state is on the Beneficiary object itself; this tracks holds.
        self.freeze_log: list[dict[str, Any]] = []
        #: Counters the sim report prints, so a silently-skipped branch is visible.
        self.counters: dict[str, int] = {}

        self._merchant_ids = list(world.merchant_sampling_order)
        self._merchant_w = np.asarray(world.merchant_sampling_weights, dtype=np.float64)
        if self._merchant_w.size and abs(self._merchant_w.sum() - 1.0) > 1e-6:
            self._merchant_w = self._merchant_w / self._merchant_w.sum()

    # ---- counters ---------------------------------------------------------------------
    def bump(self, key: str, n: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + n

    # ---- id minting -------------------------------------------------------------------
    def mint_event_id(self, prefix: str = "EV") -> str:
        self._seq += 1
        return f"{prefix}{self._seq:010d}"

    def mint_rrn(self) -> str:
        self._rrn_seq += 1
        return f"R{self._rrn_seq:011d}"

    def mint_trace(self) -> str:
        self._trace_seq += 1
        return f"{self._trace_seq % 1_000_000:06d}"

    # ---- shared sampling --------------------------------------------------------------
    def sample_merchant(self, rng: np.random.Generator | None = None) -> str:
        """Draw a merchant from THE shared Zipf pool.

        No emitter may mint a merchant id. Ad-hoc minting inside the UPI and clearing emitters
        is what pushed a previous build's pooled top-10 merchant share to 0.9% against a
        22-42% expectation and made the F5 concentration curve meaningless.
        """
        r = rng if rng is not None else self.rng
        if not self._merchant_ids:
            raise RuntimeError("world has no merchants; build_world must run before emission")
        idx = int(r.choice(len(self._merchant_ids), p=self._merchant_w))
        return self._merchant_ids[idx]

    def sample_amount_in_band(self, band: str, rng: np.random.Generator | None = None) -> float:
        r = rng if rng is not None else self.rng
        lo, hi = AMOUNT_BANDS.get(band, AMOUNT_BANDS["mid"])
        return float(np.round(r.uniform(lo, hi), 2))

    # ---- ATC ---------------------------------------------------------------------------
    def next_atc(self, pan: str) -> int:
        """Monotone per PAN. Ordinary emission cannot violate ATC monotonicity."""
        cur = self._atc.get(pan, int(self.rng.integers(20, 900)))
        nxt = cur + 1
        self._atc[pan] = nxt
        return nxt

    def replay_atc(self, pan: str) -> int:
        """Deliberately re-issue the LAST ATC — the ATK-P2 replay signature.

        Separate method, named for what it is. The invariant that ordinary emission is monotone
        stays true, and the violation is attributable to an attack rather than to a bug. F1's
        ATC invariant is therefore scoped to non-attack events, and that scoping is explicit in
        fidelity/f1_invariants.py rather than implicit here.
        """
        return self._atc.get(pan, 1)

    # ---- lifecycle registration --------------------------------------------------------
    def register_auth(self, ev: CanonicalEvent) -> AuthRecord:
        """Record an authorisation so its lifecycle can legally reference it."""
        rec = AuthRecord(
            event_id=ev.event_id,
            rrn=ev.rrn,
            trace_number=ev.trace_number,
            day_index=ev.day_index,
            hour_ist=ev.hour_ist,
            ts=ev.ts,
            rail=ev.rail,
            amount_inr=ev.amount_inr,
            approved=ev.approved,
            cardholder_id=ev.cardholder_id,
            merchant_id=ev.merchant_id,
            mcc=ev.mcc,
            pan_canonical=ev.pan_canonical,
            token_id=ev.token_id,
            token_requestor_id=ev.token_requestor_id,
            threeds_result=ev.threeds_authentication_result,
            threeds_eci=ev.threeds_eci,
            cohort_tag=ev.cohort_tag,
            attack_campaign_id=ev.attack_campaign_id,
            attack_family_id=ev.attack_family_id,
            attack_grammar_str=ev.attack_grammar_str,
            attack_cell_id=ev.attack_cell_id,
            oracle_is_attack=ev.oracle_is_attack,
        )
        self.auth_index[ev.event_id] = rec
        if ev.rrn:
            self.rrn_index[ev.rrn] = ev.event_id
        self.auth_history.setdefault(ev.cardholder_id, []).append(ev.event_id)
        return rec

    def link_to_auth(self, ev: CanonicalEvent, auth: AuthRecord) -> None:
        """Attach BOTH pairing keys to a derived message.

        The pairing indexer matches on any shared reference, so setting only one of these was a
        real bug class: a presentment with an `original_auth_event_id` but a fresh `rrn` paired
        under one indexer and not the other, and the F1 count depended on which ran.
        """
        ev.original_auth_event_id = auth.event_id
        ev.rrn = auth.rrn
        ev.trace_number = auth.trace_number
        # ATTACK PROVENANCE TRAVELS WITH THE CHAIN. Without this, the presentment, refund and
        # chargeback of a FRAUDULENT authorisation were stamped benign: `oracle_is_attack=False`,
        # empty `attack_family_id`. That is label corruption at the source -- the derived legs of an
        # attack are part of that campaign's footprint, and attributing them to nobody makes
        # per-family recall denominators and value-at-risk wrong. The AuthRecord already carries
        # every provenance field precisely so the chain can inherit it.
        if auth.oracle_is_attack:
            ev.oracle_is_attack = True
            ev.attack_campaign_id = auth.attack_campaign_id
            ev.attack_family_id = auth.attack_family_id
            ev.attack_grammar_str = auth.attack_grammar_str
            ev.attack_cell_id = auth.attack_cell_id

    # ---- convenience ------------------------------------------------------------------
    def new_event(
        self,
        *,
        rail: str,
        message_kind: str,
        tier: str,
        day_index: int,
        hour_ist: float,
        amount_inr: float,
        prefix: str = "EV",
    ) -> CanonicalEvent:
        # THE HOUR CONVENTION IS ENFORCED HERE, at the one chokepoint every event passes through,
        # rather than trusted in each emitter's arithmetic. An emitter that derives an hour by adding
        # a gap and taking a modulo (see CardTokenProvisioningEmitter) can land in (23.99, 24.0); any
        # downstream ordering guard shaped `min(HOUR_MAX, antecedent_hour + delta)` then returns a
        # time EARLIER than its antecedent, and the derived message sorts before the message it
        # derives from. Clamping centrally means no antecedent hour can ever exceed the ceiling those
        # guards clamp to, so the whole class of inversion is impossible by construction.
        # `ts` is derived from the CLAMPED hour so the two can never disagree.
        hour_clamped = min(max(float(hour_ist), 0.0), HOUR_MAX)
        return CanonicalEvent(
            event_id=self.mint_event_id(prefix),
            ts=self.calendar.ts(day_index, hour_clamped),
            day_index=int(day_index),
            hour_ist=hour_clamped,
            dow=self.calendar.dow(day_index),
            rail=rail,
            message_kind=message_kind,
            tier=tier,
            amount_inr=float(amount_inr),
        )


class RailEmitter(Protocol):
    """The emitter interface. One per rail; grouped into modules by rail family."""

    rail: str
    tier: str

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
        ...


def apply_attack_provenance(ev: CanonicalEvent, attack: dict[str, Any] | None) -> None:
    """Stamp simulator ORACLE ground truth onto an event.

    These fields are used ONLY by the evaluation harness and the reject-inference validation arm.
    `tests/test_no_oracle_in_features.py` asserts no registry feature reads any of them.
    """
    if not attack:
        return
    ev.attack_campaign_id = str(attack.get("campaign_id", ""))
    ev.attack_family_id = str(attack.get("family_id", ""))
    ev.attack_grammar_str = str(attack.get("grammar_str", ""))
    ev.attack_cell_id = str(attack.get("cell_id", ""))
    ev.attack_stage = str(attack.get("stage", ""))
    ev.oracle_is_attack = True
    ev.sealed_holdout = bool(attack.get("sealed", False))
    ev.rng_stream = str(attack.get("rng_stream", ""))
    ev.oracle_value_at_risk_inr = float(ev.amount_inr)


def hug_threshold(amount: float, threshold: float, rng: np.random.Generator) -> float:
    """Place an amount just below a threshold — the threshold-hugging observable.

    Deliberately NOT exactly threshold-1: an exact value would be a trivially detectable
    fingerprint of our own generator, and the artifact-permutation ablation would show recall
    collapsing when it is scrambled. A small random standoff is what a real attacker does.
    """
    standoff = float(abs(rng.normal(0.0, 0.012 * threshold))) + 1.0
    return float(np.round(max(1.0, threshold - standoff), 2))
