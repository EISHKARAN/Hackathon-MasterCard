"""HARD-BENIGN-12 and HARD-BENIGN-B — deliberately adversarial LEGITIMATE cohorts.

WHAT THESE ARE FOR: they are the guard rail that stops "win by declining everything". Aggregate
FPR is dominated by boring traffic and hides the customers a fraud model actually destroys. These
twelve (payer-side) and six (beneficiary-side) cohorts are the ones that generate complaint calls,
and false-positive rate is reported ON THEM SEPARATELY, never only in aggregate.

WHAT WE CLAIM, EXACTLY: that they are HARDER than an aggregate benign population. NOT that they
are representative of one. Their composition is authored by us and is not a sample of real
legitimate traffic, and that sentence goes on the slide.

WHY THE BENEFICIARY-SIDE TWIN EXISTS: GATE-B's entire feature list — in-out skew, short dwell,
high payer-set fan-in, low account age, no biller continuity, concentrated first-credit source —
is ALSO AN EXACT DESCRIPTION OF A LEGITIMATE NEW RECEIVER. That is the ethical and regulatory soft
spot of every beneficiary-side control, so false-freeze rate and false-hold rate on HARD-BENIGN-B
are headline metrics alongside HARD-BENIGN-12 false positives. A frozen legitimate receiver is a
materially worse harm than a declined transaction.

SIZING, honestly: a +-0.05pp guardrail on an FPR near 0.1% needs on the order of 1e5-1e6
legitimate rows per cohort per loop arm. We do not buy that at demo scale. `required_n_for_mde()`
computes what we WOULD need, `realised_mde()` computes what we actually bought, and the report
prints the realised MDE next to every cohort. Reporting a 0.03pp movement as a pass when the
interval spans +-0.4pp would forfeit exactly the credibility this module exists to earn.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from sim.schema import HARD_BENIGN_12_TAGS, HARD_BENIGN_B_TAGS


@dataclass(frozen=True)
class CohortSpec:
    """One adversarially-legitimate cohort.

    `why_hard` names the feature it is designed to trip. That is the point of each cohort: not
    "some unusual legitimate traffic" but "the specific legitimate traffic that looks like the
    specific attack we claim to catch".
    """

    tag: str
    label: str
    why_hard: str
    trips_features: tuple[str, ...]
    #: Mutations applied to an otherwise ordinary event to realise the cohort.
    mutate: Callable[[Any, np.random.Generator], None]


# ---------------------------------------------------------------------------------------
# HARD-BENIGN-12 (payer side)
# ---------------------------------------------------------------------------------------

def _m_bereavement(ev: Any, rng: np.random.Generator) -> None:
    # A cluster of unusual high-value spend in a compressed window, in categories the cardholder
    # has never used, often in a different city. Reads as a takeover.
    ev.amount_inr = float(np.round(abs(rng.normal(48_000.0, 22_000.0)) + 3_000.0, 2))
    ev.mcc = "7261" if rng.random() < 0.5 else "4111"
    ev.geo_cell = f"gc{int(rng.integers(0, 220)):04d}"


def _m_wedding(ev: Any, rng: np.random.Generator) -> None:
    # Many large transactions across jewellery, catering, travel, in days. Velocity + value.
    ev.amount_inr = float(np.round(abs(rng.normal(120_000.0, 60_000.0)) + 8_000.0, 2))
    ev.mcc = str(rng.choice(["5944", "5812", "4722", "5651"]))


def _m_relocation(ev: Any, rng: np.random.Generator) -> None:
    # Every geo feature breaks at once, permanently. Reads as geovelocity fraud.
    ev.geo_cell = f"gc{int(rng.integers(0, 220)):04d}"
    ev.acceptor_country = "IN"
    ev.amount_inr = float(np.round(abs(rng.normal(24_000.0, 12_000.0)) + 1_000.0, 2))


def _m_new_phone_reprovision(ev: Any, rng: np.random.Generator) -> None:
    # A brand-new device provisioning tokens and spending within minutes. This is EXACTLY the
    # ATK-T1 signature and it happens to every customer who buys a phone.
    ev.device_age_days = float(np.round(rng.uniform(0.0, 0.6), 3))
    ev.token_assurance_level = str(rng.choice(["low", "medium"], p=[0.4, 0.6]))
    ev.provisioning_to_first_spend_minutes = float(abs(rng.normal(11.0, 7.0)))
    ev.cvm_result = "cdcvm"


def _m_gig_fanin(ev: Any, rng: np.random.Generator) -> None:
    # Many unrelated payers into one receiver, short dwell, tight in-out skew. A mule signature,
    # produced by a gig worker being paid.
    ev.beneficiary_distinct_payers_24h = int(rng.integers(14, 70))
    ev.beneficiary_fanin_degree = ev.beneficiary_distinct_payers_24h
    ev.beneficiary_dwell_seconds = float(abs(rng.normal(900.0, 600.0)))
    ev.beneficiary_onward_send_minutes = ev.beneficiary_dwell_seconds / 60.0


def _m_festival_travel(ev: Any, rng: np.random.Generator) -> None:
    ev.geo_cell = f"gc{int(rng.integers(0, 220)):04d}"
    ev.mcc = str(rng.choice(["4111", "4722", "7011", "5812"]))
    ev.amount_inr = float(np.round(abs(rng.normal(16_000.0, 9_000.0)) + 500.0, 2))


def _m_first_high_ticket(ev: Any, rng: np.random.Generator) -> None:
    # The first transaction of its size in the cardholder's history. Every ratio-to-own-baseline
    # feature spikes, which is the whole design of those features.
    ev.amount_inr = float(np.round(abs(rng.normal(180_000.0, 70_000.0)) + 20_000.0, 2))
    ev.mcc = str(rng.choice(["5732", "5044", "5511", "7011"]))


def _m_joint_account(ev: Any, rng: np.random.Generator) -> None:
    # Two humans, one instrument, two devices, two geo cells, concurrently. Reads as a shared
    # credential.
    ev.geo_cell = f"gc{int(rng.integers(0, 220)):04d}"
    ev.device_age_days = float(np.round(rng.uniform(30.0, 900.0), 1))


def _m_seasonal_merchant_ramp(ev: Any, rng: np.random.Generator) -> None:
    # A small merchant's volume steps up 5x in a fortnight. Identical shape to a bust-out ramp.
    ev.merchant_age_days = float(np.round(rng.uniform(45.0, 400.0), 1))
    ev.amount_inr = float(np.round(abs(rng.normal(2_400.0, 1_100.0)) + 100.0, 2))


def _m_student_fee(ev: Any, rng: np.random.Generator) -> None:
    # Many payers to one institutional payee in a burst, once a term.
    ev.beneficiary_category = "biller"
    ev.beneficiary_distinct_payers_24h = int(rng.integers(40, 300))
    ev.beneficiary_fanin_degree = ev.beneficiary_distinct_payers_24h
    ev.amount_inr = float(np.round(abs(rng.normal(42_000.0, 18_000.0)) + 2_000.0, 2))


def _m_nri_remittance(ev: Any, rng: np.random.Generator) -> None:
    # Foreign inbound to an Indian account, forwarded to family within hours. In-out skew tight,
    # dwell short, counterparties unrelated. A textbook layering shape, entirely legitimate.
    ev.acceptor_country = str(rng.choice(["AE", "US", "GB", "SG"]))
    ev.beneficiary_dwell_seconds = float(abs(rng.normal(6_500.0, 4_000.0)))
    ev.beneficiary_onward_send_minutes = ev.beneficiary_dwell_seconds / 60.0
    ev.amount_inr = float(np.round(abs(rng.normal(85_000.0, 40_000.0)) + 5_000.0, 2))


def _m_medical_fd_liquidation(ev: Any, rng: np.random.Generator) -> None:
    # A fixed deposit liquidated then swept out in minutes, at night. This is the ATK-U1
    # coercion signature, produced by a genuine medical emergency.
    ev.hour_ist = float(np.clip(rng.normal(2.5, 1.5), 0.0, 23.99))
    ev.amount_inr = float(np.round(abs(rng.normal(220_000.0, 90_000.0)) + 20_000.0, 2))
    ev.beneficiary_dwell_seconds = float(abs(rng.normal(400.0, 250.0)))
    ev.beneficiary_onward_send_minutes = ev.beneficiary_dwell_seconds / 60.0
    ev.fd_liquidation_flag = True


HARD_BENIGN_12: tuple[CohortSpec, ...] = (
    CohortSpec("hb12_bereavement", "Bereavement spend cluster",
               "Unusual categories, unusual city, compressed window — reads as account takeover.",
               ("multi_key_velocity_ratio", "mcc_novelty", "geo_novelty"), _m_bereavement),
    CohortSpec("hb12_wedding", "Wedding spend",
               "Many large tickets in days across unrelated high-value categories.",
               ("amount_ratio_to_own_baseline", "multi_key_velocity_ratio"), _m_wedding),
    CohortSpec("hb12_relocation", "Relocation",
               "Every geo feature breaks at once and stays broken. Reads as geovelocity fraud.",
               ("geo_novelty", "geovelocity_break"), _m_relocation),
    CohortSpec("hb12_new_phone_reprovision", "New-phone token reprovisioning",
               "New device, low token assurance, spend within minutes — the exact ATK-T1 shape.",
               ("provisioning_to_first_spend_minutes", "token_assurance_vs_device_age"),
               _m_new_phone_reprovision),
    CohortSpec("hb12_gig_fanin", "Gig-worker fan-in",
               "Many unrelated payers, short dwell, tight in-out skew — the mule signature.",
               ("beneficiary_fanin_degree", "in_out_skew", "pass_through_dwell_seconds"),
               _m_gig_fanin),
    CohortSpec("hb12_festival_travel", "Festival travel",
               "Geo and category break together during the festival window.",
               ("geo_novelty", "mcc_novelty"), _m_festival_travel),
    CohortSpec("hb12_first_high_ticket", "First high-ticket purchase",
               "Every ratio-to-own-baseline feature spikes, because there is no baseline for it.",
               ("amount_ratio_to_own_baseline",), _m_first_high_ticket),
    CohortSpec("hb12_joint_account", "Joint-account co-spending",
               "Two humans, one instrument, two devices, two cells, concurrently.",
               ("device_churn", "geovelocity_break"), _m_joint_account),
    CohortSpec("hb12_seasonal_merchant_ramp", "Small-merchant seasonal ramp",
               "A 5x volume step in a fortnight — identical shape to a bust-out ramp.",
               ("merchant_ramp_curve_shape", "merchant_ticket_step_change"),
               _m_seasonal_merchant_ramp),
    CohortSpec("hb12_student_fee", "Student-fee disbursal",
               "Hundreds of payers to one payee in a burst, once a term.",
               ("beneficiary_fanin_degree", "repeat_payer_share"), _m_student_fee),
    CohortSpec("hb12_nri_remittance", "NRI remittance corridor",
               "Foreign inbound forwarded to family in hours: textbook layering, fully legitimate.",
               ("in_out_skew", "pass_through_dwell_seconds", "foreign_issuer_concentration"),
               _m_nri_remittance),
    CohortSpec("hb12_medical_fd_liquidation", "Medical-emergency FD liquidation",
               "FD liquidated then swept at night — the exact ATK-U1 coercion signature.",
               ("fd_liquidation_before_transfer", "beneficiary_onward_send_minutes"),
               _m_medical_fd_liquidation),
)


# ---------------------------------------------------------------------------------------
# HARD-BENIGN-B (beneficiary side)
# ---------------------------------------------------------------------------------------

def _mb_new_gig_payee(ev: Any, rng: np.random.Generator) -> None:
    ev.beneficiary_account_age_days = float(np.round(rng.uniform(0.0, 6.0), 2))
    ev.beneficiary_distinct_payers_24h = int(rng.integers(9, 45))
    ev.beneficiary_fanin_degree = ev.beneficiary_distinct_payers_24h
    ev.beneficiary_dwell_seconds = float(abs(rng.normal(1_100.0, 700.0)))
    ev.beneficiary_onward_send_minutes = ev.beneficiary_dwell_seconds / 60.0
    ev.beneficiary_category = "p2p_individual"


def _mb_week_old_merchant(ev: Any, rng: np.random.Generator) -> None:
    ev.beneficiary_account_age_days = float(np.round(rng.uniform(3.0, 9.0), 2))
    ev.beneficiary_category = "small_merchant"
    ev.beneficiary_distinct_payers_24h = int(rng.integers(5, 40))
    ev.beneficiary_fanin_degree = ev.beneficiary_distinct_payers_24h
    ev.beneficiary_dwell_seconds = float(abs(rng.normal(2_600.0, 1_500.0)))
    ev.beneficiary_onward_send_minutes = ev.beneficiary_dwell_seconds / 60.0


def _mb_school_fee(ev: Any, rng: np.random.Generator) -> None:
    ev.beneficiary_category = "biller"
    ev.beneficiary_distinct_payers_24h = int(rng.integers(60, 400))
    ev.beneficiary_fanin_degree = ev.beneficiary_distinct_payers_24h
    ev.beneficiary_account_age_days = float(np.round(rng.uniform(20.0, 800.0), 1))


def _mb_street_vendor(ev: Any, rng: np.random.Generator) -> None:
    ev.beneficiary_account_age_days = float(np.round(rng.uniform(1.0, 20.0), 2))
    ev.beneficiary_category = "small_merchant"
    ev.beneficiary_distinct_payers_24h = int(rng.integers(20, 160))
    ev.beneficiary_fanin_degree = ev.beneficiary_distinct_payers_24h
    ev.beneficiary_dwell_seconds = float(abs(rng.normal(700.0, 400.0)))
    ev.beneficiary_onward_send_minutes = ev.beneficiary_dwell_seconds / 60.0


def _mb_chit_collection(ev: Any, rng: np.random.Generator) -> None:
    # Community/chit collection: money in from many, straight out to one. Near-perfect value
    # conservation with a tiny skim — the ATK-G1 signature, run by a neighbourhood association.
    ev.beneficiary_distinct_payers_24h = int(rng.integers(8, 30))
    ev.beneficiary_fanin_degree = ev.beneficiary_distinct_payers_24h
    ev.beneficiary_fanout_degree = 1
    ev.beneficiary_dwell_seconds = float(abs(rng.normal(340.0, 220.0)))
    ev.beneficiary_onward_send_minutes = ev.beneficiary_dwell_seconds / 60.0


def _mb_freelancer_foreign(ev: Any, rng: np.random.Generator) -> None:
    ev.acceptor_country = str(rng.choice(["US", "GB", "DE", "AU"]))
    ev.beneficiary_account_age_days = float(np.round(rng.uniform(10.0, 300.0), 1))
    ev.beneficiary_first_credit_source = "foreign_single_source"
    ev.beneficiary_distinct_payers_24h = 1
    ev.beneficiary_fanin_degree = 1
    ev.amount_inr = float(np.round(abs(rng.normal(160_000.0, 70_000.0)) + 10_000.0, 2))


HARD_BENIGN_B: tuple[CohortSpec, ...] = (
    CohortSpec("hbb_new_gig_aggregator_payee", "New gig-aggregator payee",
               "Days-old account, dozens of unrelated payers, short dwell. Every GATE-B feature.",
               ("beneficiary_account_age_days", "beneficiary_fanin_degree", "in_out_skew"),
               _mb_new_gig_payee),
    CohortSpec("hbb_week_old_small_merchant", "Week-old small merchant",
               "A genuinely new business. Low age plus rising fan-in is the ghost-merchant shape.",
               ("beneficiary_account_age_days", "repeat_payer_share"), _mb_week_old_merchant),
    CohortSpec("hbb_school_fee_collection", "School-fee collection account",
               "Hundreds of payers in a burst. Fan-in alone cannot separate this from farming.",
               ("beneficiary_fanin_degree",), _mb_school_fee),
    CohortSpec("hbb_festival_street_vendor", "Festival-season street vendor",
               "New payee VPA, many payer devices in one geohash, instant sweep to a bank account.",
               ("payee_vpa_age_days", "distinct_payer_devices_per_geohash",
                "beneficiary_onward_send_minutes"), _mb_street_vendor),
    CohortSpec("hbb_community_chit_collection", "Community / chit collection",
               "Near-perfect value conservation with a tiny skim — the exact ATK-G1 signature.",
               ("in_out_skew", "pass_through_dwell_seconds"), _mb_chit_collection),
    CohortSpec("hbb_freelancer_foreign_inbound", "Freelancer with foreign inbound",
               "Single concentrated first-credit source from abroad, large tickets.",
               ("first_credit_source_concentration", "foreign_issuer_concentration"),
               _mb_freelancer_foreign),
)


ALL_COHORTS: tuple[CohortSpec, ...] = HARD_BENIGN_12 + HARD_BENIGN_B


def cohort_by_tag(tag: str) -> CohortSpec:
    for c in ALL_COHORTS:
        if c.tag == tag:
            return c
    raise KeyError(f"unknown cohort tag {tag!r}")


def _assert_tags_consistent() -> None:
    """The schema's tag list and this module's cohort list must not drift apart."""
    schema_12 = set(HARD_BENIGN_12_TAGS)
    mine_12 = {c.tag for c in HARD_BENIGN_12}
    if schema_12 != mine_12:
        raise AssertionError(
            f"HARD-BENIGN-12 tags disagree between sim/schema.py and sim/cohorts.py: "
            f"schema-only={sorted(schema_12 - mine_12)}, cohorts-only={sorted(mine_12 - schema_12)}"
        )
    schema_b = set(HARD_BENIGN_B_TAGS)
    mine_b = {c.tag for c in HARD_BENIGN_B}
    if schema_b != mine_b:
        raise AssertionError(
            f"HARD-BENIGN-B tags disagree between sim/schema.py and sim/cohorts.py: "
            f"schema-only={sorted(schema_b - mine_b)}, cohorts-only={sorted(mine_b - schema_b)}"
        )


_assert_tags_consistent()


# ---------------------------------------------------------------------------------------
# Sizing arithmetic — what we would need, versus what we bought.
# ---------------------------------------------------------------------------------------

def required_n_for_mde(baseline_rate: float, mde_pp: float, alpha: float = 0.05, power: float = 0.80) -> int:
    """Rows per arm needed to detect an `mde_pp` percentage-point move in a rate.

    Two-proportion normal approximation. At an FPR near 0.1% and an MDE of 0.05pp this returns a
    number in the 1e5-1e6 range, which is exactly the point: the guardrail the design would like
    is not purchasable at demo scale, so we restate the guardrail at the resolution we can buy.
    """
    p1 = max(1e-9, float(baseline_rate))
    p2 = max(1e-9, p1 + float(mde_pp) / 100.0)
    pbar = (p1 + p2) / 2.0
    z_a = 1.959963984540054 if abs(alpha - 0.05) < 1e-9 else _z(1.0 - alpha / 2.0)
    z_b = 0.8416212335729143 if abs(power - 0.80) < 1e-9 else _z(power)
    num = (z_a * math.sqrt(2.0 * pbar * (1.0 - pbar)) + z_b * math.sqrt(
        p1 * (1.0 - p1) + p2 * (1.0 - p2)
    )) ** 2
    den = (p2 - p1) ** 2
    return int(math.ceil(num / den)) if den > 0 else -1


def realised_mde(baseline_rate: float, n_per_arm: int, alpha: float = 0.05, power: float = 0.80) -> float:
    """The smallest percentage-point move `n_per_arm` rows can actually detect.

    THIS is the number printed next to every cohort. Reporting a 0.03pp movement as a pass when
    the interval spans +-0.4pp would forfeit the credibility the cohorts exist to earn.
    """
    n = int(n_per_arm)
    if n <= 1:
        return float("inf")
    p = max(1e-9, float(baseline_rate))
    z_a = 1.959963984540054 if abs(alpha - 0.05) < 1e-9 else _z(1.0 - alpha / 2.0)
    z_b = 0.8416212335729143 if abs(power - 0.80) < 1e-9 else _z(power)
    # Solve approximately for delta with p2 ~ p1 (variance held at p).
    se = math.sqrt(2.0 * p * (1.0 - p) / n)
    return float((z_a + z_b) * se * 100.0)


def _z(q: float) -> float:
    """Inverse normal CDF via the Acklam rational approximation (|err| < 1.15e-9)."""
    if not (0.0 < q < 1.0):
        raise ValueError(f"quantile must be in (0,1), got {q}")
    a = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
    b = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00)
    plow, phigh = 0.02425, 1.0 - 0.02425
    if q < plow:
        x = math.sqrt(-2.0 * math.log(q))
        return (((((c[0] * x + c[1]) * x + c[2]) * x + c[3]) * x + c[4]) * x + c[5]) / (
            (((d[0] * x + d[1]) * x + d[2]) * x + d[3]) * x + 1.0
        )
    if q > phigh:
        x = math.sqrt(-2.0 * math.log(1.0 - q))
        return -(((((c[0] * x + c[1]) * x + c[2]) * x + c[3]) * x + c[4]) * x + c[5]) / (
            (((d[0] * x + d[1]) * x + d[2]) * x + d[3]) * x + 1.0
        )
    x = q - 0.5
    r = x * x
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * x / (
        ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0
    )


def sizing_report(rows_per_cohort_12: int, rows_per_cohort_b: int, baseline_fpr: float = 0.001) -> dict[str, object]:
    """The table that ships next to every cohort FPR. Honest about what we bought."""
    return {
        "baseline_fpr_assumed": baseline_fpr,
        "design_target_mde_pp": 0.05,
        "n_required_for_design_target": required_n_for_mde(baseline_fpr, 0.05),
        "hard_benign_12": {
            "rows_per_cohort": rows_per_cohort_12,
            "realised_mde_pp": round(realised_mde(baseline_fpr, rows_per_cohort_12), 4),
            "n_cohorts": len(HARD_BENIGN_12),
        },
        "hard_benign_b": {
            "rows_per_cohort": rows_per_cohort_b,
            "realised_mde_pp": round(realised_mde(baseline_fpr, rows_per_cohort_b), 4),
            "n_cohorts": len(HARD_BENIGN_B),
        },
        "restated_guardrail": (
            "Because the design's +-0.05pp guardrail needs ~1e5-1e6 rows per cohort per arm and we "
            "do not buy that at these sizes, the guardrail we actually assert is: UPPER BOUND OF "
            "THE BOOTSTRAP 95% CI ON FP MOVEMENT <= +0.25pp, with the realised MDE printed beside "
            "every cohort."
        ),
        "authorship_note": (
            "These cohorts are OUR construction, not a validated public benchmark. The claim is "
            "'we tested the twelve hardest benign cases we could specify', not 'we tested the "
            "industry's'."
        ),
    }
