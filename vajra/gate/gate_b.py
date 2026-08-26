"""GATE-B — the beneficiary-side gate, and why it is the decisive control.

Indian loss is dominated by AUTHORISED push payments [VERIFY current share against RBI/NPCI
published figures before any number is spoken]. In coercion, task-ladder, screen-share, QR-swap and
payroll-redirection attacks, EVERY payer-side authentication signal is genuine: correct device,
correct binding, correct PIN, correct customer physically present. There is no payer-side artefact
to detect because there is no payer-side compromise.

So the enforceable control point is the BENEFICIARY ACCOUNT — the one node in the graph that is
reused across victims, that has a measurable age, and that must eventually move money onward.

THREE COMPONENTS:
  1. inbound-credit scorer      value conservation, dwell, payer-set structure, account age
  2. onboarding-cohort scorer   POPULATION statistics over a batch, never per-application
  3. bloom risk-exchange stub   a mule prior without either institution sharing PII — A STUB

THE ETHICAL SOFT SPOT, stated because it is the whole reason HARD-BENIGN-B exists: this feature list
is ALSO AN EXACT DESCRIPTION OF A LEGITIMATE NEW RECEIVER. A new gig payee, a week-old small
merchant, a school-fee collection account and a chit collection all look like a mule. So false-freeze
and false-hold rates on HARD-BENIGN-B are HEADLINE metrics alongside recall, the freeze payload
carries a bounded maximum hold and an auto-release rule, and the disparate-impact table extends to
hold and freeze actions. A frozen legitimate receiver is a materially worse harm than a declined
transaction.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from core.config import Config, load_config


# =======================================================================================
# The bloom-filter beneficiary-risk exchange — A STUB, AND LABELLED ONE
# =======================================================================================

@dataclass
class BloomRiskExchange:
    """Membership test over beneficiary identifiers, sharing no PII by construction.

    ============================== THIS IS A STUB ======================================
    Its real-world availability and regulatory permissibility are UNVERIFIED [VERIFY]. We do not
    claim any counterparty would participate.

    THE PAYER-SIDE PATH NEVER DEPENDS ON IT ALONE. `no_exchange_fallback()` returns what GATE-I uses
    instead — on-us beneficiary history, new-payee age, first-payment-to-this-payee, payer-side
    cooling-off — and that fallback is published as its OWN VIEW in the visibility ablation, so the
    degraded case is quantified rather than asserted.

    A false-positive rate is INHERENT to a bloom filter and it is reported, not hidden: a membership
    hit is probabilistic, so `prior_from_exchange` is never the sole basis for an action and the
    reason code says so.
    ====================================================================================
    """

    n_bits: int = 1 << 16
    n_hashes: int = 4
    bits: bytearray = field(default_factory=lambda: bytearray(1 << 13), repr=False)
    n_inserted: int = 0
    implemented: bool = True
    verified: bool = False

    def _positions(self, key: str) -> list[int]:
        out: list[int] = []
        for i in range(self.n_hashes):
            h = hashlib.blake2b(f"{i}|{key}".encode("utf-8"), digest_size=8).digest()
            out.append(int.from_bytes(h, "big") % self.n_bits)
        return out

    def add(self, beneficiary_id: str) -> None:
        for p in self._positions(beneficiary_id):
            self.bits[p // 8] |= 1 << (p % 8)
        self.n_inserted += 1

    def contains(self, beneficiary_id: str) -> bool:
        return all(self.bits[p // 8] & (1 << (p % 8)) for p in self._positions(beneficiary_id))

    def expected_false_positive_rate(self) -> float:
        """Reported, not hidden. (1 - e^{-kn/m})^k."""
        if self.n_inserted == 0:
            return 0.0
        k, n, m = self.n_hashes, self.n_inserted, self.n_bits
        return float((1.0 - np.exp(-k * n / m)) ** k)

    def prior_from_exchange(self, beneficiary_id: str) -> float:
        """A mule prior in [0, 1]. Deliberately capped well below 1.

        Capped because a bloom hit is PROBABILISTIC and because the exchange is unverified. A prior
        that could reach 1.0 would let an unverified stub decide an action on its own.
        """
        if not (self.implemented and beneficiary_id):
            return 0.0
        return 0.55 if self.contains(beneficiary_id) else 0.0

    def status(self) -> dict[str, Any]:
        return {
            "status": "STUB",
            "implemented": self.implemented,
            "verified": self.verified,
            "n_inserted": self.n_inserted,
            "n_bits": self.n_bits,
            "n_hashes": self.n_hashes,
            "expected_false_positive_rate": self.expected_false_positive_rate(),
            "shares_pii": False,
            "verify_note": (
                "Real-world availability and regulatory permissibility are UNVERIFIED. If shared "
                "beneficiary signals are unobtainable, GATE-B degrades to a single-institution "
                "inbound-credit scorer with materially weaker recall, and the visibility ablation "
                "is the thing that quantifies exactly how much weaker."
            ),
        }

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "bloom_exchange.json").write_text(
            json.dumps(
                {
                    "n_bits": self.n_bits,
                    "n_hashes": self.n_hashes,
                    "n_inserted": self.n_inserted,
                    "bits_hex": self.bits.hex(),
                    "status": self.status(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> "BloomRiskExchange":
        d = json.loads((directory / "bloom_exchange.json").read_text(encoding="utf-8"))
        return cls(
            n_bits=int(d["n_bits"]),
            n_hashes=int(d["n_hashes"]),
            bits=bytearray.fromhex(d["bits_hex"]),
            n_inserted=int(d["n_inserted"]),
        )


def no_exchange_fallback(row: Mapping[str, Any]) -> dict[str, float]:
    """What the payer side uses when the exchange is unavailable.

    Published as its own ablation view, so the no-exchange case is a MEASURED result rather than a
    reassurance. None of these requires any counterparty to cooperate.
    """
    age = float(row.get("beneficiary_account_age_days", -1.0) or -1.0)
    return {
        "on_us_beneficiary_history": float(row.get("beneficiary_inbound_credit_count_24h", -1.0) or -1.0),
        "new_payee_age_days": age,
        "first_payment_to_this_payee": 1.0 if age >= 0 and age < 1.0 else 0.0,
        "payer_side_cooling_off_applicable": 1.0 if age >= 0 and age < 2.0 else 0.0,
    }


# =======================================================================================
# The onboarding-cohort scorer — POPULATION statistics, never per-application
# =======================================================================================

@dataclass
class OnboardingCohortScorer:
    """Scores the STATISTICAL FOOTPRINT OF A BATCH of onboardings.

    THIS IS THE ONLY LAYER THAT CAN SEE THE SYNTHETIC-IDENTITY FAMILIES AT ALL, because each
    application clears KYC individually and the fraud is visible only as a cohort statistic.

    WHAT WE DELIBERATELY DO NOT BUILD, marked design-only in the UI and on the slide: document and
    narrative embeddings, capture geometry, and anything liveness-adjacent. We attempt no liveness or
    document forensics and produce NO BYPASS KNOWLEDGE. A full KYC-origination simulator is a second
    simulator wearing a bullet point's clothing.
    """

    #: Feature -> (weight, direction). Direction +1 means "higher is riskier".
    WEIGHTS: Mapping[str, tuple[float, int]] = field(
        default_factory=lambda: {
            "onboarding_batch_timing_cluster": (0.20, +1),
            "device_os_entropy_collapse": (0.22, +1),
            "asn_reuse_rate": (0.18, +1),
            "name_ngram_unlikelihood": (0.12, +1),
            "address_geocode_density": (0.10, +1),
            "first_credit_source_concentration_batch": (0.10, +1),
            "batch_kyc_tier_uniformity": (0.08, +1),
        }
    )
    #: Fitted percentile edges per feature, from the TRAINING window only.
    edges: dict[str, np.ndarray] = field(default_factory=dict, repr=False)
    fitted: bool = False

    DESIGN_ONLY_SIGNALS: tuple[str, ...] = (
        "virtual_camera_artefact",
        "frame_timing_regularity",
        "sensor_noise_absence",
        "lipsync_offset",
        "capture_geometry_reuse",
        "document_embedding_near_duplicate",
    )

    def fit(self, features: Mapping[str, np.ndarray]) -> "OnboardingCohortScorer":
        for name in self.WEIGHTS:
            v = np.asarray(features.get(name, np.zeros(0)), dtype=np.float64)
            v = v[v > -1.0]
            if v.size >= 20:
                self.edges[name] = np.quantile(v, np.linspace(0.0, 1.0, 101))
        self.fitted = bool(self.edges)
        return self

    def score(self, features: Mapping[str, np.ndarray]) -> np.ndarray:
        """Cohort risk in [0, 1]. Zero where no batch statistics are available."""
        n = 0
        for v in features.values():
            n = max(n, int(np.asarray(v).size))
        acc = np.zeros(n, dtype=np.float64)
        wsum = 0.0
        for name, (w, direction) in self.WEIGHTS.items():
            v = np.asarray(features.get(name, np.full(n, -1.0)), dtype=np.float64)
            e = self.edges.get(name)
            valid = v > -1.0
            pct = np.zeros(n, dtype=np.float64)
            if e is not None and e.size:
                pct[valid] = np.clip(np.searchsorted(e, v[valid], side="left") / (e.size - 1), 0.0, 1.0)
            if direction < 0:
                pct = 1.0 - pct
            acc += w * np.where(valid, pct, 0.0)
            wsum += w
        return acc / max(wsum, 1e-9)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "fitted": self.fitted,
            "features_used": sorted(self.WEIGHTS),
            "features_with_edges": sorted(self.edges),
            "unit": "population-level cohort statistic; NEVER per-application",
            "design_only_signals_not_built": list(self.DESIGN_ONLY_SIGNALS),
            "design_only_note": (
                "The list above is NOT IN THE ARTIFACT and is badged design-only in the UI and on "
                "the slide. Those signals are real observables and belong in the taxonomy; we do "
                "not build liveness or document forensics and we produce no bypass knowledge."
            ),
        }


# =======================================================================================
# The beneficiary decision: hold, freeze-recommend, or let it pass
# =======================================================================================

@dataclass
class BeneficiaryAction:
    action: str
    reason_codes: tuple[str, ...]
    hold_hours: int
    auto_release: bool
    #: Whether the action was raised on a HARD-BENIGN-B row. Counted so the false-freeze and
    #: false-hold rates are computed from the same code path that produced them.
    on_hard_benign: bool = False


def decide_beneficiary_action(
    *,
    score: float,
    row: Mapping[str, Any],
    t_hold: float,
    t_freeze: float,
    exchange_prior: float,
    cfg: Config | None = None,
) -> BeneficiaryAction:
    """Choose the beneficiary-side action.

    TWO ASYMMETRIES, both deliberate:

    *   `t_freeze` is materially higher than `t_hold`. A hold is bounded and auto-releases; a freeze
        recommendation escalates to a human. The cost matrix prices `false_freeze_cost` at several
        times `false_hold_cost` for exactly this reason.
    *   The EXCHANGE PRIOR CANNOT ESCALATE TO A FREEZE ON ITS OWN. The exchange is an unverified
        stub with an inherent bloom false-positive rate, so it may raise a hold and add a reason
        code, but a freeze needs on-us evidence too.
    """
    cfg = cfg or load_config()
    hold_cfg = cfg.beneficiary_hold
    codes: list[str] = []

    skew = float(row.get("in_out_skew", -1.0) or -1.0)
    dwell_min = float(row.get("beneficiary_onward_send_minutes", -1.0) or -1.0)
    fanin = float(row.get("beneficiary_distinct_payers_24h", -1.0) or -1.0)
    ben_age = float(row.get("beneficiary_account_age_days", -1.0) or -1.0)
    name_match = float(row.get("creditor_name_match_score", -1.0) or -1.0)
    conc = float(row.get("first_credit_source_concentration", -1.0) or -1.0)

    if 0.0 <= skew <= 0.05:
        codes.append("GB_IN_OUT_SKEW")
    if 0.0 <= dwell_min <= 10.0:
        codes.append("GB_SHORT_DWELL")
    if fanin >= 20.0 and 0.0 <= ben_age < 7.0:
        codes.append("GB_PAYER_FANIN")
    if 0.0 <= ben_age < 2.0:
        codes.append("GB_YOUNG_BENEFICIARY")
    if conc >= 0.6:
        codes.append("GB_FIRST_CREDIT_CONCENTRATION")
    if 0.0 <= name_match < 0.6:
        codes.append("GB_NAME_MISMATCH")
    if exchange_prior > 0.0:
        codes.append("GB_EXCHANGE_PRIOR")

    on_hard_benign = str(row.get("cohort_tag", "")).startswith("hbb_")
    # On-us evidence: everything except the exchange prior.
    on_us_codes = [c for c in codes if c != "GB_EXCHANGE_PRIOR"]

    if score >= t_freeze and len(on_us_codes) >= 2:
        return BeneficiaryAction(
            action="freeze_recommend",
            reason_codes=tuple(codes),
            hold_hours=int(hold_cfg["max_hold_hours"]),
            auto_release=bool(hold_cfg["auto_release_unless_escalated"]),
            on_hard_benign=on_hard_benign,
        )
    if score >= t_hold and on_us_codes:
        return BeneficiaryAction(
            action="hold",
            reason_codes=tuple(codes),
            hold_hours=int(hold_cfg["max_hold_hours"]),
            auto_release=True,
            on_hard_benign=on_hard_benign,
        )
    if score >= t_hold and codes:
        # Exchange prior alone: raise the code, take the SOFTEST action. An unverified stub does not
        # get to hold someone's money by itself.
        return BeneficiaryAction(
            action="review",
            reason_codes=tuple(codes),
            hold_hours=0,
            auto_release=True,
            on_hard_benign=on_hard_benign,
        )
    return BeneficiaryAction("approve", (), 0, True, on_hard_benign)


def false_action_rates(actions: Sequence[BeneficiaryAction], cohort_tags: Sequence[str]) -> dict[str, Any]:
    """FALSE-FREEZE AND FALSE-HOLD RATES ON HARD-BENIGN-B. Headline metrics, not appendix ones."""
    tags = np.asarray(cohort_tags, dtype=object).astype(str)
    acts = np.asarray([a.action for a in actions], dtype=object).astype(str)
    hbb = np.char.startswith(tags, "hbb_")
    out: dict[str, Any] = {
        "n_hard_benign_b": int(hbb.sum()),
        "false_freeze_rate": float((acts[hbb] == "freeze_recommend").mean()) if hbb.sum() else 0.0,
        "false_hold_rate": float((acts[hbb] == "hold").mean()) if hbb.sum() else 0.0,
        "false_review_rate": float((acts[hbb] == "review").mean()) if hbb.sum() else 0.0,
    }
    per_cohort: dict[str, dict[str, float]] = {}
    for tag in sorted({t for t in tags.tolist() if t.startswith("hbb_")}):
        m = tags == tag
        per_cohort[tag] = {
            "n": float(m.sum()),
            "freeze_rate": float((acts[m] == "freeze_recommend").mean()),
            "hold_rate": float((acts[m] == "hold").mean()),
        }
    out["per_cohort"] = per_cohort
    out["why_headline"] = (
        "A frozen legitimate receiver is a MATERIALLY WORSE HARM than a declined transaction, so "
        "these rates sit next to recall rather than in an appendix. Every GATE-B feature is also an "
        "exact description of a legitimate new receiver, which is why HARD-BENIGN-B exists."
    )
    return out
