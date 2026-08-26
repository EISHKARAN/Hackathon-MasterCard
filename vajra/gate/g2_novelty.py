"""G2 — abstention and novelty: Mondrian conformal p-values plus an ECOD density channel.

G2 ANSWERS A DIFFERENT QUESTION FROM G1. Not "how fraudulent does this look" but "how UNLIKE
ANYTHING IN MY CALIBRATION SET is this". A novel composition may score mid-band on G1 while sitting
far outside the conformal support, and the correct action there is friction, not a decision. A low
conformal p-value routes to escalation, NEVER to a silent approval.

============================== THREE HONEST ADMISSIONS ==================================

1.  **Exchangeability is violated and we measure coverage rather than assuming it.** Conformal
    validity rests on exchangeability, and time-forward payment data is not exchangeable (Barber,
    Candès, Ramdas & Tibshirani, Annals of Statistics 2023). So we publish EMPIRICAL coverage
    against nominal, per stratum, instead of quoting the nominal guarantee.

2.  **Thin strata are merged, and which ones merged is published.** Mondrian CP conditions on
    channel x MCC band x region. Some strata will have too few calibration points for a p-value to
    mean anything, so there is a minimum count and an explicit merge rule, and the merged strata are
    named in the report (Althani, MAKE 2026, on class-conditional CP under extreme imbalance).

3.  **ABSTENTION IS PRICED, NOT FREE.** The benign abstention rate per rail is reported next to
    every "caught" number. An abstention that fires on ordinary traffic is friction an issuer pays
    for, and a system that abstains on everything has caught nothing.

========================================================================================

THE ECOD UNIT TRAP, recorded because it silently destroyed a previous build. The raw ECOD score is
a SUM of per-feature negative-log tail probabilities across ~388 features, so its natural range is
in the hundreds — it is NOT a z-score. Comparing it against a threshold of 3.0 flags every row, G2
escalates 100% of traffic, and every event abstains, which reads as "the model declines nothing and
frictions everything". So `ECODDensity` calibrates its own score distribution at `fit()` and exposes
`score_z()`; if it is uncalibrated it escalates NOTHING rather than everything.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

#: Minimum calibration points for a Mondrian stratum to be used on its own.
MIN_STRATUM_CALIBRATION = 200

#: The merge target when a stratum is too thin: fall back to the channel-only stratum, then global.
MERGE_LADDER: tuple[str, ...] = ("full", "channel_mcc", "channel", "global")


# =======================================================================================
# ECOD — Empirical-Cumulative-distribution-based Outlier Detection
# =======================================================================================

@dataclass
class ECODDensity:
    """Parameter-free, deterministic, O(nd) unsupervised outlier score.

    Chosen over an autoencoder because it needs no training loop, has no reproducibility caveat,
    and has no hyper-parameters to tune against a number we do not trust.

    The score is `sum_j -log(tail_j(x_j))` over features, where `tail_j` is the empirical
    one-or-two-sided tail probability of feature j. That sum grows with dimensionality, which is
    exactly why the calibration below exists.
    """

    #: Sorted training values per feature, for the empirical CDF.
    _sorted: list[np.ndarray] = field(default_factory=list, repr=False)
    n_features: int = 0
    n_train: int = 0
    #: Calibrated moments of the RAW score, so `score_z` is a real z-score.
    raw_mean: float = 0.0
    raw_std: float = 0.0
    #: Empirical quantiles of the raw score, for `score_quantile`.
    _raw_quantiles: np.ndarray = field(default_factory=lambda: np.zeros(0), repr=False)
    calibrated: bool = False

    def fit(self, X: np.ndarray) -> "ECODDensity":
        X = np.asarray(X, dtype=np.float64)
        self.n_train, self.n_features = X.shape
        self._sorted = [np.sort(X[:, j]) for j in range(self.n_features)]
        raw = self._raw_score(X)
        self.raw_mean = float(raw.mean())
        self.raw_std = float(raw.std())
        self._raw_quantiles = np.quantile(raw, np.linspace(0.0, 1.0, 1001))
        # A degenerate spread means every row scores identically and a z-score is undefined. Say so
        # by staying UNCALIBRATED rather than dividing by ~0 and producing garbage.
        self.calibrated = bool(self.n_train >= 50 and self.raw_std > 1e-9)
        return self

    def _raw_score(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=np.float64)
        if X.shape[1] != self.n_features:
            raise ValueError(f"ECOD fitted on {self.n_features} features, got {X.shape[1]}")
        n = X.shape[0]
        total = np.zeros(n, dtype=np.float64)
        eps = 1.0 / max(2.0 * self.n_train, 2.0)
        for j in range(self.n_features):
            s = self._sorted[j]
            if s.size == 0:
                continue
            left = np.searchsorted(s, X[:, j], side="right") / s.size      # F(x)
            right = 1.0 - np.searchsorted(s, X[:, j], side="left") / s.size  # 1 - F(x-)
            tail = np.minimum(np.maximum(np.minimum(left, right), eps), 1.0)
            total += -np.log(tail)
        return total

    def score_z(self, X: np.ndarray) -> np.ndarray:
        """Z-score of the raw ECOD score against its TRAINING distribution.

        Returns zeros when uncalibrated. That is the safe direction: an uncalibrated density
        channel that returned large values would escalate every row, which is precisely the failure
        this class exists to prevent.
        """
        raw = self._raw_score(X)
        if not self.calibrated:
            return np.zeros_like(raw)
        return (raw - self.raw_mean) / max(self.raw_std, 1e-9)

    def score_quantile(self, X: np.ndarray) -> np.ndarray:
        """Empirical quantile of the raw score in [0, 1]. 0.5 when uncalibrated."""
        raw = self._raw_score(X)
        if not self.calibrated or self._raw_quantiles.size == 0:
            return np.full_like(raw, 0.5)
        idx = np.searchsorted(self._raw_quantiles, raw, side="left")
        return np.clip(idx / (self._raw_quantiles.size - 1), 0.0, 1.0)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "n_train": self.n_train,
            "n_features": self.n_features,
            "raw_mean": self.raw_mean,
            "raw_std": self.raw_std,
            "calibrated": self.calibrated,
            "unit_note": (
                "The RAW score is a SUM of per-feature negative-log tail probabilities over "
                f"{self.n_features} features, so its natural scale is ~{self.raw_mean:.0f}, NOT a "
                "z-score. Comparing the raw score against a z-threshold flags every row. Use "
                "score_z() or score_quantile()."
            ),
        }

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "g2_ecod.npz",
            **{f"f{j}": self._sorted[j] for j in range(self.n_features)},
            raw_quantiles=self._raw_quantiles,
        )
        (directory / "g2_ecod_meta.json").write_text(
            json.dumps(
                {
                    "n_features": self.n_features,
                    "n_train": self.n_train,
                    "raw_mean": self.raw_mean,
                    "raw_std": self.raw_std,
                    "calibrated": self.calibrated,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> "ECODDensity":
        meta = json.loads((directory / "g2_ecod_meta.json").read_text(encoding="utf-8"))
        z = np.load(directory / "g2_ecod.npz")
        obj = cls(
            _sorted=[z[f"f{j}"] for j in range(int(meta["n_features"]))],
            n_features=int(meta["n_features"]),
            n_train=int(meta["n_train"]),
            raw_mean=float(meta["raw_mean"]),
            raw_std=float(meta["raw_std"]),
            _raw_quantiles=z["raw_quantiles"],
            calibrated=bool(meta["calibrated"]),
        )
        return obj


# =======================================================================================
# Mondrian conformal prediction
# =======================================================================================

def mondrian_stratum(rail: str, mcc: str, geo_cell: str, *, level: str = "full") -> str:
    """The conditioning stratum: channel x MCC band x region, with coarser fallbacks.

    MCC is BANDED rather than used raw: a per-MCC stratum over thirty MCCs times twelve rails times
    hundreds of geo cells would make every stratum thin, and a thin stratum's p-value is noise.
    """
    band = _mcc_band(mcc)
    region = (geo_cell or "")[:4]
    if level == "full":
        return f"{rail}|{band}|{region}"
    if level == "channel_mcc":
        return f"{rail}|{band}|*"
    if level == "channel":
        return f"{rail}|*|*"
    return "*|*|*"


def _mcc_band(mcc: str) -> str:
    """Coarse MCC bands. Business-meaningful, not learned, so the stratum cannot drift."""
    m = str(mcc or "")
    if m in ("6011", "6051", "6540", "4814"):
        return "quasi_cash"
    if m.startswith("54") or m.startswith("58"):
        return "grocery_dining"
    if m.startswith("41") or m.startswith("47") or m.startswith("70"):
        return "travel"
    if m.startswith("59") or m.startswith("57") or m.startswith("53"):
        return "retail"
    if m.startswith("80") or m.startswith("82"):
        return "health_education"
    if m == "":
        return "none"
    return "other"


@dataclass
class MondrianConformal:
    """Split-conformal p-values, conditioned per stratum, with an explicit merge rule."""

    #: stratum -> sorted nonconformity scores from the calibration set.
    calibration: dict[str, np.ndarray] = field(default_factory=dict, repr=False)
    #: stratum -> the stratum actually used after merging (may be a coarser level).
    merge_map: dict[str, str] = field(default_factory=dict)
    min_calibration: int = MIN_STRATUM_CALIBRATION
    n_calibration_rows: int = 0
    #: Recorded so the report can say which strata were too thin to stand alone.
    thin_strata: tuple[str, ...] = ()

    def fit(
        self,
        nonconformity: np.ndarray,
        rails: Sequence[str],
        mccs: Sequence[str],
        geos: Sequence[str],
    ) -> "MondrianConformal":
        """Fit on a BENIGN, TIME-FORWARD calibration slice, excluding holdout-family rows.

        The calibration set is a leakage surface: fitted over a pool containing sealed rows it would
        import holdout information into every p-value. `eval/leakage/statistic_fit.py` asserts the
        exclusion; this method assumes the caller has already applied it and records the row count
        so the assertion has something to check.
        """
        nc = np.asarray(nonconformity, dtype=np.float64)
        self.n_calibration_rows = int(nc.size)
        buckets: dict[str, list[float]] = {}
        for level in MERGE_LADDER:
            for i in range(nc.size):
                s = mondrian_stratum(rails[i], mccs[i], geos[i], level=level)
                buckets.setdefault(s, []).append(float(nc[i]))
        self.calibration = {k: np.sort(np.asarray(v)) for k, v in buckets.items()}

        # Build the merge map over the FULL-level strata only.
        thin: list[str] = []
        full_strata = {
            mondrian_stratum(rails[i], mccs[i], geos[i], level="full") for i in range(nc.size)
        }
        for s in sorted(full_strata):
            chosen = s
            if self.calibration.get(s, np.zeros(0)).size < self.min_calibration:
                thin.append(s)
                rail, band, _region = s.split("|")
                for level, cand in (
                    ("channel_mcc", f"{rail}|{band}|*"),
                    ("channel", f"{rail}|*|*"),
                    ("global", "*|*|*"),
                ):
                    if self.calibration.get(cand, np.zeros(0)).size >= self.min_calibration:
                        chosen = cand
                        break
                else:
                    chosen = "*|*|*"
            self.merge_map[s] = chosen
        self.thin_strata = tuple(thin)
        return self

    def p_values(
        self,
        nonconformity: np.ndarray,
        rails: Sequence[str],
        mccs: Sequence[str],
        geos: Sequence[str],
    ) -> tuple[np.ndarray, list[str]]:
        """Conformal p-value per row, and the stratum each was computed in.

        `p = (1 + #{calib >= score}) / (1 + n_calib)`, the standard split-conformal form. A LOW p
        means "unlike anything in my calibration set", which is a NOVELTY statement, not a fraud
        probability — and the distinction is why a low p routes to escalation rather than to a
        decline.
        """
        nc = np.asarray(nonconformity, dtype=np.float64)
        out = np.ones(nc.size, dtype=np.float64)
        used: list[str] = []
        for i in range(nc.size):
            s = mondrian_stratum(rails[i], mccs[i], geos[i], level="full")
            target = self.merge_map.get(s)
            if target is None:
                # Unseen stratum at serve time: fall back down the ladder rather than inventing a
                # p-value from an empty calibration set.
                rail, band, _r = s.split("|")
                for cand in (f"{rail}|{band}|*", f"{rail}|*|*", "*|*|*"):
                    if self.calibration.get(cand, np.zeros(0)).size >= self.min_calibration:
                        target = cand
                        break
                target = target or "*|*|*"
            calib = self.calibration.get(target, np.zeros(0))
            used.append(target)
            if calib.size == 0:
                out[i] = 1.0        # no basis for a novelty claim -> not novel
                continue
            # #{calib >= score}
            ge = calib.size - int(np.searchsorted(calib, nc[i], side="left"))
            out[i] = (1.0 + ge) / (1.0 + calib.size)
        return out, used

    def empirical_coverage(
        self,
        nonconformity: np.ndarray,
        rails: Sequence[str],
        mccs: Sequence[str],
        geos: Sequence[str],
        alpha: float = 0.05,
    ) -> dict[str, Any]:
        """MEASURED coverage against nominal `1 - alpha`, overall and per stratum.

        This is the honest replacement for quoting the nominal guarantee. Time-forward payment data
        violates exchangeability, so the nominal guarantee does not hold, and a number that does not
        hold should be measured rather than asserted.
        """
        p, used = self.p_values(nonconformity, rails, mccs, geos)
        covered = p > alpha
        per: dict[str, dict[str, float]] = {}
        for s in sorted(set(used)):
            m = np.asarray([u == s for u in used], dtype=bool)
            if m.sum() == 0:
                continue
            per[s] = {
                "n": float(m.sum()),
                "empirical_coverage": float(covered[m].mean()),
                "nominal_coverage": float(1.0 - alpha),
                "gap": float(covered[m].mean() - (1.0 - alpha)),
            }
        return {
            "alpha": alpha,
            "nominal_coverage": 1.0 - alpha,
            "empirical_coverage_overall": float(covered.mean()) if covered.size else 0.0,
            "per_stratum": per,
            "n_strata_used": len(per),
            "n_thin_strata_merged": len(self.thin_strata),
            "thin_strata_sample": list(self.thin_strata[:20]),
            "min_calibration_per_stratum": self.min_calibration,
            "exchangeability_note": (
                "Time-forward payment data VIOLATES exchangeability (Barber, Candes, Ramdas & "
                "Tibshirani, Annals of Statistics 2023), so the nominal conformal guarantee does "
                "not hold here. We therefore MEASURE coverage rather than assume it, and publish "
                "the gap per stratum."
            ),
        }

    def diagnostics(self) -> dict[str, Any]:
        sizes = {k: int(v.size) for k, v in self.calibration.items() if "|*|*" not in k}
        return {
            "n_calibration_rows": self.n_calibration_rows,
            "n_strata": len(sizes),
            "n_thin_strata": len(self.thin_strata),
            "min_calibration_per_stratum": self.min_calibration,
            "merge_ladder": list(MERGE_LADDER),
            "smallest_strata": dict(sorted(sizes.items(), key=lambda kv: kv[1])[:10]),
        }

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        keys = sorted(self.calibration)
        np.savez_compressed(
            directory / "g2_conformal.npz",
            **{f"s{i}": self.calibration[k] for i, k in enumerate(keys)},
        )
        (directory / "g2_conformal_meta.json").write_text(
            json.dumps(
                {
                    "strata": keys,
                    "merge_map": self.merge_map,
                    "min_calibration": self.min_calibration,
                    "n_calibration_rows": self.n_calibration_rows,
                    "thin_strata": list(self.thin_strata),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> "MondrianConformal":
        meta = json.loads((directory / "g2_conformal_meta.json").read_text(encoding="utf-8"))
        z = np.load(directory / "g2_conformal.npz")
        keys = list(meta["strata"])
        return cls(
            calibration={k: z[f"s{i}"] for i, k in enumerate(keys)},
            merge_map=dict(meta["merge_map"]),
            min_calibration=int(meta["min_calibration"]),
            n_calibration_rows=int(meta["n_calibration_rows"]),
            thin_strata=tuple(meta.get("thin_strata") or ()),
        )


def abstention_price(
    abstained: np.ndarray,
    is_attack: np.ndarray,
    rails: Sequence[str],
    cohort_tags: Sequence[str],
) -> dict[str, Any]:
    """PRICE THE ABSTENTION. The benign abstention rate per rail, and on the hard cohorts.

    An abstention that fires on ordinary traffic is friction the issuer pays for. Reporting a
    "caught" number without this alongside it would let a system that abstains on everything claim
    it caught everything.
    """
    ab = np.asarray(abstained, dtype=bool)
    atk = np.asarray(is_attack, dtype=bool)
    benign = ~atk
    rails_arr = np.asarray(rails, dtype=object).astype(str)
    tags = np.asarray(cohort_tags, dtype=object).astype(str)

    per_rail: dict[str, float] = {}
    for r in sorted(set(rails_arr.tolist())):
        m = benign & (rails_arr == r)
        if m.sum():
            per_rail[r] = float(ab[m].mean())

    hb12 = benign & np.char.startswith(tags, "hb12_")
    hbb = benign & np.char.startswith(tags, "hbb_")
    ordinary = benign & (tags == "ordinary")
    return {
        "benign_abstention_rate_overall": float(ab[benign].mean()) if benign.sum() else 0.0,
        "benign_abstention_rate_per_rail": per_rail,
        "benign_abstention_rate_ordinary": float(ab[ordinary].mean()) if ordinary.sum() else 0.0,
        "benign_abstention_rate_hard_benign_12": float(ab[hb12].mean()) if hb12.sum() else 0.0,
        "benign_abstention_rate_hard_benign_b": float(ab[hbb].mean()) if hbb.sum() else 0.0,
        "attack_abstention_rate": float(ab[atk].mean()) if atk.sum() else 0.0,
        "note": (
            "ABSTENTION IS PRICED, NOT FREE. These rates are reported next to every 'caught' "
            "number, because a system that abstains on everything has caught nothing."
        ),
    }
