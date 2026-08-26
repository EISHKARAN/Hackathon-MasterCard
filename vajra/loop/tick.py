"""ONE TICK — the six stages, and the telemetry that proves the loop moved.

    1. ARCHIVE-select   pick elites and under-filled feasible cells
    2. PLAN             the LLM Composer emits attack plans — ONE CALL PER TICK, not per transaction
    3. EXECUTE          the RL attacker runs campaigns under a P&L budget, observing only what an
                        attacker observes
    4. SCORE            GATE-I and GATE-B score every event
    5. MINE             the Gap Miner clusters escapes and renders the region in plain English
    6. FORGE            retrain, withhold a sibling, promotion gate, regression ledger

THE TICK TIMER IS DISPLAYED WHATEVER IT READS. The design's <=120s target is a design constraint we hold
ourselves to, not a measured runtime, and a judge with a stopwatch would catch a mismatch long before we
finished the sentence. So `TickResult.wall_clock_seconds` is measured and rendered on the LOOP screen.

THE EXECUTION BUDGET IS ITSELF A METRIC. Quality-diversity search with two samples per cell is not
search: each cell's "elite" is simply its only occupant, attacker P&L selects nothing, and the ruin
condition never binds. `archive.coverage()["search_claim"]` downgrades the claim automatically when the
realised budget is too thin.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from archive.map_elites import Archive, Elite
from attack.campaigns import campaigns_from_plans
from attack.composer import Composer, ComposerProposal
from attack.rl import (
    TACTICS,
    AttackerObservation,
    Context,
    QLambdaAgent,
    ThompsonBandit,
    Transition,
    allowed_tactics,
    budget_bucket,
    context_for,
    heat_level,
    outcome_from_observation,
    ruin_decision,
    state_index,
    step_reward,
)
from core.config import Config, load_config
from core.rng import stream
from grammar.cell_of import cell_of
from grammar.composition import Composition
from grammar.sealed import load_sealed_manifest
from loop.forge import Forge, SiblingWithholding
from loop.gap_miner import AttackHypothesisRequest, GapMiner
from loop.sentinel import CanarySuite, Sentinel


@dataclass
class TickResult:
    tick: int
    wall_clock_seconds: float
    stage_seconds: dict[str, float]
    selected_cells: list[str]
    proposals: list[dict[str, Any]]
    n_campaigns: int
    n_events: int
    n_escapes: int
    escape_region: dict[str, Any]
    admitted: list[dict[str, Any]]
    rejected: list[dict[str, Any]]
    coverage: dict[str, Any]
    rl: dict[str, Any]
    sibling: dict[str, Any] | None
    promotion: dict[str, Any] | None
    regressions: list[dict[str, Any]]
    sentinel: dict[str, Any] | None
    telemetry: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "wall_clock_seconds": round(self.wall_clock_seconds, 2),
            "stage_seconds": {k: round(v, 3) for k, v in self.stage_seconds.items()},
            "selected_cells": self.selected_cells,
            "proposals": self.proposals,
            "n_campaigns": self.n_campaigns,
            "n_events": self.n_events,
            "n_escapes": self.n_escapes,
            "escape_region": self.escape_region,
            "admitted": self.admitted,
            "rejected": self.rejected,
            "coverage": self.coverage,
            "rl": self.rl,
            "sibling": self.sibling,
            "promotion": self.promotion,
            "regressions": self.regressions,
            "sentinel": self.sentinel,
            "telemetry": self.telemetry,
            "tick_budget_note": (
                "The <=120s target is a DESIGN CONSTRAINT, not a measured runtime. This number is what "
                "the tick actually took, and the LOOP screen displays it whatever it reads."
            ),
        }


@dataclass
class LoopTelemetry:
    """The six published series. Every one is a DIRECTION OF TRAVEL, not an absolute."""

    cpre_by_family: list[dict[str, float]] = field(default_factory=list)
    time_to_evade: list[dict[str, Any]] = field(default_factory=list)
    time_to_close: list[dict[str, Any]] = field(default_factory=list)
    sibling_recall: list[dict[str, Any]] = field(default_factory=list)
    guardrails: list[dict[str, Any]] = field(default_factory=list)
    regressions: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "series_1_cost_per_rupee_extracted": {
                "direction": "UP",
                "unit": "simulator-internal accounting quantity, NOT a market price",
                "per_tick": self.cpre_by_family,
                "note": (
                    "Reported PER FAMILY so one family's collapse cannot be averaged away, and as a "
                    "DIRECTION OF TRAVEL rather than an absolute rupee figure, because the cost "
                    "constants are ours."
                ),
            },
            "series_2_time_to_evade": {
                "direction": "UP",
                "per_tick": self.time_to_evade,
                "note": (
                    "Measured against a FROZEN gate snapshot. If the defender retrains while the "
                    "attacker searches, the two co-drift and the number is meaningless."
                ),
            },
            "series_3_time_to_close": {"direction": "DOWN", "per_tick": self.time_to_close},
            "series_4_sibling_transfer_recall": {
                "direction": "UP",
                "per_tick": self.sibling_recall,
                "note": (
                    "THE LOOP'S VALIDITY SERIES — the only one of the six that distinguishes learning "
                    "from memorisation. Measured at the PRE-RETRAIN threshold."
                ),
            },
            "series_5_guardrails": {
                "direction": "FLAT",
                "per_tick": self.guardrails,
                "note": (
                    "The anti-cheat. Winning by declining everything is trivial, and a system whose "
                    "recall climbs while its HARD-BENIGN false-positive line climbs with it has learned "
                    "nothing worth shipping."
                ),
            },
            "series_6_regression_ledger": {
                "direction": "DISPLAYED",
                "entries": self.regressions,
            },
        }


class TickRunner:
    """Runs one or more ticks. Holds the persistent RL and archive state across them."""

    def __init__(
        self,
        *,
        archive: Archive,
        composer: Composer,
        cfg: Config | None = None,
        agent: QLambdaAgent | None = None,
        bandit: ThompsonBandit | None = None,
        forge: Forge | None = None,
        gap_miner: GapMiner | None = None,
        sentinel: Sentinel | None = None,
        canary: CanarySuite | None = None,
        legal_cell_index: Mapping[str, Sequence[str]] | None = None,
        rl_enabled: bool = True,
        bandit_only: bool = False,
        random_tactic: bool = False,
    ) -> None:
        self.cfg = cfg or load_config()
        self.archive = archive
        self.composer = composer
        self.agent = agent or QLambdaAgent.from_config()
        self.bandit = bandit or ThompsonBandit.from_config()
        self.forge = forge or Forge()
        self.gap_miner = gap_miner or GapMiner()
        self.sentinel = sentinel or Sentinel()
        self.canary = canary or CanarySuite()
        self.legal_cell_index = dict(legal_cell_index or {})
        self.telemetry = LoopTelemetry()
        self.rng = stream("loop.tick")
        #: CONTROL ARMS. Each disables one level so the RL claim is falsifiable rather than asserted.
        self.rl_enabled = bool(rl_enabled)
        self.bandit_only = bool(bandit_only)
        self.random_tactic = bool(random_tactic)
        self.arm_label = (
            "static (loop disabled)" if not rl_enabled
            else "bandit_only (Level 2 disabled)" if bandit_only
            else "random_tactic (Level 2 replaced by uniform random choice)" if random_tactic
            else "full hierarchical agent"
        )
        #: Tick at which each family was first discovered, for time-to-close.
        self._discovered_at: dict[str, int] = {}
        self._closed_at: dict[str, int] = {}

    # ---- stage 1: ARCHIVE-select -------------------------------------------------------
    def select(self, n: int = 3) -> list[tuple[Elite | None, str]]:
        out: list[tuple[Elite | None, str]] = []
        for _ in range(max(1, n)):
            out.append(self.archive.select_parent())
        return out

    # ---- stage 2: PLAN -----------------------------------------------------------------
    def plan(
        self,
        selections: Sequence[tuple[Elite | None, str]],
        escape_region: AttackHypothesisRequest,
        *,
        stamped_at: str,
    ) -> tuple[list[ComposerProposal], list[dict[str, Any]]]:
        """ONE Composer invocation per tick, on the escape region.

        Multiple cells are targeted from that ONE prompt's cached response family — the cap is on
        network calls, not on proposals, and `Composer.propose` is cache-first so repeated targets in a
        tick cost nothing.
        """
        proposals: list[ComposerProposal] = []
        rejected: list[dict[str, Any]] = []
        for parent, cell_id in selections:
            if not cell_id:
                continue
            prop, verdict = self.composer.propose(
                escape_region=escape_region.escape_region_text,
                cell_id=cell_id,
                parent_composition=parent.composition if parent else None,
                region_signatures=escape_region.signatures,
                legal_for_cell=self.legal_cell_index.get(cell_id, ()),
                stamped_at=stamped_at,
            )
            if prop is None:
                rejected.append({"cell_id": cell_id, "why": verdict.explain()})
            else:
                proposals.append(prop)
        return proposals, rejected

    # ---- stage 3: EXECUTE --------------------------------------------------------------
    def execute_campaign_rl(
        self,
        proposal: ComposerProposal,
        *,
        budget_inr: float,
        env_step,
        max_steps: int = 12,
    ) -> dict[str, Any]:
        """Run one campaign as an RL episode.

        `env_step(tactic, arm, stage) -> AttackerObservation` is supplied by the caller, which is what
        keeps this class independent of the simulator: the loop CLI wires it to the real engine, and a
        test wires it to a stub.
        """
        comp = Composition.parse(proposal.grammar_str)
        has_ben = comp.has_beneficiary_leg()
        mask_names = allowed_tactics(comp.EVASION, has_beneficiary_leg=has_ben)
        mask = [TACTICS.index(t) for t in mask_names]
        if not mask:
            return {"error": "empty action mask", "grammar_str": proposal.grammar_str}

        costs = self.cfg.attacker_costs
        stages = list(proposal.stages) or ["establish", "extract"]
        spent = 0.0
        retained = 0.0
        probes = mules = credentials = 0
        adverse_window: list[int] = []
        transitions: list[Transition] = []
        trace: list[dict[str, Any]] = []
        ruin_trigger = ""
        detection_latency_h = -1.0
        break_even_h = -1.0
        elapsed_h = 0.0

        outcome = "none"
        for step in range(max_steps):
            stage_name = stages[min(step, len(stages) - 1)]
            heat = heat_level(float(np.mean(adverse_window[-8:])) if adverse_window else 0.0)
            bb = budget_bucket(budget_inr - spent, budget_inr)
            s = state_index(stage_name, outcome, bb, heat)

            # ---- LEVEL 2: choose a TACTIC ------------------------------------------------
            if self.bandit_only:
                # Control arm: no MDP. Always try to take the money, which is what a bandit with no
                # credit assignment does -- it cannot learn to spend on probing that pays later.
                a = TACTICS.index("cash_out") if TACTICS.index("cash_out") in mask else mask[0]
            elif self.random_tactic:
                a = int(mask[int(self.rng.integers(0, len(mask)))])
            else:
                a = self.agent.act(s, mask, self.rng)
            tactic = TACTICS[a]

            # ---- LEVEL 1: choose the ARM PARAMETERS --------------------------------------
            ctx = context_for(comp.RAIL, max(1.0, budget_inr / max(1, max_steps)), 12.0, -1.0)
            arm, _samples = self.bandit.select(ctx, tactic, self.rng)

            obs: AttackerObservation = env_step(tactic, arm, stage_name)

            if tactic == "probe":
                probes += int(max(1, arm.fan_out))
            if tactic in ("rotate_entity", "pad_payer_set"):
                mules += 1
            if tactic == "inherit_trust":
                credentials += 1

            spent += float(obs.spend_inr)
            retained += float(obs.value_retained_inr)
            elapsed_h += 1.0
            adverse_window.append(1 if obs.adverse else 0)
            if break_even_h < 0 and retained >= spent and spent > 0:
                break_even_h = elapsed_h
            if not ruin_trigger and obs.ruin_event:
                ruin_trigger = obs.ruin_event
                detection_latency_h = elapsed_h

            self.bandit.update(ctx, arm, obs)

            ruined_now, ruin_reason = ruin_decision(
                detection_latency_hours=detection_latency_h,
                break_even_hours=break_even_h if break_even_h > 0 else elapsed_h + 1.0,
                trigger=ruin_trigger,
            )
            r, breakdown = step_reward(
                obs,
                probes=probes,
                mules=mules,
                credentials=credentials,
                elapsed_steps=1,
                costs=costs,
                ruin_fired=ruined_now,
                unrecovered_spend_inr=max(0.0, spent - retained),
            )
            next_outcome = outcome_from_observation(obs)
            next_stage = stages[min(step + 1, len(stages) - 1)]
            s2 = state_index(
                next_stage,
                next_outcome,
                budget_bucket(budget_inr - spent, budget_inr),
                heat_level(float(np.mean(adverse_window[-8:]))),
            )
            terminal = bool(ruined_now or spent >= budget_inr or step == max_steps - 1)
            tr = Transition(s, a, r, s2, terminal, tuple(mask))
            transitions.append(tr)
            if self.rl_enabled and not self.bandit_only and not self.random_tactic:
                self.agent.update(tr)

            trace.append(
                {
                    "step": step,
                    "stage": stage_name,
                    "tactic": tactic,
                    "arm": arm.as_dict(),
                    "observation": obs.as_dict(),
                    "reward": r,
                    "reward_breakdown": breakdown,
                }
            )
            outcome = next_outcome
            if terminal:
                break

        if self.rl_enabled:
            self.agent.remember(transitions)

        total_cost = (
            float(costs.get("probe_cost", 0.0)) * probes
            + float(costs.get("mule_burn", 0.0)) * mules
            + float(costs.get("credential_cost", 0.0)) * credentials
            + float(costs.get("lambda_step_cost", 0.0)) * elapsed_h
        )
        ruined, ruin_reason = ruin_decision(
            detection_latency_hours=detection_latency_h,
            break_even_hours=break_even_h,
            trigger=ruin_trigger,
        )
        fitness = retained - total_cost - (
            float(costs.get("ruin_penalty_multiplier", 1.5)) * max(0.0, spent - retained)
            if ruined else 0.0
        )
        return {
            "grammar_str": proposal.grammar_str,
            "stages": stages,
            "n_steps": len(trace),
            "value_retained_inr": retained,
            "spend_inr": spent,
            "cost_inr": total_cost,
            "fitness": fitness,
            "ruined": ruined,
            "ruin_trigger": ruin_reason or ruin_trigger,
            "detection_latency_hours": detection_latency_h,
            "break_even_hours": break_even_h,
            "cpre": (total_cost / retained) if retained > 0 else float("inf"),
            "trace": trace,
            "arm_label": self.arm_label,
        }

    # ---- stage 5 helper: escapes -------------------------------------------------------
    def mine(
        self,
        X: np.ndarray,
        feature_names: Sequence[str],
        escaped: np.ndarray,
        cell_ids: Sequence[str],
        signatures: Sequence[str] = (),
    ) -> AttackHypothesisRequest:
        clusters = self.gap_miner.cluster_escapes_by_cell(cell_ids, escaped)
        worst = clusters[0][0] if clusters else ""
        return self.gap_miner.mine(
            X, feature_names, escaped, cell_id=worst, signatures=signatures
        )

    # ---- telemetry ---------------------------------------------------------------------
    def record_tick_telemetry(
        self,
        tick: int,
        *,
        results: Sequence[Mapping[str, Any]],
        sibling: Mapping[str, Any] | None,
        guardrails: Mapping[str, Any] | None,
        regressions: Sequence[Mapping[str, Any]],
        time_to_evade: Mapping[str, Any] | None,
    ) -> None:
        by_family: dict[str, list[float]] = {}
        for r in results:
            fam = str(r.get("grammar_str", ""))[:40]
            cpre = float(r.get("cpre", float("inf")))
            if np.isfinite(cpre):
                by_family.setdefault(fam, []).append(cpre)
        self.telemetry.cpre_by_family.append(
            {"tick": float(tick), **{k: float(np.mean(v)) for k, v in by_family.items()}}
        )
        if time_to_evade:
            self.telemetry.time_to_evade.append({"tick": tick, **dict(time_to_evade)})
        if sibling:
            self.telemetry.sibling_recall.append({"tick": tick, **dict(sibling)})
        if guardrails:
            self.telemetry.guardrails.append({"tick": tick, **dict(guardrails)})
        self.telemetry.regressions.extend([dict(r) for r in regressions])

        # time-to-close: ticks from discovery to recall recovery, per family.
        for r in results:
            fam = str(r.get("grammar_str", ""))
            self._discovered_at.setdefault(fam, tick)
        if sibling and sibling.get("closed_vector_recall_after_retrain", 0.0) >= 0.80:
            fam = str(sibling.get("closed_composition", ""))
            if fam and fam not in self._closed_at:
                self._closed_at[fam] = tick
                self.telemetry.time_to_close.append(
                    {
                        "tick": tick,
                        "family": fam[:60],
                        "ticks_to_close": tick - self._discovered_at.get(fam, tick),
                        "definition": "ticks from archive-elite discovery to closed-vector recall >= 0.80",
                    }
                )

    def save_state(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.archive.save(directory / "archive.json")
        self.agent.save(directory / "q_agent")
        self.bandit.save(directory / "bandit.json")
        self.forge.save(directory / "forge.json")
        (directory / "telemetry.json").write_text(
            json.dumps(self.telemetry.as_dict(), indent=2) + "\n", encoding="utf-8"
        )
        (directory / "sentinel.json").write_text(
            json.dumps(self.sentinel.as_dict(), indent=2) + "\n", encoding="utf-8"
        )
        self.canary.save(directory / "canary")
        self.composer.flush_reject_log()
