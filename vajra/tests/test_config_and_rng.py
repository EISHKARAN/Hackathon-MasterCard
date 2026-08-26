"""Core invariants: RNG stream independence, config derivations, no hard-coded scale literals."""
from __future__ import annotations
import re
from pathlib import Path
import pytest
from core.config import load_config
from core.rng import derive_seed, stream, family_stream


def test_rng_streams_independent_of_order():
    """A named stream's draws are a function of its NAME, not of what ran before it."""
    a1 = stream("sim.graph").random(5)
    _burn = stream("attack.bandit").random(1000)  # consume a different stream
    a2 = stream("sim.graph").random(5)
    assert (a1 == a2).all(), "sim.graph draws changed because another stream was consumed first"


def test_family_streams_distinct():
    seeds = {f"ATK-{i}": derive_seed(f"attack.family.ATK-{i}") for i in range(60)}
    assert len(set(seeds.values())) == len(seeds), "family streams collided"


def test_undeclared_stream_raises():
    with pytest.raises(KeyError):
        stream("totally.undeclared.stream")


def test_alert_budget_is_derived():
    """0.024% must be DERIVED from staffing, never a literal, so editing staffing moves it."""
    cfg = load_config()
    q = cfg.ops["review_queue"]
    expected = q["analysts"] * q["cases_per_analyst_per_shift"] * q["shifts_per_day"]
    assert cfg.alert_budget_per_day == expected
    assert abs(cfg.alert_budget_share - expected / cfg.reference_volume_per_day) < 1e-12


def test_rail_mix_normalised():
    cfg = load_config()
    assert abs(sum(cfg.rail_mix.values()) - 1.0) < 1e-6


def test_no_hardcoded_reference_volume_literal():
    """The 10M reference portfolio must live in config, not as a literal in the pipeline."""
    root = Path(__file__).resolve().parent.parent
    offenders = []
    for p in root.rglob("*.py"):
        if any(part in {".venv", "tests", ".git"} for part in p.parts):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        # 10_000_000 or 10000000 as a literal outside config.py is a smell.
        if re.search(r"\b10_?000_?000\b", text) and p.name != "config.py":
            offenders.append(str(p.relative_to(root)))
    assert not offenders, f"hard-coded 10M reference volume in: {offenders}"
