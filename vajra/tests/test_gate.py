"""GATE unit invariants: fusion train/serve agreement, band ordering, capacity mass-point, G0 totality."""

from __future__ import annotations

import json

import numpy as np
import pytest

from gate.fusion import COMPONENTS, Fusion, _rankdata_average
from gate.g0_guards import G0Guards
from gate.g2_novelty import ECODDensity
from gate.policy import ActionTable, capacity_threshold


def test_fusion_train_serve_agree():
    """`combine` on the training data must reproduce the `fit`-time rank-average.

    This is the test that would have caught the train/serve skew bug: fit ranked over the population,
    serve meaned raw scores, and a quarter of ordinary traffic landed in the calibrator's saturated top.
    """
    rng = np.random.default_rng(3)
    comps = {c: rng.random(500) for c in COMPONENTS}
    # Introduce a mass point at zero, the exact condition that broke the previous build.
    for c in comps:
        comps[c][:200] = 0.0
    f = Fusion()
    f.fit(comps, labels=(rng.random(500) < 0.1).astype(int))
    fit_ranks = {c: _rankdata_average(comps[c]) for c in COMPONENTS}
    expected = f._fuse_from_ranks(fit_ranks)
    served = f.combine(comps)
    assert np.allclose(expected, served, atol=1e-9), "fusion fit and serve disagree on the training data"


def test_fusion_tail_transform_train_serve_agree():
    """The tail transform must not reintroduce the train/serve skew the rank ECDF exists to remove.

    Same invariant as `test_fusion_train_serve_agree`, on the other combine rule. The transform is
    applied INSIDE `_fuse_from_ranks`, so both paths get it -- this test is what pins that down.
    """
    rng = np.random.default_rng(11)
    comps = {c: rng.random(500) for c in COMPONENTS}
    for c in comps:
        comps[c][:200] = 0.0
    f = Fusion(tail_transform=True)
    f.fit(comps, labels=(rng.random(500) < 0.1).astype(int))
    expected = f._fuse_from_ranks({c: _rankdata_average(comps[c]) for c in COMPONENTS})
    assert np.allclose(expected, f.combine(comps), atol=1e-9)


def test_fusion_tail_transform_is_monotone_within_channel():
    """-log(1-r) must be order-preserving in r, so the transform reorders nothing WITHIN a channel.

    If this ever failed, the tail transform would be silently reranking on its own rather than only
    changing how much of the fused budget a channel spends near its extreme.
    """
    f = Fusion(weights={"g1": 1.0}, tail_transform=True)
    r = np.linspace(0.0, 1.0, 1000)
    out = f._fuse_from_ranks({"g1": r})
    assert np.all(np.diff(out) >= 0.0), "tail transform is not monotone in the rank"
    # And it must be BOUNDED by tail_eps rather than diverging at r == 1.
    assert np.isfinite(out).all()
    assert out.max() == pytest.approx(-np.log(f.tail_eps), rel=1e-9)


def test_fusion_meta_roundtrip_defaults_to_rank_average(tmp_path):
    """A bundle saved WITHOUT the tail flag must load as a rank average, not silently switch rules."""
    rng = np.random.default_rng(5)
    comps = {c: rng.random(200) for c in COMPONENTS}
    f = Fusion().fit(comps, labels=(rng.random(200) < 0.2).astype(int))
    f.save(tmp_path)
    meta = json.loads((tmp_path / "fusion_meta.json").read_text())
    del meta["tail_transform"]  # simulate a bundle written before the field existed
    (tmp_path / "fusion_meta.json").write_text(json.dumps(meta))
    assert Fusion.load(tmp_path).tail_transform is False


def test_capacity_threshold_never_alerts_whole_mass_point():
    """A quantile landing ON a tie must not alert every tied row (alerts are score >= t)."""
    s = np.concatenate([np.zeros(9000), np.linspace(0.1, 1.0, 1000)])  # 90% tied at zero
    t, rep = capacity_threshold(s, budget_share=0.02)
    alerted = float((s >= t).mean())
    assert alerted <= 0.02 + 1e-9, f"alerted {alerted:.4f} exceeds the 2% budget"


def test_capacity_threshold_all_identical_publishes_overflow():
    """If every score is identical, no threshold can separate them; the overflow must be reported."""
    s = np.zeros(1000)
    t, rep = capacity_threshold(s, budget_share=0.02)
    assert rep.get("budget_overflow") is True
    assert rep["realised_share"] > 0.02  # honestly reported, not hidden


def test_ecod_stays_uncalibrated_when_degenerate():
    """A degenerate spread must leave ECOD uncalibrated so it escalates nothing, not everything."""
    d = ECODDensity().fit(np.ones((100, 5)))  # zero variance
    assert not d.calibrated
    z = d.score_z(np.ones((10, 5)))
    assert np.allclose(z, 0.0), "uncalibrated ECOD must contribute zero, not flag every row"


def test_ecod_raw_score_is_not_a_zscore():
    """The raw ECOD score is a sum over features; its scale must be much larger than a z-score."""
    rng = np.random.default_rng(1)
    d = ECODDensity().fit(rng.normal(size=(2000, 50)))
    assert d.raw_mean > 10.0, "raw ECOD score should be a sum over 50 features, not near a z-score scale"
    assert d.calibrated


def test_action_bands_ordered():
    """friction <= review <= decline, globally and per rail. Prevents the band-collapse bug."""
    rng = np.random.default_rng(5)
    n = 4000
    scores = rng.random(n)
    rails = np.array(["upi-pay" if i % 2 else "card-cnp-3ds" for i in range(n)], dtype=object)
    amounts = rng.uniform(100, 50000, n)
    labels = (rng.random(n) < 0.01).astype(float)
    at = ActionTable.fit(scores, rails.tolist(), amounts, labels)
    assert at.global_t_friction <= at.global_t_review <= at.global_t_decline
    for rail in set(rails.tolist()):
        assert at.t_friction[rail] <= at.t_review[rail] <= at.t_decline[rail]


def test_friction_cap_never_escalates_a_high_scoring_rail():
    """A rail whose tail scores far above the global decline point must keep its friction band.

    THE REGRESSION THIS PINS. `t_friction` is per-rail from that rail's cap; `t_review`/`t_decline`
    are global. If the friction threshold is taken from the rail's WHOLE tail it can land above the
    global decline point, and `_enforce_ordering` then raises review and decline up to meet it --
    deleting both bands and converting the rail's entire friction band into auto-declines. At the
    full preset that hit `card-clearing-dispute` (8.07% of volume) the moment the fused score became
    discriminative enough to separate rails.

    A friction CAP bounds how much friction a rail may get. It must never escalate a rail.
    """
    rng = np.random.default_rng(17)
    # THE SHAPE MATTERS, and getting it wrong makes this test vacuous. Two conditions are needed:
    #   * SEVERAL ordinary rails, because `global_t_friction` is the MEDIAN of the per-rail
    #     thresholds -- with only two rails the hot rail drags the median up and nothing crosses;
    #   * the hot rail is a SMALL share of volume (~0.5%), because `global_t_review` is pinned at the
    #     staffed alert budget of 0.024% and so sits extremely far out in the global tail. Only when
    #     the hot rail is small does its own 98th percentile land ABOVE that global threshold.
    # 0.5% is chosen to match `agentic-commerce`, which is 0.45% of the real stream and did collapse.
    n, n_bulk_rails = 100_000, 5
    n_hot = int(n * 0.005)
    per = (n - n_hot) // n_bulk_rails
    bulk_names = [f"bulk-{i}" for i in range(n_bulk_rails)]
    parts, names = [], []
    for nm in bulk_names:
        parts.append(rng.uniform(0.0, 0.15, per))
        names += [nm] * per
    parts.append(rng.uniform(0.30, 0.95, n_hot))
    names += ["hot-rail"] * n_hot
    scores = np.concatenate(parts)
    rails = np.array(names, dtype=object)
    amounts = rng.uniform(100, 50000, scores.size)
    labels = (rng.random(scores.size) < 0.01).astype(float)

    at = ActionTable.fit(scores, rails.tolist(), amounts, labels)
    for rail in (*bulk_names, "hot-rail"):
        fri, rev, dec = at.t_friction[rail], at.t_review[rail], at.t_decline[rail]
        assert fri <= rev <= dec, f"{rail}: ladder crossed ({fri}, {rev}, {dec})"
        # The cap must not have pushed friction above the ladder for the hot rail.
        assert fri <= at.global_t_review + 1e-12, (
            f"{rail}: friction threshold {fri} exceeds the global review threshold "
            f"{at.global_t_review} -- the cap escalated the rail instead of bounding it"
        )
    bd = at.assert_bands_distinct()
    assert not bd["any_collapsed"], f"ladder collapsed: {bd['collapsed']}"
    # And the hot rail must actually receive friction rather than only declines.
    hot = rails == "hot-rail"
    frictioned = ((scores[hot] >= at.t_friction["hot-rail"]) & (scores[hot] < at.t_review["hot-rail"]))
    assert frictioned.mean() > 0.0, "the high-scoring rail lost its friction band entirely"


def test_friction_report_records_the_band_correction():
    """The second friction pass must be auditable, not silent."""
    rng = np.random.default_rng(4)
    n = 5000
    scores = rng.random(n)
    rails = np.array(["upi-pay"] * n, dtype=object)
    at = ActionTable.fit(scores, rails.tolist(), rng.uniform(100, 9000, n),
                         (rng.random(n) < 0.02).astype(float))
    rep = at.friction_report
    assert "per_rail" in rep and "provisional_pass" in rep, rep.keys()
    pr = rep["per_rail"]["upi-pay"]
    for k in ("friction_cap", "share_at_or_above_review_excluded_from_cap",
              "target_tail_share", "realised_friction_band_share", "clamped_to_review"):
        assert k in pr, f"friction report is missing {k}"


def test_g0_is_total_on_partial_row():
    """G0 is the kill switch: it must never crash on a partial row. It completes from schema defaults."""
    g0 = G0Guards()
    # A near-empty row: G0 must still evaluate rather than KeyError.
    res = g0.evaluate(g0.prepare({"rail": "card-cnp-keyed", "message_kind": "authorisation"}))
    assert isinstance(res.refuse, bool)


def test_g0_refuses_cryptogram_on_keyed():
    g0 = G0Guards()
    row = {"rail": "card-cnp-keyed", "message_kind": "authorisation", "emv_cryptogram_present": True}
    res = g0.evaluate(g0.prepare(row))
    assert res.refuse
    assert "G0_CRYPTOGRAM_ON_KEYED" in res.reason_codes


def test_reason_codes_all_in_vocabulary():
    """Every reason code a guard emits must exist in the fixed vocabulary."""
    from gate.decision import reason_code_catalogue
    from gate.g0_guards import GUARDS

    cat = reason_code_catalogue()
    for g in GUARDS:
        assert g.reason_code in cat, f"guard {g.id} emits an unknown reason code {g.reason_code}"


def test_decision_score_not_rounded():
    """A real tiny score must not render as 0.0000 — it must survive serialisation unrounded."""
    from gate.decision import Decision

    d = Decision(event_id="E", persona="GATE-I", score=2.175e-12, action="approve",
                 band="approve", latency_ms=1.0)
    assert d.as_dict()["score"] == 2.175e-12
