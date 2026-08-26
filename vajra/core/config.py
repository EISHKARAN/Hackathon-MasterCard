"""Typed access to config/*.yaml.

Config is loaded once and frozen. Two rules this module enforces, both of which exist
because the design commits to them in writing:

*   **No magic numbers outside config/.** A number that reaches a report must be
    traceable to a yaml key a judge can edit, or be machine-counted at run time. The
    test `tests/test_no_hardcoded_scale.py` greps for the handful of literals we care
    most about (the 10M reference portfolio, the 2400-case alert budget, the 576 cell
    count) and fails if they appear as literals anywhere outside config/ and tests/.

*   **Derived quantities are derived, not restated.** `alert_budget_per_day` is
    computed from analysts x cases x shifts and asserted against the share printed in
    reports, so "0.024% of volume" can never drift from the staffing it came from.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml

from core.paths import paths


def _load_yaml(name: str) -> dict[str, Any]:
    with (paths.config / name).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"config/{name} must parse to a mapping, got {type(data)!r}")
    return data


@dataclass(frozen=True)
class Config:
    seed: dict[str, Any] = field(repr=False)
    ops: dict[str, Any] = field(repr=False)
    cost_matrix: dict[str, Any] = field(repr=False)
    scenario: dict[str, Any] = field(repr=False)

    # ---- scenario -------------------------------------------------------------
    @property
    def default_preset(self) -> str:
        return os.environ.get("VAJRA_PRESET") or self.scenario["default_preset"]

    def preset(self, name: str | None = None) -> dict[str, Any]:
        key = name or self.default_preset
        presets = self.scenario["presets"]
        if key not in presets:
            raise KeyError(
                f"unknown preset {key!r}; config/scenario.yaml declares {sorted(presets)}"
            )
        return dict(presets[key], name=key)

    @property
    def base_rate(self) -> float:
        override = os.environ.get("VAJRA_BASE_RATE")
        return float(override) if override else float(self.scenario["base_rate"]["target"])

    @property
    def tier_a_rails(self) -> list[str]:
        return list(self.scenario["tier_a_rails"])

    @property
    def tier_b_rails(self) -> list[str]:
        return list(self.scenario["tier_b_rails"])

    @property
    def all_rails(self) -> list[str]:
        return self.tier_a_rails + self.tier_b_rails

    @property
    def rail_mix(self) -> dict[str, float]:
        mix = dict(self.scenario["rail_mix"])
        total = sum(mix.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"config/scenario.yaml rail_mix must sum to 1.0, got {total:.6f}. "
                "The mix is a policy choice, but an unnormalised mix silently changes "
                "every per-rail denominator in the metrics table."
            )
        return mix

    # ---- ops ------------------------------------------------------------------
    @property
    def reference_volume_per_day(self) -> int:
        return int(self.ops["scale"]["reference_authorisations_per_day"])

    @property
    def alert_budget_per_day(self) -> int:
        q = self.ops["review_queue"]
        return int(q["analysts"]) * int(q["cases_per_analyst_per_shift"]) * int(q["shifts_per_day"])

    @property
    def alert_budget_share(self) -> float:
        """Alert budget as a share of the reference portfolio. DERIVED, never stated."""
        return self.alert_budget_per_day / self.reference_volume_per_day

    def friction_cap(self, rail: str) -> float:
        caps = self.ops["friction_caps"]
        return float(caps.get(rail, caps["_default"]))

    @property
    def analyst(self) -> dict[str, Any]:
        return dict(self.ops["analyst_model"])

    @property
    def label_latency(self) -> dict[str, Any]:
        return dict(self.ops["label_latency"])

    @property
    def incumbent(self) -> dict[str, Any]:
        return dict(self.ops["incumbent_policy"])

    @property
    def beneficiary_hold(self) -> dict[str, Any]:
        return dict(self.ops["beneficiary_hold"])

    # ---- costs ----------------------------------------------------------------
    @property
    def defender_costs(self) -> dict[str, Any]:
        return dict(self.cost_matrix["defender"])

    @property
    def attacker_costs(self) -> dict[str, Any]:
        return dict(self.cost_matrix["attacker"])

    def attacker_costs_scaled(self, mule_multiplier: float) -> dict[str, Any]:
        """Attacker constants with mule_burn scaled, for `make sensitivity`."""
        c = self.attacker_costs
        c["mule_burn"] = float(c["mule_burn"]) * float(mule_multiplier)
        c["_mule_multiplier"] = float(mule_multiplier)
        return c


@lru_cache(maxsize=1)
def load_config() -> Config:
    return Config(
        seed=_load_yaml("seed.yaml"),
        ops=_load_yaml("ops.yaml"),
        cost_matrix=_load_yaml("cost_matrix.yaml"),
        scenario=_load_yaml("scenario.yaml"),
    )
