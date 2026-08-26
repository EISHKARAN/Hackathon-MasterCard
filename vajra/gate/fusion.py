"""Fusion — rank-average plus isotonic calibration. DELIBERATELY DUMB.

WE REJECT A LEARNED MULTI-HEAD META-STACKER AS A DECIDED POSITION, not as an omission. With
simulator-derived fraud counts a learned stacker overfits, and a promotion gate judged against a
false-positive budget WE GENERATED OURSELVES is not a gate. If the rank-average underperforms a
stacker on our own data, we will say so and still ship the rank-average, because the number we
would be optimising is not trustworthy. The fallback below the rank-average is a fixed max-rule.

============================ THE TRAIN/SERVE SKEW BUG ==================================
This module's whole design is shaped by a bug that took four rounds to find in a previous build, so
it is worth stating precisely.

`fit()` computed a rank-average over the whole population. `combine()` computed a plain MEAN of raw
component scores. Those are two different axes: a component whose raw scores sit in [0, 1e-11] and
one whose raw scores sit in [0, 700] contribute utterly differently to a mean and identically to a
rank-average. A quarter of ordinary traffic landed in the isotonic calibrator's saturated top and
was actioned.

THE FIX, and it has two halves:
  1.  `combine()` ranks each component against a STORED ECDF of that component's TRAINING scores,
      so serving uses the same axis as fitting.
  2.  TIES ARE AVERAGED, `(left + right) / 2`. Using `side='right'` alone puts every tied row at the
      TOP of its tie — and with a mass point at zero (very common: most rows have no anomaly at
      all) that means every ordinary row ranks at the 99th percentile and gets flagged.

`tests/test_fusion_train_serve.py` asserts the two paths agree on the training data itself, which is
the only test that would have caught the original bug.
========================================================================================
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

#: The components fused, in a fixed order.
COMPONENTS: tuple[str, ...] = ("g1", "g2_conformal", "g2_density", "sketch", "gate_b")

#: Default weights. NOT equal, and the reason is a correctness argument rather than a tuning result.
#:
#: G1 IS THE ONLY SUPERVISED CHANNEL. G2's conformal p-value answers "is this unlike my calibration
#: set", the density channel answers "is this in a sparse region", and the sketch channel answers "is
#: this fan-out unusual" — none of them has ever seen a label. Giving them a combined majority of the
#: fused score means the RANKING is mostly decided by channels that do not know what fraud is, which
#: destroys top-of-ranking precision exactly where precision@k is measured.
#:
#: So G1 dominates the SCORE, and the unsupervised channels do their real work through the separate
#: ABSTENTION path (a low conformal p-value lifts an approve to friction regardless of score). That
#: keeps the "I do not recognise this" signal without letting it outvote the evidence.
#:
#: These weights are a DESIGN POSITION, not a fit. We did not tune them against a reported number —
#: tuning the fusion against recall on our own simulator is exactly the untrustworthy optimisation the
#: design refuses elsewhere. `reports/fusion_ablation_<view>.json`, written by
#: `make refit-fusion`, publishes ALL EIGHT arms including the equal-weight one so the choice is
#: visible rather than asserted.
DEFAULT_WEIGHTS: dict[str, float] = {
    "g1": 0.62,
    "g2_conformal": 0.10,
    "g2_density": 0.06,
    "sketch": 0.10,
    "gate_b": 0.12,
}


def _rankdata_average(x: np.ndarray) -> np.ndarray:
    """Average-tie ranks in [0, 1]. The reference implementation both paths must match."""
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    if n == 0:
        return x
    if n == 1:
        return np.array([0.5])
    uniq, inv, cnt = np.unique(x, return_inverse=True, return_counts=True)
    starts = np.concatenate(([0], np.cumsum(cnt)[:-1]))
    mean_rank = starts + (cnt - 1) / 2.0
    return mean_rank[inv] / (n - 1)


@dataclass
class IsotonicCalibrator:
    """Monotone probability calibration, fitted with pool-adjacent-violators.

    Applied AFTER any undersampling correction, per Dal Pozzolo et al. (2017): undersampling and
    class weights distort probabilities, and an uncalibrated score cannot be fed a cost matrix.
    """

    x_: np.ndarray = field(default_factory=lambda: np.zeros(0))
    y_: np.ndarray = field(default_factory=lambda: np.zeros(0))
    fitted: bool = False
    n_fit: int = 0
    fit_prevalence: float = 0.0

    def fit(self, scores: np.ndarray, labels: np.ndarray) -> "IsotonicCalibrator":
        s = np.asarray(scores, dtype=np.float64)
        y = np.asarray(labels, dtype=np.float64)
        keep = np.isfinite(s) & np.isfinite(y) & (y >= 0)
        s, y = s[keep], y[keep]
        if s.size < 20 or len(np.unique(y)) < 2:
            # Not enough signal to calibrate. Stay UNFITTED and act as the identity rather than
            # inventing a mapping: a fabricated calibration is worse than none, because the cost
            # matrix downstream would treat its output as a probability.
            self.fitted = False
            self.n_fit = int(s.size)
            return self
        order = np.argsort(s, kind="stable")
        s, y = s[order], y[order]
        # Pool-adjacent-violators on the sorted sequence.
        yy = y.copy()
        w = np.ones_like(yy)
        i = 0
        while i < yy.size - 1:
            if yy[i] <= yy[i + 1] + 1e-12:
                i += 1
                continue
            # Pool i and i+1, then walk back to restore monotonicity.
            total_w = w[i] + w[i + 1]
            pooled = (yy[i] * w[i] + yy[i + 1] * w[i + 1]) / total_w
            yy[i] = pooled
            w[i] = total_w
            yy = np.delete(yy, i + 1)
            w = np.delete(w, i + 1)
            s = np.delete(s, i + 1)
            i = max(i - 1, 0)
        self.x_ = s
        self.y_ = np.clip(yy, 0.0, 1.0)
        self.fitted = True
        self.n_fit = int(keep.sum())
        self.fit_prevalence = float(y.mean())
        return self

    def transform(self, scores: np.ndarray) -> np.ndarray:
        s = np.asarray(scores, dtype=np.float64)
        if not self.fitted or self.x_.size == 0:
            return np.clip(s, 0.0, 1.0)
        return np.clip(np.interp(s, self.x_, self.y_), 0.0, 1.0)

    def as_dict(self) -> dict[str, Any]:
        return {
            "fitted": self.fitted,
            "n_fit": self.n_fit,
            "fit_prevalence": self.fit_prevalence,
            "n_breakpoints": int(self.x_.size),
            "note": (
                "Applied AFTER the undersampling prior correction. An uncalibrated score cannot be "
                "fed a cost matrix, and an unfitted calibrator acts as the identity rather than "
                "inventing a mapping."
            ),
        }


@dataclass
class Fusion:
    """Rank-average over components, then isotonic calibration.

    `component_ecdf` is the stored training-score distribution per component. It is what makes
    serving use the same axis as fitting, and it is the fix for the train/serve skew described in
    the module docstring.
    """

    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    component_ecdf: dict[str, np.ndarray] = field(default_factory=dict, repr=False)
    calibrator: IsotonicCalibrator = field(default_factory=IsotonicCalibrator)
    #: Fallback mode, used when a component is absent at serve time.
    use_max_rule: bool = False
    n_fit_rows: int = 0
    #: Combine on the LOG-TAIL of each channel's rank rather than the rank itself.
    #:
    #: WHY THIS EXISTS. A weighted mean of ranks is SCALE-FREE, so a channel with weight w can
    #: reorder any two rows whose rank gap is smaller than w. The top-k rows of an n-row ranking span
    #: a rank gap of only k/n; at the full preset that is 641/2,672,910 = 2.4e-4, while `sketch`
    #: carries w=0.10. So a channel worth 0.10 can move a row ~267,000 rank positions, and the
    #: identity of the alert queue is decided by the channels with the least information rather than
    #: by G1's extremes -- precisely where precision@k and recall@FPR are measured.
    #:
    #: Each channel's (1 - rank) IS a one-sided empirical p-value against the stored ECDF, so
    #: summing w_c * -log(1 - r_c) is WEIGHTED FISHER COMBINATION: a fixed, parameter-free rule from
    #: 1932, not a learned stacker. It fits nothing, so it does not weaken the no-tuning position.
    #:
    #: NOT a free win, and the failure mode is specific: `_rank_against_training` clips to 1.0, so an
    #: entire saturated tie group receives the maximum tail bonus at once. A coarse channel whose top
    #: tie holds thousands of rows can therefore still flood the queue. That is what `tail_eps`
    #: floors, and what `saturation_report()` measures before anyone trusts this.
    tail_transform: bool = False
    #: Floor on the tail p-value. NOT 1/n: at n~990k that gives a saturated tie group a bonus worth
    #: ~0.89 of G1's entire rank range, which reintroduces the very pathology this is fixing.
    tail_eps: float = 1e-3

    # ---- fitting ---------------------------------------------------------------------
    def fit(
        self,
        components: Mapping[str, np.ndarray],
        labels: np.ndarray | None = None,
    ) -> "Fusion":
        """Store each component's training ECDF, then fit the calibrator on the fused rank score."""
        present = [c for c in COMPONENTS if c in components]
        if not present:
            raise ValueError(f"no known components supplied; expected some of {COMPONENTS}")
        n = len(np.asarray(components[present[0]]))
        for c in present:
            arr = np.asarray(components[c], dtype=np.float64)
            if arr.size != n:
                raise ValueError(f"component {c!r} has {arr.size} rows, expected {n}")
            self.component_ecdf[c] = np.sort(arr)
        self.n_fit_rows = int(n)

        fused = self._fuse_from_ranks({c: _rankdata_average(np.asarray(components[c])) for c in present})
        if labels is not None:
            self.calibrator.fit(fused, np.asarray(labels))
        return self

    # ---- serving ---------------------------------------------------------------------
    def _rank_against_training(self, name: str, values: np.ndarray) -> np.ndarray:
        """Rank values against the STORED training ECDF, with ties averaged.

        `(left + right) / 2` reproduces fit-time average-tie ranking. `side='right'` alone would put
        every tied row at the TOP of its tie, and with a mass point at zero that flags all ordinary
        traffic — the exact bug this function exists to avoid.
        """
        ref = self.component_ecdf.get(name)
        v = np.asarray(values, dtype=np.float64)
        if ref is None or ref.size <= 1:
            return _rankdata_average(v)
        # Reproduce `_rankdata_average` EXACTLY when `v` is the training data. For value x with `c`
        # copies starting at sorted position s: left=s, right=s+c, so (left+right-1)/2 = s+(c-1)/2,
        # which is the average tie rank, and dividing by (n-1) matches the fit-time normalisation.
        # An earlier version divided by n and used (left+right)/2, which disagreed by a normalisation
        # constant AND a half-rank — the exact train/serve skew the fusion is supposed to remove.
        left = np.searchsorted(ref, v, side="left").astype(np.float64)
        right = np.searchsorted(ref, v, side="right").astype(np.float64)
        mid = (left + right - 1.0) / 2.0
        return np.clip(mid / float(ref.size - 1), 0.0, 1.0)

    def _fuse_from_ranks(self, ranks: Mapping[str, np.ndarray]) -> np.ndarray:
        present = [c for c in COMPONENTS if c in ranks]
        if self.use_max_rule:
            stack = np.vstack([np.asarray(ranks[c], dtype=np.float64) for c in present])
            return np.max(stack, axis=0)
        total_w = sum(self.weights.get(c, 0.0) for c in present)
        if total_w <= 0:
            stack = np.vstack([np.asarray(ranks[c], dtype=np.float64) for c in present])
            return np.mean(stack, axis=0)
        acc = np.zeros(len(np.asarray(ranks[present[0]])), dtype=np.float64)
        for c in present:
            r = np.asarray(ranks[c], dtype=np.float64)
            if self.tail_transform:
                # -log of the one-sided p-value, floored at tail_eps. Monotone increasing in r, so
                # this reorders NOTHING within a channel; it only changes how much of the fused
                # budget a channel spends near its own extreme.
                eps = float(self.tail_eps)
                r = -np.log(np.clip(1.0 - r, eps, 1.0))
            acc += (self.weights.get(c, 0.0) / total_w) * r
        return acc

    def saturation_report(self, components: Mapping[str, np.ndarray] | None = None) -> dict[str, Any]:
        """How much mass sits at rank exactly 1.0, per channel.

        This is the number that decides whether `tail_transform` is safe. A channel whose top tie
        holds a non-trivial share of the population hands that whole tie the maximum tail bonus
        simultaneously, which floods the queue with a block far larger than k.
        """
        out: dict[str, Any] = {"tail_eps": float(self.tail_eps), "channels": {}}
        for c in COMPONENTS:
            ref = self.component_ecdf.get(c)
            if ref is None or ref.size == 0:
                continue
            src = np.asarray(components[c], dtype=np.float64) if components and c in components else ref
            r = self._rank_against_training(c, src)
            out["channels"][c] = {
                "n": int(r.size),
                "share_at_rank_1": float(np.mean(r >= 1.0 - 1e-12)),
                "n_distinct_ranks": int(np.unique(r).size),
                "max_tail_value": float(-np.log(max(self.tail_eps, 1e-300))),
            }
        return out

    def combine(self, components: Mapping[str, np.ndarray]) -> np.ndarray:
        """Fuse at serve time. Uses the SAME axis as `fit` by construction."""
        ranks = {
            c: self._rank_against_training(c, np.asarray(components[c]))
            for c in COMPONENTS
            if c in components
        }
        if not ranks:
            raise ValueError(f"no known components supplied; expected some of {COMPONENTS}")
        return self._fuse_from_ranks(ranks)

    def score(self, components: Mapping[str, np.ndarray]) -> np.ndarray:
        """Fuse and calibrate. THIS is the number the action table is fitted and applied on."""
        return self.calibrator.transform(self.combine(components))

    def component_contributions(self, components: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
        """Per-component rank contribution, for the decision trace and the distinctness test."""
        present = [c for c in COMPONENTS if c in components]
        total_w = sum(self.weights.get(c, 0.0) for c in present) or 1.0
        return {
            c: (self.weights.get(c, 0.0) / total_w)
            * self._rank_against_training(c, np.asarray(components[c]))
            for c in present
        }

    def diagnostics(self) -> dict[str, Any]:
        return {
            "weights": dict(self.weights),
            "components_with_ecdf": sorted(self.component_ecdf),
            "n_fit_rows": self.n_fit_rows,
            "use_max_rule": self.use_max_rule,
            "tail_transform": self.tail_transform,
            "tail_eps": self.tail_eps,
            "combine_rule": (
                "weighted Fisher combination of one-sided empirical p-values (-log(1-rank))"
                if self.tail_transform else "weighted arithmetic mean of ECDF ranks"
            ),
            "calibrator": self.calibrator.as_dict(),
            "design_position": (
                "Rank-average plus isotonic, DELIBERATELY not a learned stacker. With "
                "simulator-derived fraud counts a stacker overfits, and a promotion gate judged "
                "against a false-positive budget we generated ourselves is not a gate."
            ),
        }

    # ---- persistence -----------------------------------------------------------------
    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        keys = sorted(self.component_ecdf)
        np.savez_compressed(
            directory / "fusion_ecdf.npz",
            **{f"c_{k}": self.component_ecdf[k] for k in keys},
            iso_x=self.calibrator.x_,
            iso_y=self.calibrator.y_,
        )
        (directory / "fusion_meta.json").write_text(
            json.dumps(
                {
                    "weights": self.weights,
                    "components": keys,
                    "use_max_rule": self.use_max_rule,
                    "tail_transform": self.tail_transform,
                    "tail_eps": self.tail_eps,
                    "n_fit_rows": self.n_fit_rows,
                    "calibrator": {
                        "fitted": self.calibrator.fitted,
                        "n_fit": self.calibrator.n_fit,
                        "fit_prevalence": self.calibrator.fit_prevalence,
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> "Fusion":
        meta = json.loads((directory / "fusion_meta.json").read_text(encoding="utf-8"))
        z = np.load(directory / "fusion_ecdf.npz")
        cal = IsotonicCalibrator(
            x_=z["iso_x"], y_=z["iso_y"],
            fitted=bool(meta["calibrator"]["fitted"]),
            n_fit=int(meta["calibrator"]["n_fit"]),
            fit_prevalence=float(meta["calibrator"]["fit_prevalence"]),
        )
        return cls(
            weights=dict(meta["weights"]),
            component_ecdf={k: z[f"c_{k}"] for k in meta["components"]},
            calibrator=cal,
            use_max_rule=bool(meta["use_max_rule"]),
            # `.get` with the rank-average default, so a bundle trained BEFORE the tail transform
            # existed loads with exactly the behaviour it was fitted under. Defaulting to True here
            # would silently reinterpret every stored bundle's axis.
            tail_transform=bool(meta.get("tail_transform", False)),
            tail_eps=float(meta.get("tail_eps", 1e-3)),
            n_fit_rows=int(meta["n_fit_rows"]),
        )
