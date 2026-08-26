"""G1 — the tabular scorer. LightGBM, with the PU-learning and calibration corrections.

WHY A GRADIENT-BOOSTED TREE ENSEMBLE AND NOT A DEEP TABULAR MODEL: argued from literature in
docs/RESEARCH.md section 1 (Grinsztajn et al. NeurIPS 2022; Shwartz-Ziv & Armon 2022; McElfresh et
al. NeurIPS 2023; Shmuel et al. 2024). Our regime is the corner where trees win — ~388
heterogeneous, individually meaningful features, irregular thresholds, and a positive count in the
low thousands. Two further reasons that are ours rather than the literature's: LightGBM exports to
a Treelite `.so`, which is what makes the inline latency story credible, and TreeSHAP gives exact
attributions in microseconds, which is what makes the fixed reason-code vocabulary derivable rather
than decorative.

FOUR THINGS THIS MODULE GETS RIGHT THAT ARE EASY TO GET WRONG:

1.  **Objective and metric.** `average_precision` for early stopping, not AUC. At a 0.1-0.5%
    positive rate, ROC-AUC is dominated by the true-negative mass and is near-1 for any competent
    model, so stopping on it stops on noise. PR-AUC degrades honestly.

2.  **The unlabelled window is UNLABELLED, not negative.** A recent event with no matured label is
    not a legitimate transaction; it is unknown. `nnPU` treats it as such, following Kiryo et al.
    (NeurIPS 2017) with the Elkan-Noto correction. Training it as a negative is the single most
    common way a fraud model's recall is silently inflated on paper and destroyed in production.

3.  **Undersampling shifts the posterior, and the shift must be undone.** Dal Pozzolo et al. (IEEE
    TNNLS 2017). If we undersample negatives we MUST re-derive the operating point AND refit the
    calibrator for the shifted prior; doing one without the other is worse than not undersampling.
    A previous build learned this the expensive way, so undersampling is OFF by default here and
    `prior_correction` is applied whenever it is on.

4.  **Determinism.** `num_threads=1` and a fixed feature order for the CI run, because
    multithreaded histogram construction is not bit-reproducible. The demo run may use all cores
    and says so.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


@dataclass
class G1Config:
    """Hyper-parameters. Chosen for a small-positive, high-heterogeneity regime."""

    num_leaves: int = 63
    max_depth: int = -1
    learning_rate: float = 0.05
    n_estimators: int = 600
    min_child_samples: int = 40
    subsample: float = 0.85
    subsample_freq: int = 1
    colsample_bytree: float = 0.7
    reg_lambda: float = 5.0
    reg_alpha: float = 0.5
    #: `is_unbalance` rescales the gradient rather than resampling, which keeps the training
    #: prevalence equal to the operating prevalence -- so the calibrator does not have to undo a
    #: prior shift. Preferred over undersampling for exactly that reason.
    is_unbalance: bool = True
    #: Deliberately OFF. See rule 3 in the module docstring.
    undersample_negatives: bool = False
    undersample_ratio: float = 0.0
    #: Cap on the number of UNLABELLED rows entered into the nnPU expansion.
    #:
    #: Each unlabelled row is entered TWICE (once weighted pi as positive, once weighted 1-pi as
    #: negative), so an uncapped expansion at the `full` preset would allocate a design matrix several
    #: times larger than the event stream and exhaust a 16 GB laptop. Subsampling the unlabelled set is
    #: statistically sound -- the nnPU risk estimator stays unbiased, it just has higher variance -- and
    #: the realised count is reported so the variance cost is visible rather than hidden.
    nnpu_max_unlabelled: int = 400_000
    early_stopping_rounds: int = 60
    #: Single-threaded for reproducibility in CI. The demo path may raise it and labels itself.
    num_threads: int = 1
    seed: int = 20260909
    #: Monotone constraints on features where the direction is not in question. Applied by NAME so
    #: a registry reorder cannot silently attach a constraint to the wrong column.
    monotone_features: tuple[tuple[str, int], ...] = (
        ("bin_issuer_prior_fraud_rate", 1),
        ("peer_cohort_prior_fraud_rate", 1),
        ("geo_cell_prior_fraud_rate", 1),
        ("incumbent_score", 1),
        ("field_combination_implausibility", 1),
        ("cryptogram_present_but_unverified", 1),
        ("refund_without_original_auth", 1),
        ("mandate_mcc_drift", 1),
        ("creditor_name_match_score", -1),
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            k: (list(v) if isinstance(v, tuple) else v)
            for k, v in self.__dict__.items()
        }


@dataclass
class G1Model:
    """A fitted G1. Holds the booster, the feature order, and the PU/prior corrections."""

    feature_names: tuple[str, ...]
    booster: Any                       # lightgbm.Booster
    config: G1Config
    #: Class prior used by the PU correction, and the training prevalence actually realised.
    pi_positive: float = 0.0
    train_prevalence: float = 0.0
    #: Prior-shift correction factor. 1.0 when no undersampling was applied.
    prior_correction: float = 1.0
    n_train_rows: int = 0
    n_train_positives: int = 0
    n_train_unlabelled: int = 0
    best_iteration: int = 0
    version: str = ""
    #: Feature importances, kept so the report can show what the model actually used.
    importance_gain: Mapping[str, float] = field(default_factory=dict)
    #: Parameters as RESOLVED at fit time, which can differ from the requested config: is_unbalance is
    #: disabled under PU weights, and num_leaves is capped by the positive count. Recorded so the
    #: report shows what ACTUALLY RAN rather than what was asked for.
    resolved_params: Mapping[str, Any] = field(default_factory=dict)

    # ---- prediction ------------------------------------------------------------------
    def predict_raw(self, X: np.ndarray) -> np.ndarray:
        """Raw model probability, BEFORE the prior correction and before fusion."""
        if X.shape[1] != len(self.feature_names):
            raise ValueError(
                f"G1 was fitted on {len(self.feature_names)} features and received "
                f"{X.shape[1]}. A feature-order or feature-count mismatch between train and serve "
                f"is a silent accuracy loss that no metric attributes correctly."
            )
        n_iter = self.best_iteration or None
        return np.asarray(self.booster.predict(X, num_iteration=n_iter), dtype=np.float64)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Probability with the undersampling prior correction applied.

        Dal Pozzolo et al. (2017): undersampling shifts the posterior by a known factor, and the
        correction is exact. When no undersampling was applied, `prior_correction == 1.0` and this
        is the identity.
        """
        p = self.predict_raw(X)
        if abs(self.prior_correction - 1.0) < 1e-12:
            return p
        beta = float(self.prior_correction)
        return p / (p + (1.0 - p) / max(beta, 1e-12))

    def shap_values(self, X: np.ndarray) -> np.ndarray:
        """Exact TreeSHAP contributions. Shape (n, n_features + 1); last column is the base value."""
        return np.asarray(
            self.booster.predict(X, pred_contrib=True, num_iteration=self.best_iteration or None),
            dtype=np.float64,
        )

    def top_attributions(self, X: np.ndarray, k: int = 5) -> list[dict[str, float]]:
        """Per-row top-k SHAP attributions by absolute contribution."""
        sv = self.shap_values(X)
        contrib = sv[:, :-1]
        out: list[dict[str, float]] = []
        for i in range(contrib.shape[0]):
            row = contrib[i]
            idx = np.argsort(-np.abs(row))[:k]
            out.append({self.feature_names[j]: float(row[j]) for j in idx})
        return out

    # ---- persistence -----------------------------------------------------------------
    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        model_path = directory / "g1_booster.txt"
        self.booster.save_model(str(model_path), num_iteration=self.best_iteration or None)
        meta = {
            "feature_names": list(self.feature_names),
            "config": self.config.as_dict(),
            "pi_positive": self.pi_positive,
            "train_prevalence": self.train_prevalence,
            "prior_correction": self.prior_correction,
            "n_train_rows": self.n_train_rows,
            "n_train_positives": self.n_train_positives,
            "n_train_unlabelled": self.n_train_unlabelled,
            "best_iteration": self.best_iteration,
            "version": self.version,
            "importance_gain": dict(self.importance_gain),
            "resolved_params": dict(self.resolved_params),
        }
        (directory / "g1_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        return model_path

    @classmethod
    def load(cls, directory: Path) -> "G1Model":
        import lightgbm as lgb

        meta = json.loads((directory / "g1_meta.json").read_text(encoding="utf-8"))
        booster = lgb.Booster(model_file=str(directory / "g1_booster.txt"))
        cfg = G1Config(**{
            k: (tuple(tuple(x) for x in v) if k == "monotone_features" else v)
            for k, v in meta["config"].items()
        })
        return cls(
            feature_names=tuple(meta["feature_names"]),
            booster=booster,
            config=cfg,
            pi_positive=float(meta["pi_positive"]),
            train_prevalence=float(meta["train_prevalence"]),
            prior_correction=float(meta["prior_correction"]),
            n_train_rows=int(meta["n_train_rows"]),
            n_train_positives=int(meta["n_train_positives"]),
            n_train_unlabelled=int(meta["n_train_unlabelled"]),
            best_iteration=int(meta["best_iteration"]),
            version=str(meta["version"]),
            importance_gain=dict(meta.get("importance_gain") or {}),
            resolved_params=dict(meta.get("resolved_params") or {}),
        )


# =======================================================================================
# Positive-unlabelled handling
# =======================================================================================

def nnpu_sample_weights(
    y: np.ndarray,
    *,
    pi_positive: float,
    unlabelled_value: int = -1,
) -> tuple[np.ndarray, np.ndarray]:
    """Turn (positive / unlabelled / negative) labels into (binary y, sample weights).

    THE PROBLEM. In the recent window a fraudulent event may have no matured label yet. Treating
    "no label" as "legitimate" is a systematic mislabelling concentrated exactly where the model is
    most needed, and it inflates apparent precision.

    THE CORRECTION (Elkan & Noto 2008; Kiryo et al. 2017, non-negative risk). Each unlabelled row
    is entered TWICE:
      * once as a positive with weight `pi`,
      * once as a negative with weight `1 - pi`,
    which is the expectation of its true label under the class prior. The non-negative part of nnPU
    is the clamp at zero, applied here by construction: weights are non-negative, so the empirical
    risk cannot go negative and the estimator cannot diverge with a flexible model.

    NON-SCAR, STATED. Both estimators are usually presented under SCAR. Our labelling is not SCAR
    — the never-labelled synthetic-identity cohort makes label absence class-conditional. We
    exercise them in their FAVOURABLE case (pi known from the simulator, positivity held by the
    epsilon-randomised incumbent) and report sensitivity to pi off by +-2x. This is a limitation we
    state, not one we have removed.

    Returns `(y_binary, weights)` over an EXPANDED row set; the caller must expand X to match using
    `nnpu_expand_index`.
    """
    y = np.asarray(y)
    pi = float(np.clip(pi_positive, 1e-6, 0.5))
    pos = y == 1
    neg = y == 0
    unl = y == unlabelled_value

    y_out = np.concatenate([np.ones(pos.sum()), np.zeros(neg.sum()), np.ones(unl.sum()), np.zeros(unl.sum())])
    w_out = np.concatenate([
        np.ones(pos.sum()),
        np.ones(neg.sum()),
        np.full(unl.sum(), pi),
        np.full(unl.sum(), 1.0 - pi),
    ])
    return y_out.astype(np.int8), w_out.astype(np.float64)


def nnpu_expand_index(y: np.ndarray, unlabelled_value: int = -1) -> np.ndarray:
    """Row indices that expand X to match `nnpu_sample_weights`' output ordering."""
    y = np.asarray(y)
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    unl = np.flatnonzero(y == unlabelled_value)
    return np.concatenate([pos, neg, unl, unl])


def ipw_reject_inference_weights(
    accept_probability: np.ndarray,
    *,
    was_declined: np.ndarray,
    clip_min: float = 0.05,
    clip_max: float = 20.0,
) -> tuple[np.ndarray, dict[str, float]]:
    """Inverse-propensity weights correcting for approval-conditioning.

    Declined events have NO OUTCOME AT ALL, ever. The training population is therefore
    approval-conditioned, and the correction is to weight each APPROVED row by 1 / P(accept) so it
    stands in for the declined rows it was selected over.

    THE WEIGHTS ARE CLIPPED, and the clipping is reported rather than hidden. An unclipped IPW
    estimator has unbounded variance wherever the propensity is small, and a handful of rows with
    weight 400 would dominate the fit. The share of clipped rows is the honest measure of how thin
    the overlap is; `reports/propensity_histogram.json` shows the same thing visually.
    """
    p = np.asarray(accept_probability, dtype=np.float64)
    declined = np.asarray(was_declined, dtype=bool)
    raw = np.ones_like(p)
    valid = (~declined) & (p > 0.0) & (p <= 1.0)
    raw[valid] = 1.0 / p[valid]
    clipped = np.clip(raw, clip_min, clip_max)
    n_clipped = int(((raw < clip_min) | (raw > clip_max)).sum())
    return clipped, {
        "n_rows": float(p.size),
        "n_declined_excluded": float(declined.sum()),
        "n_weights_clipped": float(n_clipped),
        "share_clipped": float(n_clipped / max(1, p.size)),
        "mean_weight": float(clipped[valid].mean()) if valid.any() else 0.0,
        "max_weight": float(clipped.max()),
    }


# =======================================================================================
# Fitting
# =======================================================================================

def fit_g1(
    X_train: np.ndarray,
    y_train: np.ndarray,
    feature_names: Sequence[str],
    *,
    X_valid: np.ndarray | None = None,
    y_valid: np.ndarray | None = None,
    sample_weight: np.ndarray | None = None,
    config: G1Config | None = None,
    pi_positive: float | None = None,
    use_nnpu: bool = True,
    version: str = "",
) -> G1Model:
    """Fit G1. `y` uses 1 = fraud, 0 = legitimate, -1 = UNLABELLED (not negative)."""
    import lightgbm as lgb

    cfg = config or G1Config()
    names = list(feature_names)
    if X_train.shape[1] != len(names):
        raise ValueError(f"X has {X_train.shape[1]} columns but {len(names)} names were given")

    y = np.asarray(y_train)
    n_unl = int((y == -1).sum())
    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())
    labelled = n_pos + n_neg
    prevalence = (n_pos / labelled) if labelled else 0.0
    pi = float(pi_positive if pi_positive is not None else max(prevalence, 1e-4))

    n_unl_used = n_unl
    if use_nnpu and n_unl > 0:
        y_work = y
        if cfg.nnpu_max_unlabelled and n_unl > cfg.nnpu_max_unlabelled:
            # Subsample the unlabelled set. Deterministic, and the dropped rows become plain
            # "ignore" rather than being relabelled -- relabelling them as negative would reintroduce
            # exactly the bias nnPU exists to remove.
            rng_pu = np.random.default_rng(cfg.seed + 7)
            unl_idx = np.flatnonzero(y == -1)
            keep = rng_pu.choice(unl_idx, size=cfg.nnpu_max_unlabelled, replace=False)
            y_work = y.copy()
            drop = np.setdiff1d(unl_idx, keep, assume_unique=False)
            y_work[drop] = -2                      # -2 == excluded entirely, neither P nor U
            n_unl_used = int(cfg.nnpu_max_unlabelled)
        idx = nnpu_expand_index(y_work)
        y_fit, w_pu = nnpu_sample_weights(y_work, pi_positive=pi)
        X_fit = X_train[idx]
        w_fit = w_pu if sample_weight is None else w_pu * np.asarray(sample_weight)[idx]
    else:
        keep = y != -1
        X_fit = X_train[keep]
        y_fit = y[keep].astype(np.int8)
        w_fit = None if sample_weight is None else np.asarray(sample_weight)[keep]

    prior_correction = 1.0
    if cfg.undersample_negatives and cfg.undersample_ratio > 0:
        rng = np.random.default_rng(cfg.seed)
        pos_idx = np.flatnonzero(y_fit == 1)
        neg_idx = np.flatnonzero(y_fit == 0)
        target_neg = int(min(neg_idx.size, max(1, pos_idx.size / cfg.undersample_ratio)))
        keep_neg = rng.choice(neg_idx, size=target_neg, replace=False)
        sel = np.concatenate([pos_idx, keep_neg])
        sel.sort()
        # THE PRIOR SHIFT. beta = kept negatives / all negatives. The correction in
        # G1Model.predict undoes exactly this, and the calibrator downstream is refitted on the
        # corrected scores. Doing one without the other is worse than not undersampling.
        prior_correction = float(target_neg / max(1, neg_idx.size))
        X_fit, y_fit = X_fit[sel], y_fit[sel]
        if w_fit is not None:
            w_fit = w_fit[sel]

    monotone = _monotone_vector(names, cfg.monotone_features)

    # THE DOUBLE-CORRECTION TRAP. nnPU sample weights ALREADY encode the class prior: each unlabelled
    # row enters as pi positive plus (1-pi) negative. Layering `is_unbalance` on top rescales the
    # positive gradient by the class ratio a SECOND time, which over-predicts and flattens the top of
    # the ranking — precisely where precision@k is measured. So `is_unbalance` is disabled whenever the
    # PU weights are in play, and the resolved value is recorded in the report.
    pu_weights_in_play = bool(use_nnpu and n_unl > 0)
    is_unbalance_effective = bool(
        cfg.is_unbalance and not cfg.undersample_negatives and not pu_weights_in_play
    )

    # SMALL-POSITIVE GUARD. With a few hundred positives, 63 leaves memorise noise: a leaf can isolate
    # single rows and the model's confident tail becomes arbitrary. Cap the capacity by the positive
    # count rather than by a fixed number, so the same config works at smoke and at full scale.
    effective_leaves = int(cfg.num_leaves)
    if n_pos > 0:
        effective_leaves = int(max(7, min(cfg.num_leaves, max(7, n_pos // 2))))

    params = {
        "objective": "binary",
        "metric": ["average_precision", "auc"],
        "num_leaves": effective_leaves,
        "max_depth": cfg.max_depth,
        "learning_rate": cfg.learning_rate,
        "min_child_samples": cfg.min_child_samples,
        "bagging_fraction": cfg.subsample,
        "bagging_freq": cfg.subsample_freq,
        "feature_fraction": cfg.colsample_bytree,
        "lambda_l2": cfg.reg_lambda,
        "lambda_l1": cfg.reg_alpha,
        "is_unbalance": is_unbalance_effective,
        "num_threads": cfg.num_threads,
        "seed": cfg.seed,
        "deterministic": True,
        "force_row_wise": True,
        "verbosity": -1,
        "monotone_constraints": monotone,
        "monotone_constraints_method": "advanced",
    }

    train_set = lgb.Dataset(X_fit, label=y_fit, weight=w_fit, feature_name=names, free_raw_data=False)
    valid_sets = [train_set]
    valid_names = ["train"]
    callbacks = [lgb.log_evaluation(period=0)]
    if X_valid is not None and y_valid is not None:
        vy = np.asarray(y_valid)
        vkeep = vy != -1
        if vkeep.sum() > 0 and len(np.unique(vy[vkeep])) > 1:
            valid_sets.append(
                lgb.Dataset(X_valid[vkeep], label=vy[vkeep].astype(np.int8),
                            feature_name=names, reference=train_set, free_raw_data=False)
            )
            valid_names.append("valid")
            # Early stopping on AVERAGE PRECISION, not AUC: at this base rate ROC-AUC is dominated
            # by the true-negative mass and stopping on it stops on noise.
            callbacks.append(
                lgb.early_stopping(cfg.early_stopping_rounds, first_metric_only=True, verbose=False)
            )

    booster = lgb.train(
        params,
        train_set,
        num_boost_round=cfg.n_estimators,
        valid_sets=valid_sets,
        valid_names=valid_names,
        callbacks=callbacks,
    )

    resolved = {
        "is_unbalance_effective": is_unbalance_effective,
        "pu_weights_in_play": pu_weights_in_play,
        "num_leaves_requested": int(cfg.num_leaves),
        "num_leaves_effective": effective_leaves,
        "n_unlabelled_available": int(n_unl),
        "n_unlabelled_used_in_pu_expansion": int(n_unl_used),
        "nnpu_subsampled": bool(n_unl_used < n_unl),
    }
    gains = booster.feature_importance(importance_type="gain")
    importance = {names[i]: float(gains[i]) for i in range(len(names)) if gains[i] > 0}

    return G1Model(
        feature_names=tuple(names),
        booster=booster,
        config=cfg,
        pi_positive=pi,
        train_prevalence=prevalence,
        prior_correction=prior_correction,
        n_train_rows=int(X_fit.shape[0]),
        n_train_positives=n_pos,
        n_train_unlabelled=n_unl,
        best_iteration=int(booster.best_iteration or 0),
        version=version,
        importance_gain=dict(sorted(importance.items(), key=lambda kv: -kv[1])),
        resolved_params=resolved,
    )


def _monotone_vector(names: Sequence[str], constraints: Sequence[tuple[str, int]]) -> list[int]:
    """Build LightGBM's monotone-constraint vector BY FEATURE NAME.

    By name rather than by position, because a registry reorder would otherwise silently attach a
    "must increase risk" constraint to an unrelated column — a bug that degrades the model quietly
    and looks like bad luck.
    """
    lookup = {n: 0 for n in names}
    for name, direction in constraints:
        if name in lookup:
            lookup[name] = int(direction)
    return [lookup[n] for n in names]
