"""The GATE scorer — one codebase, two personae.

INLINE: G0 guards -> G1 tree ensemble -> G2 conformal/density -> fusion -> action table.
NEAR-LINE (off the critical path): G3 GRU and G4 RGCN write entity risk back to the online store,
which the NEXT inline decision reads. That writeback is the only feedback edge inside GATE, and it
is deliberately not a feedback edge on the current decision — a near-line model on the critical path
is how latency claims become fictional.

TWO PERSONAE FROM THE SAME CODE:
  GATE-I  payer/issuer side. "Should this debit be authorised?"
  GATE-B  payee PSP / receiving bank. "Should this credit be trusted, and should this account keep
          the ability to move money onward?"

They do not vote on the same event. They act at different points in the same money path and compose
through two channels: FORWARD, GATE-B's beneficiary prior becomes a GATE-I feature (the only
mechanism by which GATE-I can act on coercion-class fraud at all); BACKWARD, GATE-I's decision and
reason codes are attached to the credit event GATE-B sees.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from core.config import Config, load_config
from features.builder import FeatureMatrix
from features.registry import load_registry
from gate.decision import Decision, freeze_recommendation
from gate.fusion import Fusion
from gate.g0_guards import G0Guards
from gate.g1_tabular import G1Model
from gate.g2_novelty import ECODDensity, MondrianConformal
from gate.gate_b import (
    BloomRiskExchange,
    OnboardingCohortScorer,
    decide_beneficiary_action,
    no_exchange_fallback,
)
from gate.policy import ActionTable, action_for
from gate.sketches import OnlineStore

#: Conformal p-value at or below which G2 abstains and escalates. NOT a fraud threshold: a low p
#: means "unlike anything in my calibration set", so the response is friction, never a silent
#: approval and never a decline on its own.
DEFAULT_CONFORMAL_ALPHA = 0.02

#: Density z-score above which the density channel contributes. Compared against `score_z()`, never
#: against the RAW ECOD score — see the unit trap in gate/g2_novelty.py.
DEFAULT_DENSITY_Z = 3.0


@dataclass
class GateBundle:
    """Everything a persona needs to score. Saved and loaded as a unit, so a partial load fails."""

    persona: str
    g1: G1Model | None
    conformal: MondrianConformal | None
    density: ECODDensity | None
    fusion: Fusion
    action_table: ActionTable
    onboarding: OnboardingCohortScorer | None = None
    exchange: BloomRiskExchange | None = None
    model_version: str = ""
    feature_names: tuple[str, ...] = ()
    #: The view this bundle was fitted for. The ablation trains one bundle per view.
    view: str = "issuer"
    #: Set when G3/G4 were unavailable, so the report says SKIPPED rather than implying they ran.
    nearline_status: Mapping[str, str] = field(default_factory=dict)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        if self.g1 is not None:
            self.g1.save(directory)
        if self.conformal is not None:
            self.conformal.save(directory)
        if self.density is not None:
            self.density.save(directory)
        self.fusion.save(directory)
        self.action_table.save(directory)
        if self.exchange is not None:
            self.exchange.save(directory)
        (directory / "bundle_meta.json").write_text(
            json.dumps(
                {
                    "persona": self.persona,
                    "model_version": self.model_version,
                    "view": self.view,
                    "feature_names": list(self.feature_names),
                    "has_g1": self.g1 is not None,
                    "has_conformal": self.conformal is not None,
                    "has_density": self.density is not None,
                    "has_exchange": self.exchange is not None,
                    "nearline_status": dict(self.nearline_status),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> "GateBundle":
        meta = json.loads((directory / "bundle_meta.json").read_text(encoding="utf-8"))
        return cls(
            persona=meta["persona"],
            g1=G1Model.load(directory) if meta.get("has_g1") else None,
            conformal=MondrianConformal.load(directory) if meta.get("has_conformal") else None,
            density=ECODDensity.load(directory) if meta.get("has_density") else None,
            fusion=Fusion.load(directory),
            action_table=ActionTable.load(directory),
            exchange=BloomRiskExchange.load(directory) if meta.get("has_exchange") else None,
            model_version=meta.get("model_version", ""),
            feature_names=tuple(meta.get("feature_names") or ()),
            view=meta.get("view", "issuer"),
            nearline_status=dict(meta.get("nearline_status") or {}),
        )


@dataclass
class ScoreBatch:
    """Batch scoring output. Arrays aligned to the input matrix's row order."""

    fused: np.ndarray
    bands: np.ndarray
    actions: np.ndarray
    conformal_p: np.ndarray
    abstained: np.ndarray
    components: dict[str, np.ndarray]
    guard_refuse: np.ndarray
    guard_codes: list[tuple[str, ...]]
    reason_codes: list[tuple[str, ...]]
    latency_ms: np.ndarray


class Scorer:
    """Scores a FeatureMatrix, or one event at a time for the live `/score` endpoint."""

    def __init__(
        self,
        bundle: GateBundle,
        *,
        cfg: Config | None = None,
        store: OnlineStore | None = None,
        conformal_alpha: float = DEFAULT_CONFORMAL_ALPHA,
        density_z: float = DEFAULT_DENSITY_Z,
        g0_only: bool = False,
    ) -> None:
        self.bundle = bundle
        self.cfg = cfg or load_config()
        self.store = store or OnlineStore()
        self.conformal_alpha = float(conformal_alpha)
        self.density_z = float(density_z)
        #: The kill switch. G0-only is a REAL fallback because G0 has no model dependency.
        self.g0_only = bool(g0_only)
        self.g0 = G0Guards()

    # ---- component scores -------------------------------------------------------------
    def _g1_scores(self, fm: FeatureMatrix) -> np.ndarray:
        if self.bundle.g1 is None:
            return np.zeros(len(fm), dtype=np.float64)
        keep = [n for n in self.bundle.g1.feature_names]
        missing = [n for n in keep if n not in fm.names]
        if missing:
            raise ValueError(
                f"G1 needs {len(missing)} features the matrix does not have (e.g. {missing[:5]}). "
                f"This bundle was fitted for view {self.bundle.view!r}; scoring it against a "
                f"different view's matrix would silently reindex the columns."
            )
        idx = [fm.names.index(n) for n in keep]
        return self.bundle.g1.predict(fm.X[:, idx])

    def _conformal(self, fm: FeatureMatrix, g1: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Returns (p_values, novelty_score). Novelty is `1 - p`, so higher means more novel."""
        if self.bundle.conformal is None:
            return np.ones(len(fm)), np.zeros(len(fm))
        # Nonconformity = the G1 score. For a novelty p-value calibrated on BENIGN rows, a high
        # score is nonconforming, which is exactly the ordering we want.
        #
        # `mcc` and `geo_cell` MUST come from meta: the stratum is channel x MCC band x region, and
        # passing blanks here would compute p-values in a rail-only stratum while the calibration
        # used the full one. That is a train/serve skew with no visible symptom, so it raises.
        for required in ("mcc", "geo_cell"):
            if required not in fm.meta:
                raise KeyError(
                    f"the feature matrix carries no {required!r} in meta, so the Mondrian conformal "
                    f"stratum cannot be reconstructed at serve time. It would silently degrade to a "
                    f"rail-only stratum while the calibration used channel x MCC band x region."
                )
        p, _used = self.bundle.conformal.p_values(
            g1,
            fm.meta["rail"].astype(str).tolist(),
            fm.meta["mcc"].astype(str).tolist(),
            fm.meta["geo_cell"].astype(str).tolist(),
        )
        return p, 1.0 - p

    def _density(self, fm: FeatureMatrix) -> np.ndarray:
        """Density channel, normalised through `score_z`. NEVER the raw ECOD sum."""
        if self.bundle.density is None:
            return np.zeros(len(fm), dtype=np.float64)
        keep = [n for n in self.bundle.feature_names if n in fm.names] or list(fm.names)
        idx = [fm.names.index(n) for n in keep]
        z = self.bundle.density.score_z(fm.X[:, idx])
        if not self.bundle.density.calibrated:
            # Uncalibrated -> contribute NOTHING. The safe direction: an uncalibrated density
            # channel that contributed large values would escalate every row.
            return np.zeros_like(z)
        return np.clip(z / max(self.density_z, 1e-9), 0.0, 4.0)

    def _sketch(self, fm: FeatureMatrix) -> np.ndarray:
        out = np.zeros(len(fm), dtype=np.float64)
        for i in range(len(fm)):
            row = {
                "ts": float(fm.ts[i]),
                "amount_inr": float(fm.meta["amount_inr"][i]),
                "message_kind": str(fm.meta["message_kind"][i]),
                "beneficiary_id": str(fm.meta["beneficiary_id"][i]),
                "cardholder_id": str(fm.meta["cardholder_id"][i]),
                "device_fingerprint_id": str(fm.meta["device_fingerprint_id"][i]),
                "merchant_id": str(fm.meta["merchant_id"][i]),
            }
            self.store.observe(row)
            out[i] = self.store.sketch_risk_score(row)
        return out

    def _gate_b_component(self, fm: FeatureMatrix) -> np.ndarray:
        """The beneficiary prior, used as a component on BOTH personae.

        On GATE-B it is the core signal. On GATE-I it is the FORWARD composition channel: a
        payer-side push to a beneficiary carrying a mule prior is scored on that prior even when
        every payer-side signal is clean. That is the only mechanism by which GATE-I can act on
        coercion-class fraud at all.
        """
        names = ("in_out_skew", "pass_through_dwell_seconds", "beneficiary_account_age_days",
                 "beneficiary_distinct_payers_24h", "first_credit_source_concentration")
        present = [n for n in names if n in fm.names]
        if not present:
            return np.zeros(len(fm), dtype=np.float64)
        acc = np.zeros(len(fm), dtype=np.float64)
        cnt = 0
        for n in present:
            v = fm.column(n).astype(np.float64)
            valid = v > -1.0
            term = np.zeros_like(v)
            if n == "in_out_skew":
                term[valid] = np.clip(1.0 - v[valid] / 0.15, 0.0, 1.0)
            elif n == "pass_through_dwell_seconds":
                term[valid] = np.clip(1.0 - v[valid] / 3600.0, 0.0, 1.0)
            elif n == "beneficiary_account_age_days":
                term[valid] = np.clip(1.0 - v[valid] / 30.0, 0.0, 1.0)
            elif n == "beneficiary_distinct_payers_24h":
                term[valid] = np.clip(v[valid] / 40.0, 0.0, 1.0)
            else:
                term[valid] = np.clip(v[valid], 0.0, 1.0)
            acc += term
            cnt += 1
        return acc / max(cnt, 1)

    # ---- batch scoring ----------------------------------------------------------------
    def score_batch(self, fm: FeatureMatrix, rows: Sequence[Mapping[str, Any]] | None = None) -> ScoreBatch:
        n = len(fm)
        t0 = time.perf_counter()

        # ---- G0 -----------------------------------------------------------------------
        guard_refuse = np.zeros(n, dtype=bool)
        guard_codes: list[tuple[str, ...]] = [() for _ in range(n)]
        guard_rules: list[str | None] = [None for _ in range(n)]
        if rows is not None:
            for i, r in enumerate(rows):
                res = self.g0.evaluate(self.g0.prepare(dict(r)))
                guard_refuse[i] = res.refuse
                guard_codes[i] = res.reason_codes
                guard_rules[i] = res.guard_rule

        if self.g0_only:
            # KILL-SWITCH MODE. G0 refuses the impossible and approves everything else. This is a
            # real fallback, not an outage, precisely because G0 has no model dependency.
            fused = guard_refuse.astype(np.float64)
            bands = np.where(guard_refuse, "auto_decline", "approve").astype(object)
            actions = np.asarray(
                [action_for(str(fm.meta["rail"][i]), str(bands[i])) for i in range(n)], dtype=object
            )
            lat = np.full(n, (time.perf_counter() - t0) * 1000.0 / max(n, 1))
            return ScoreBatch(
                fused=fused, bands=bands, actions=actions,
                conformal_p=np.ones(n), abstained=np.zeros(n, dtype=bool),
                components={"g0": guard_refuse.astype(np.float64)},
                guard_refuse=guard_refuse, guard_codes=guard_codes,
                reason_codes=[tuple(c) + ("POLICY_KILL_SWITCH_G0_ONLY",) for c in guard_codes],
                latency_ms=lat,
            )

        # ---- components ----------------------------------------------------------------
        g1 = self._g1_scores(fm)
        p_conf, novelty = self._conformal(fm, g1)
        dens = self._density(fm)
        sk = self._sketch(fm)
        gb = self._gate_b_component(fm)

        components = {
            "g1": g1,
            "g2_conformal": novelty,
            "g2_density": dens,
            "sketch": sk,
            "gate_b": gb,
        }

        # ---- fusion --------------------------------------------------------------------
        fused = self.bundle.fusion.score(components)

        # ---- abstention (PRICED, not free) ---------------------------------------------
        abstained = p_conf <= self.conformal_alpha
        if self.bundle.density is not None and self.bundle.density.calibrated:
            abstained = abstained | (dens >= 1.0)

        # ---- bands and actions ---------------------------------------------------------
        rails = fm.meta["rail"].astype(str)
        bands = self.bundle.action_table.bands(fused, rails.tolist())
        # A structural refusal overrides the band. An abstention lifts an approve to friction, never
        # to a decline: "I do not recognise this" is not "this is fraud".
        bands = np.where(guard_refuse, "auto_decline", bands)
        bands = np.where(abstained & (bands == "approve"), "friction", bands)
        actions = np.asarray(
            [action_for(rails[i], str(bands[i])) for i in range(n)], dtype=object
        )

        # ---- reason codes ---------------------------------------------------------------
        reason_codes = self._reason_codes(
            fm, components, abstained, guard_codes, bands, conformal_p=p_conf
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        lat = np.full(n, elapsed_ms / max(n, 1), dtype=np.float64)
        return ScoreBatch(
            fused=fused, bands=bands, actions=actions, conformal_p=p_conf,
            abstained=abstained, components=components, guard_refuse=guard_refuse,
            guard_codes=guard_codes, reason_codes=reason_codes, latency_ms=lat,
        )

    def _reason_codes(
        self,
        fm: FeatureMatrix,
        components: Mapping[str, np.ndarray],
        abstained: np.ndarray,
        guard_codes: Sequence[tuple[str, ...]],
        bands: np.ndarray,
        conformal_p: np.ndarray | None = None,
    ) -> list[tuple[str, ...]]:
        """Derive the fixed-vocabulary reason codes, SHAP-driven where G1 dominates."""
        n = len(fm)
        out: list[list[str]] = [list(guard_codes[i]) for i in range(n)]

        if self.bundle.g1 is not None:
            idx = [fm.names.index(x) for x in self.bundle.g1.feature_names if x in fm.names]
            # SHAP IS COMPUTED ONLY FOR ROWS THAT ARE ACTUALLY ACTIONED.
            #
            # `top_attributions` runs LightGBM `pred_contrib` (an n_rows x n_features+1 matrix) and
            # then loops IN PYTHON, one argsort and one dict per row. Over a 2.67M-row test window
            # that is ~6.7 GB of contributions plus 2.67M dict builds -- and `eval` scores the test
            # window five times (once primary, once per view for the visibility ablation), so it was
            # the dominant cost and the OOM risk of the whole stage.
            #
            # A reason code only means something for a case a human or a policy will act on: an
            # APPROVED row is never explained (see the tail of this method, which only fills a code
            # for actioned bands). NO METRIC READS `reason_codes` -- eval/metrics.py never references
            # them -- so restricting the SHAP pass to actioned rows changes no reported number and
            # cuts the work by the inverse of the action rate, roughly fiftyfold at the staffed budget.
            actioned_idx = np.flatnonzero((bands != "approve") | abstained | np.asarray(
                [bool(g) for g in guard_codes], dtype=bool
            ))
            top_by_row: dict[int, dict[str, float]] = {}
            if actioned_idx.size:
                sub = self.bundle.g1.top_attributions(fm.X[np.ix_(actioned_idx, idx)], k=3)
                top_by_row = {int(r): sub[j] for j, r in enumerate(actioned_idx)}
            top = [top_by_row.get(i, {}) for i in range(n)]
            reg = load_registry()
            fam_to_code = {
                "velocity_panel": "G1_VELOCITY_SELF_SPIKE",
                "velocity_distinct": "G1_FANOUT_DEGREE",
                "temporal": "G1_TEMPORAL_UNIFORMITY",
                "sequence_artefacts": "G1_RETRY_CHAIN",
                "trust_envelope": "G1_TRUST_TELEMETRY_IMPLAUSIBLE",
                "mandate_deltas": "G1_MANDATE_HEADROOM",
                "threshold_geometry": "G1_THRESHOLD_HUGGING",
                "cross_message": "G1_CLEARING_DIVERGENCE",
                "graph_sketches": "G1_FANOUT_DEGREE",
                "beneficiary_side": "GB_IN_OUT_SKEW",
                "onboarding_cohort": "G1_ONBOARDING_COHORT",
                "entity_age": "G1_COLD_ENTITY_PRIOR",
                "habit_deviation": "G1_HABIT_DEVIATION",
                "merchant_side": "G1_MERCHANT_RAMP",
                "device_session": "G1_IDENTITY_TRANSITION",
                "rail_context": "G1_INCUMBENT_AGREES",
                "channel_context": "G1_INCUMBENT_AGREES",
            }
            for i in range(n):
                if str(bands[i]) == "approve":
                    continue
                for feat, contrib in top[i].items():
                    if contrib <= 0:
                        continue
                    try:
                        fam = reg.get(feat).family
                    except KeyError:
                        continue
                    code = fam_to_code.get(fam)
                    if code and code not in out[i]:
                        out[i].append(code)

        # ATTRIBUTE THE ABSTENTION TO THE CHANNEL THAT ACTUALLY FIRED. Abstention triggers on EITHER
        # a low conformal p-value OR a high ECOD density score (see the abstention block above), but
        # this previously stamped G2_CONFORMAL_NOVEL on EVERY abstained row unconditionally. A row that
        # abstained purely on density then displayed "Unlike anything in the calibration set" beside a
        # conformal p of 0.9967 -- which means the OPPOSITE, highly conforming. On the judge-driven
        # screen that is a self-contradicting row, and the underlying suspicion (a genuine low-density
        # outlier) got the credit taken away from it by a false explanation.
        p_arr = None if conformal_p is None else np.asarray(conformal_p, dtype=np.float64)
        dens_arr = np.asarray(components.get("g2_density", np.zeros(n)), dtype=np.float64)
        for i in range(n):
            if abstained[i]:
                conformal_fired = bool(p_arr is None or p_arr[i] <= self.conformal_alpha)
                density_fired = bool(dens_arr[i] >= 1.0)
                if conformal_fired and "G2_CONFORMAL_NOVEL" not in out[i]:
                    out[i].append("G2_CONFORMAL_NOVEL")
                if density_fired and "G2_DENSITY_OUTLIER" not in out[i]:
                    out[i].append("G2_DENSITY_OUTLIER")
                if not conformal_fired and not density_fired and not out[i]:
                    # Abstained but neither channel explains it: say so rather than invent a reason.
                    out[i].append("G2_ABSTAIN_UNATTRIBUTED")
            if str(bands[i]) in ("friction", "review", "auto_decline") and not out[i]:
                # Never emit an empty explanation for an actioned row. A reviewer cannot dispose of
                # a case with no reason code.
                out[i].append("POLICY_RAIL_LADDER")
        return [tuple(x) for x in out]

    # ---- one event, for the live endpoint ---------------------------------------------
    def score_one(
        self,
        fm: FeatureMatrix,
        row: Mapping[str, Any],
        *,
        index: int = 0,
        persona: str | None = None,
    ) -> Decision:
        """Score a single event and return a full Decision with a MEASURED latency."""
        t0 = time.perf_counter()
        sub = fm.subset_rows(np.asarray([i == index for i in range(len(fm))], dtype=bool))
        batch = self.score_batch(sub, rows=[row])
        p = persona or self.bundle.persona
        rail = str(sub.meta["rail"][0])

        freeze_payload = None
        action = str(batch.actions[0])
        codes = list(batch.reason_codes[0])
        if p == "GATE-B":
            prior = 0.0
            if self.bundle.exchange is not None:
                prior = self.bundle.exchange.prior_from_exchange(str(row.get("beneficiary_id", "")))
            ba = decide_beneficiary_action(
                score=float(batch.fused[0]),
                row={**row, "cohort_tag": str(sub.meta["cohort_tag"][0])},
                t_hold=self.bundle.action_table.t_review.get(rail, self.bundle.action_table.global_t_review),
                t_freeze=self.bundle.action_table.t_decline.get(rail, self.bundle.action_table.global_t_decline),
                exchange_prior=prior,
                cfg=self.cfg,
            )
            action = ba.action
            for c in ba.reason_codes:
                if c not in codes:
                    codes.append(c)
            if ba.action in ("hold", "freeze_recommend"):
                hold = self.cfg.beneficiary_hold
                freeze_payload = freeze_recommendation(
                    str(row.get("beneficiary_id", "")),
                    score=float(batch.fused[0]),
                    max_hold_hours=int(hold["max_hold_hours"]),
                    auto_release=bool(hold["auto_release_unless_escalated"]),
                    golden_hour_target_minutes=int(hold["golden_hour_target_minutes"]),
                    reason_codes=codes,
                    inflow_at_risk_inr=float(row.get("amount_inr", 0.0)),
                )

        latency = (time.perf_counter() - t0) * 1000.0
        return Decision(
            event_id=str(sub.event_ids[0]),
            persona=p,
            score=float(batch.fused[0]),
            action=action,
            band=str(batch.bands[0]),
            latency_ms=latency,
            reason_codes=tuple(codes),
            component_scores={k: float(v[0]) for k, v in batch.components.items()},
            attribution=self._attribution_for(sub),
            conformal_p=float(batch.conformal_p[0]),
            abstained=bool(batch.abstained[0]),
            guard_rule=(batch.guard_codes[0][0] if batch.guard_codes[0] else None),
            model_version=self.bundle.model_version,
            freeze_payload=freeze_payload,
        )

    def _attribution_for(self, fm: FeatureMatrix) -> dict[str, float]:
        """Top SHAP attributions for one row. The input to the archive's distinctness test."""
        if self.bundle.g1 is None:
            return {}
        idx = [fm.names.index(x) for x in self.bundle.g1.feature_names if x in fm.names]
        return self.bundle.g1.top_attributions(fm.X[:, idx], k=8)[0]
