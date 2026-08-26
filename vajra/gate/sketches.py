"""The in-process online store: sketch counters over the nine entity keys.

THIS IS THE COLD-GRAPH FIX. The heavy graph model cannot score the first seconds of a burst, and the
first seconds are exactly where enumeration, provisioning abuse and fan-out live. So cheap streaming
counters run INLINE and graph signal exists at t=0; the GNN supplies richer embeddings near-line.

WE DO NOT CLAIM LIVE GRAPH TRAVERSAL IN THE AUTHORISATION PATH. That is the mistake that makes
latency claims fictional.

THE ONE THING THAT MAKES THE LATENCY TARGET REACHABLE: a SINGLE BATCHED MULTI-KEY FETCH. All nine
entity keys are read in ONE round trip, not nine sequential ones. Lose the batch and the throughput
arithmetic collapses — `bench/` measures both so the claim is a measurement rather than an assertion.

FOOTPRINT, stated the honest way: values-per-entity-per-key-type x active entities. NEVER as a round
total, because a round total hides which key type dominates.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

#: THE NINE ENTITY KEYS. That count is canonical; any other figure in the repo is a typo.
ENTITY_KEYS: tuple[str, ...] = (
    "pan_canonical",
    "token_id",
    "token_requestor_id",
    "device_fingerprint_id",
    "terminal_id",
    "merchant_id",
    "bin_prefix",
    "vpa",
    "beneficiary_id",
)

#: Trailing windows, in seconds.
WINDOWS: dict[str, float] = {"1h": 3600.0, "24h": 86_400.0, "7d": 604_800.0, "30d": 2_592_000.0}


class HyperLogLogLite:
    """A small HyperLogLog for approximate distinct counts.

    Approximate ON PURPOSE: an exact set per entity per window is unbounded memory, and the
    counter's job inline is to answer "is this fan-out unusual" rather than to be exact. The
    relative error is ~1.04/sqrt(m); with m=64 registers that is ~13%, which is well inside the
    resolution the fan-out features actually need and costs 64 bytes per entity.
    """

    __slots__ = ("m", "registers", "_alpha")

    def __init__(self, m: int = 64) -> None:
        if m & (m - 1) != 0:
            raise ValueError(f"m must be a power of two, got {m}")
        self.m = m
        self.registers = bytearray(m)
        self._alpha = 0.7213 / (1.0 + 1.079 / m) if m >= 128 else 0.709

    def add(self, value: str) -> None:
        h = int.from_bytes(hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest(), "big")
        idx = h & (self.m - 1)
        w = h >> int(math.log2(self.m))
        rho = (w.bit_length() and (64 - int(math.log2(self.m)) - w.bit_length() + 1)) or 1
        if rho > self.registers[idx]:
            self.registers[idx] = min(rho, 255)

    def estimate(self) -> float:
        z = sum(2.0 ** -r for r in self.registers)
        if z == 0:
            return 0.0
        est = self._alpha * self.m * self.m / z
        zeros = self.registers.count(0)
        if est <= 2.5 * self.m and zeros:
            return float(self.m * math.log(self.m / zeros))
        return float(est)

    def n_bytes(self) -> int:
        return self.m


@dataclass
class EntityState:
    """Per-entity rolling state. Bounded by construction: fixed-size ring buffers only."""

    #: (ts, amount) ring buffer, capped. The cap is the memory guarantee.
    events: list[tuple[float, float]] = field(default_factory=list)
    hll: HyperLogLogLite = field(default_factory=HyperLogLogLite)
    first_seen_ts: float = -1.0
    last_seen_ts: float = -1.0
    n_total: int = 0
    #: Beneficiary-side running totals, used only for the beneficiary key.
    inflow: float = 0.0
    outflow: float = 0.0

    MAX_EVENTS = 512

    def observe(self, ts: float, amount: float, counterparty: str = "") -> None:
        self.events.append((float(ts), float(amount)))
        if len(self.events) > self.MAX_EVENTS:
            # Drop the oldest half at once rather than one per event: an O(1)-amortised trim keeps
            # the inline path's cost bounded, which is what the p99 claim depends on.
            self.events = self.events[len(self.events) // 2 :]
        if counterparty:
            self.hll.add(counterparty)
        if self.first_seen_ts < 0:
            self.first_seen_ts = float(ts)
        self.last_seen_ts = float(ts)
        self.n_total += 1

    def window_count(self, ts: float, window_s: float) -> int:
        cutoff = ts - window_s
        return sum(1 for t, _ in self.events if cutoff <= t < ts)

    def window_sum(self, ts: float, window_s: float) -> float:
        cutoff = ts - window_s
        return float(sum(a for t, a in self.events if cutoff <= t < ts))

    def age_days(self, ts: float) -> float:
        return -1.0 if self.first_seen_ts < 0 else (ts - self.first_seen_ts) / 86_400.0


@dataclass
class OnlineStore:
    """The only new stateful dependency on the inline path, and it ships with a degradation policy.

    `fetch_multi` is the SINGLE BATCHED MULTI-KEY FETCH: one call for all nine keys. The degraded
    path (`reduced_vector`) is what the scorer falls back to when the store times out, and `bench/`
    re-measures p99 under injected store latency so the fallback has a number rather than a promise.
    """

    #: (key_type, key_value) -> state
    state: dict[tuple[str, str], EntityState] = field(default_factory=dict)
    #: Counters for the footprint report.
    n_fetches: int = 0
    n_keys_fetched: int = 0

    def observe(self, row: Mapping[str, Any]) -> None:
        ts = float(row.get("ts", 0.0))
        amount = float(row.get("amount_inr", 0.0))
        counterparty_for = {
            "pan_canonical": row.get("merchant_id", ""),
            "token_id": row.get("merchant_id", ""),
            "token_requestor_id": row.get("pan_canonical", ""),
            "device_fingerprint_id": row.get("cardholder_id", ""),
            "terminal_id": row.get("pan_canonical", ""),
            "merchant_id": row.get("pan_canonical", ""),
            "bin_prefix": row.get("merchant_id", ""),
            "vpa": row.get("payee_vpa", ""),
            "beneficiary_id": row.get("cardholder_id", ""),
        }
        for kt in ENTITY_KEYS:
            kv = str(row.get(kt, "") or "")
            if not kv:
                continue
            st = self.state.setdefault((kt, kv), EntityState())
            st.observe(ts, amount, str(counterparty_for.get(kt, "") or ""))
            if kt == "beneficiary_id":
                if str(row.get("message_kind", "")) == "inbound_credit":
                    st.inflow += amount
                elif str(row.get("message_kind", "")) == "onward_send":
                    st.outflow += amount

    def fetch_multi(self, row: Mapping[str, Any]) -> dict[str, float]:
        """ONE round trip for all nine keys. The design decision that makes the target reachable.

        Returns a flat dict of sketch features. Lose the batching — read the keys one at a time —
        and the per-call cost multiplies by nine, which is what `bench/` measures.
        """
        ts = float(row.get("ts", 0.0))
        self.n_fetches += 1
        out: dict[str, float] = {}
        for kt in ENTITY_KEYS:
            kv = str(row.get(kt, "") or "")
            self.n_keys_fetched += 1
            st = self.state.get((kt, kv)) if kv else None
            for wname, wsec in WINDOWS.items():
                out[f"sk_{kt}_{wname}_count"] = float(st.window_count(ts, wsec)) if st else -1.0
                out[f"sk_{kt}_{wname}_sum"] = float(st.window_sum(ts, wsec)) if st else -1.0
            out[f"sk_{kt}_distinct"] = float(st.hll.estimate()) if st else -1.0
            out[f"sk_{kt}_age_days"] = float(st.age_days(ts)) if st else -1.0
        ben = str(row.get("beneficiary_id", "") or "")
        bst = self.state.get(("beneficiary_id", ben)) if ben else None
        out["sk_ben_inflow"] = float(bst.inflow) if bst else -1.0
        out["sk_ben_outflow"] = float(bst.outflow) if bst else -1.0
        out["sk_ben_in_out_skew"] = (
            float(abs(bst.inflow - bst.outflow) / bst.inflow) if bst and bst.inflow > 0 else -1.0
        )
        return out

    @staticmethod
    def reduced_vector(row: Mapping[str, Any]) -> dict[str, float]:
        """THE DEGRADED FEATURE VECTOR, used when the store times out.

        Named, not implicit. It contains only what is derivable from the message ITSELF — no
        aggregates, no graph, no history. Recall is lower in this mode and `bench/` measures how much
        lower, because a fail-open path whose cost is unmeasured is a fail-open path nobody trusts.
        """
        out: dict[str, float] = {}
        for kt in ENTITY_KEYS:
            for wname in WINDOWS:
                out[f"sk_{kt}_{wname}_count"] = -1.0
                out[f"sk_{kt}_{wname}_sum"] = -1.0
            out[f"sk_{kt}_distinct"] = -1.0
            out[f"sk_{kt}_age_days"] = -1.0
        out["sk_ben_inflow"] = -1.0
        out["sk_ben_outflow"] = -1.0
        out["sk_ben_in_out_skew"] = -1.0
        return out

    def sketch_risk_score(self, row: Mapping[str, Any]) -> float:
        """A cheap inline risk contribution from the sketches alone.

        This is the `sketch` component in the fusion. It is deliberately a simple bounded
        combination rather than a model: the sketches' job is to make graph signal EXIST at t=0, and
        a learned model over them would be a second G1 with worse features.
        """
        feats = self.fetch_multi(row)
        terms: list[float] = []
        # Beneficiary fan-in relative to a plausible ceiling.
        d = feats.get("sk_beneficiary_id_distinct", -1.0)
        if d >= 0:
            terms.append(min(d / 40.0, 1.0))
        # Value conservation net of a skim: a TIGHT skew is the mule signature.
        skew = feats.get("sk_ben_in_out_skew", -1.0)
        if skew >= 0:
            terms.append(max(0.0, 1.0 - skew / 0.15))
        # PAN-level token-requestor fan-out.
        tf = feats.get("sk_token_requestor_id_distinct", -1.0)
        if tf >= 0:
            terms.append(min(tf / 12.0, 1.0))
        # Device sharing.
        dv = feats.get("sk_device_fingerprint_id_distinct", -1.0)
        if dv >= 0:
            terms.append(min(dv / 6.0, 1.0))
        # Terminal-level distinct cards, the enumeration signature.
        tc = feats.get("sk_terminal_id_1h_count", -1.0)
        if tc >= 0:
            terms.append(min(tc / 30.0, 1.0))
        return float(np.mean(terms)) if terms else 0.0

    # ---- the footprint report ---------------------------------------------------------
    def footprint(self) -> dict[str, Any]:
        """Stated as values-per-entity-per-key-type x active entities. NEVER a round total."""
        per_key: dict[str, dict[str, float]] = {}
        values_per_entity = len(WINDOWS) * 2 + 2      # counts, sums, distinct, age
        for kt in ENTITY_KEYS:
            n = sum(1 for (k, _v) in self.state if k == kt)
            per_key[kt] = {
                "active_entities": float(n),
                "values_per_entity": float(values_per_entity),
                "hll_bytes_per_entity": float(HyperLogLogLite().n_bytes()),
                "values_total": float(n * values_per_entity),
            }
        return {
            "entity_key_types": len(ENTITY_KEYS),
            "windows": list(WINDOWS),
            "per_key_type": per_key,
            "batched_fetch": {
                "n_fetches": self.n_fetches,
                "n_keys_fetched": self.n_keys_fetched,
                "keys_per_fetch": (self.n_keys_fetched / self.n_fetches) if self.n_fetches else 0.0,
                "note": (
                    "ONE round trip for all nine keys. This is the decision that makes the latency "
                    "target reachable at all; bench/ measures the unbatched cost for comparison."
                ),
            },
            "footprint_statement": (
                "Footprint is reported as values-per-entity-per-key-type x active entities, never "
                "as a round total, because a round total hides which key type dominates."
            ),
            "degradation_policy": (
                "Feature-fetch timeout at N ms -> the NAMED reduced feature vector -> G0-only. p99 "
                "is re-measured under injected store latency so the fallback has a number."
            ),
        }
