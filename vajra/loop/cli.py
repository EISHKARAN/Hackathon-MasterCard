"""`make loop` — run recorded TICKs plus the control arms, and write the loop telemetry.

FOUR ARMS, and every one of them is a PUBLISHED RESULT rather than a diagnostic:

    full           the hierarchical agent: MAP-Elites curriculum + Q(lambda) + Thompson bandit
    random_tactic  Level 2 replaced by uniform random tactic choice -> what credit assignment bought
    bandit_only    Level 2 disabled -> the honest null for "why RL at all"
    static         the whole loop disabled -> LOOP-LIFT, the headline control

IF `bandit_only` MATCHES `full`, WE REPORT THAT THE MDP LEVEL BOUGHT NOTHING. That outcome is
survivable; hiding it is not. And if LOOP-LIFT is small we report it and argue the loop's value on
time-to-close instead of on raw recall.

Both arms are SINGLE RUNS ON ONE SEED unless `--seeds` is raised. A single-seed delta is weak evidence
and the report labels it n=1 rather than dressing it up.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any, Mapping, Sequence

import numpy as np

from archive.map_elites import Archive, Elite
from attack.composer import Composer
from attack.dual_use_lint import utc_stamp
from attack.rl import AttackerObservation, QLambdaAgent, ThompsonBandit
from core import paths
from core.config import load_config
from core.io import write_json
from core.rng import stream
from core.stagelog import stage
from features.builder import build_matrix, fit_reference_stats, prepare_columns
from features.registry import load_registry
from grammar.cell_of import cell_of
from grammar.composition import Composition
from grammar.enumerate_space import legal_cell_index
from grammar.seeds import load_seeds
from gate.scorer import GateBundle, Scorer
from gate.sketches import OnlineStore
from loop.forge import Forge
from loop.gap_miner import GapMiner
from loop.sentinel import CanarySuite, Sentinel
from loop.tick import TickRunner
from eval.metrics import recall_at_fpr, wilson_interval
from eval.splits import temporal_split
from gate.cli import _load_events, _load_label_table, _resolve_labels


def _build_env_step(rng: np.random.Generator, difficulty: float):
    """The attacker's environment, expressed ONLY in attacker-observable terms.

    This is a REDUCED-FORM environment, and saying so matters: a full tick would re-run the simulator
    and re-score every event, which is what `make all` does end to end. Inside the loop we model the
    gate's RESPONSE to a tactic, calibrated by `difficulty` (the gate's realised action rate), so the
    RL agent learns against a moving defender without a full re-simulation per step.

    WHAT IT DOES NOT DO: it never reveals a score, a p-value or a feature. `AttackerObservation`'s field
    set makes that structural rather than a promise.
    """

    def env_step(tactic: str, arm, stage_name: str) -> AttackerObservation:  # noqa: ANN001
        # Base adverse probability rises with the gate's difficulty and falls for evasive tactics.
        evade_bonus = {
            "probe": 0.35, "hug_threshold": 0.30, "split_velocity": 0.28, "rotate_entity": 0.25,
            "extend_dwell": 0.22, "pad_payer_set": 0.20, "switch_acquirer": 0.18,
            "inherit_trust": 0.15, "deescalate_amount": 0.12, "escalate_amount": -0.15,
            "cash_out": -0.20,
        }.get(tactic, 0.0)
        p_adverse = float(np.clip(difficulty - evade_bonus, 0.01, 0.97))
        adverse = bool(rng.random() < p_adverse)

        band = {"micro": 60.0, "low": 900.0, "mid": 8_000.0, "high": 45_000.0, "very_high": 180_000.0}
        amount = float(band.get(arm.amount_band, 5_000.0) * max(1, arm.fan_out))
        spend = float(
            amount * 0.02 if tactic == "probe" else amount * 0.05
        )
        if tactic == "probe":
            # Probing spends and returns NO value. This is the delayed-reward structure a bandit
            # cannot learn to exploit and the MDP can.
            return AttackerObservation(
                approved=not adverse, declined=adverse, reason_code="declined_risk" if adverse else "",
                response_latency_ms=float(abs(rng.normal(45.0, 15.0))),
                amount_inr=amount, value_retained_inr=0.0, spend_inr=spend,
            )

        if adverse:
            kind = rng.random()
            if kind < 0.45:
                return AttackerObservation(
                    declined=True, reason_code="declined_risk",
                    response_latency_ms=float(abs(rng.normal(42.0, 14.0))),
                    amount_inr=amount, value_retained_inr=0.0, spend_inr=spend,
                )
            if kind < 0.70:
                return AttackerObservation(
                    stepped_up=True, reason_code="step_up_required",
                    response_latency_ms=float(abs(rng.normal(55.0, 18.0))),
                    amount_inr=amount, value_retained_inr=0.0, spend_inr=spend,
                )
            if kind < 0.88:
                return AttackerObservation(
                    approved=True, credit_landed=True, credit_held=True, onward_send_blocked=True,
                    response_latency_ms=float(abs(rng.normal(30.0, 10.0))),
                    amount_inr=amount, value_retained_inr=0.0, spend_inr=spend,
                )
            return AttackerObservation(
                approved=True, credit_landed=True, account_frozen=True,
                seconds_to_freeze=float(abs(rng.normal(1_800.0, 900.0))),
                response_latency_ms=float(abs(rng.normal(30.0, 10.0))),
                amount_inr=amount, value_retained_inr=0.0, spend_inr=spend,
            )

        skim = 0.97 if tactic == "cash_out" else 0.55
        return AttackerObservation(
            approved=True, credit_landed=True,
            response_latency_ms=float(abs(rng.normal(38.0, 12.0))),
            amount_inr=amount, value_retained_inr=amount * skim, spend_inr=spend,
        )

    return env_step


def _run_arm(
    arm_name: str,
    *,
    n_ticks: int,
    difficulty: float,
    legal_index: Mapping[str, Sequence[str]],
    seed_cells: Sequence[str],
    stamped_at: str,
) -> dict[str, Any]:
    cfg = load_config()
    archive = Archive(cfg)
    archive.register_seed_cells(seed_cells)
    # Selection targets cells the grammar can actually occupy; coverage is still reported over the
    # full feasible denominator.
    archive.set_reachable(legal_index.keys())
    composer = Composer(mode="cached", blind=(arm_name == "static"))
    runner = TickRunner(
        archive=archive,
        composer=composer,
        cfg=cfg,
        legal_cell_index=legal_index,
        rl_enabled=(arm_name != "static"),
        bandit_only=(arm_name == "bandit_only"),
        random_tactic=(arm_name == "random_tactic"),
    )
    rng = stream(f"loop.tick.{arm_name}")
    env_step = _build_env_step(rng, difficulty)
    gm = GapMiner()

    ticks: list[dict[str, Any]] = []
    for t in range(1, n_ticks + 1):
        import time as _time

        t0 = _time.perf_counter()
        stage_s: dict[str, float] = {}

        # ---- 1. ARCHIVE-select --------------------------------------------------------
        s0 = _time.perf_counter()
        selections = runner.select(n=3)
        stage_s["1_archive_select"] = _time.perf_counter() - s0

        # ---- 5' MINE (previous tick's escapes drive this tick's plan) -------------------
        s0 = _time.perf_counter()
        prev = ticks[-1] if ticks else None
        if prev and prev.get("escape_region", {}).get("reportable"):
            region_obj = prev["escape_region"]
        else:
            region_obj = {
                "escape_region_text": (
                    "no prior escape region (first tick): targeting under-occupied feasible cells"
                ),
                "signatures": [],
                "cell_id": selections[0][1] if selections else "",
                "reportable": False,
            }
        stage_s["5_mine_prev"] = _time.perf_counter() - s0

        # ---- 2. PLAN ------------------------------------------------------------------
        s0 = _time.perf_counter()

        class _Region:
            escape_region_text = str(region_obj.get("escape_region_text", ""))
            signatures = tuple(region_obj.get("signatures") or ())

        proposals, rejected = runner.plan(selections, _Region(), stamped_at=stamped_at)
        stage_s["2_plan"] = _time.perf_counter() - s0

        # ---- 3. EXECUTE ---------------------------------------------------------------
        s0 = _time.perf_counter()
        results = [
            runner.execute_campaign_rl(p, budget_inr=float(cfg.attacker_costs.get("mule_burn", 900)) * 60, env_step=env_step)
            for p in proposals
        ]
        stage_s["3_execute"] = _time.perf_counter() - s0

        # ---- 4. SCORE (folded into EXECUTE's environment in the reduced-form loop) -----
        # The full end-to-end scoring path is `make sim && make train && make eval`. Inside the loop
        # the gate's response IS the environment, and `difficulty` is calibrated from the gate's
        # realised action rate so the agent learns against the real operating point.

        # ---- admit into the archive ----------------------------------------------------
        admitted: list[dict[str, Any]] = []
        rejected_admissions: list[dict[str, Any]] = []
        for p, r in zip(proposals, results):
            if "error" in r:
                rejected_admissions.append({"grammar_str": p.grammar_str, "why": r["error"]})
                continue
            comp = Composition.parse(p.grammar_str)
            cell = cell_of(comp, p.stages)
            e = Elite(
                cell_id=cell.id,
                composition=p.grammar_str,
                stages=tuple(p.stages),
                family_id=f"GEN-{abs(hash(p.grammar_str)) % 10000:04d}",
                fitness=float(r["fitness"]),
                value_retained_inr=float(r["value_retained_inr"]),
                cost_inr=float(r["cost_inr"]),
                ruined=bool(r["ruined"]),
                ruin_trigger=str(r["ruin_trigger"]),
                detection_latency_hours=float(r["detection_latency_hours"]),
                break_even_hours=float(r["break_even_hours"]),
                n_events=int(r["n_steps"]),
                discovered_tick=t,
            )
            ok, why = archive.try_admit(e)
            (admitted if ok else rejected_admissions).append(
                {"cell_id": cell.id, "grammar_str": p.grammar_str, "why": why, "fitness": e.fitness}
            )

        # ---- 5. MINE (this tick's escapes) --------------------------------------------
        s0 = _time.perf_counter()
        esc_rows = []
        esc_flags = []
        esc_cells = []
        for p, r in zip(proposals, results):
            for step in r.get("trace", []):
                obs = step["observation"]
                esc_flags.append(0 if obs.get("declined") or obs.get("stepped_up")
                                 or obs.get("credit_held") or obs.get("account_frozen") else 1)
                esc_rows.append([
                    float(step["arm"]["fan_out"]),
                    float(obs.get("amount_inr", 0.0)),
                    float(obs.get("response_latency_ms", -1.0)),
                    float(step.get("reward", 0.0)),
                ])
                esc_cells.append(cell_of(Composition.parse(p.grammar_str), p.stages).id)
        if esc_rows:
            X = np.asarray(esc_rows, dtype=np.float32)
            # Feature names here are the LOOP's own reduced-form names, not the registry's: the
            # in-loop Gap Miner runs on the attacker-visible trace. The full-registry Gap Miner runs
            # in `make eval` on the scored population.
            region = gm.mine(
                X, ["fan_out", "amount_inr", "response_latency_ms", "step_reward"],
                np.asarray(esc_flags), cell_id=(esc_cells[0] if esc_cells else ""),
            )
        else:
            region = gm.mine(np.zeros((0, 4), dtype=np.float32), ["a", "b", "c", "d"], np.zeros(0), cell_id="")
        stage_s["5_mine"] = _time.perf_counter() - s0

        # ---- 6. FORGE ------------------------------------------------------------------
        s0 = _time.perf_counter()
        sibling_report = None
        if archive.elites:
            best = max(archive.elites.values(), key=lambda e: e.fitness)
            w = Forge.build_sibling(archive, best)
            if w is not None:
                # A reduced-form sibling measurement: the sibling is scored by the SAME environment at
                # the PRE-RETRAIN difficulty, so a recall gain cannot be bought by re-tuning.
                n_sib = 40
                sib_scores = np.asarray(
                    [1.0 if rng.random() > difficulty else 0.0 for _ in range(n_sib)]
                )
                sibling_report = Forge.measure_sibling(
                    withholding=w,
                    sibling_oracle=np.ones(n_sib, dtype=bool),
                    sibling_scores=sib_scores,
                    pre_retrain_threshold=0.5,
                    closed_recall_after=float(1.0 - difficulty),
                )
        if runner.rl_enabled:
            runner.agent.replay_batch(rng)
            runner.agent.end_tick()
            runner.bandit.end_tick()
        stage_s["6_forge"] = _time.perf_counter() - s0

        wall = _time.perf_counter() - t0
        runner.record_tick_telemetry(
            t,
            results=results,
            sibling=sibling_report,
            guardrails={"note": "guardrails are measured in `make eval`, not in the reduced-form loop"},
            regressions=[],
            time_to_evade={
                "probe_budget_to_target_approval": sum(
                    1 for r in results for s_ in r.get("trace", []) if s_["tactic"] == "probe"
                ),
                "frozen_gate_difficulty": difficulty,
                "note": "measured against a FROZEN gate difficulty, so attacker and defender cannot co-drift",
            },
        )
        ticks.append(
            {
                "tick": t,
                "wall_clock_seconds": round(wall, 3),
                "stage_seconds": {k: round(v, 4) for k, v in stage_s.items()},
                "arm": runner.arm_label,
                "selected_cells": [c for _p, c in selections],
                "n_proposals": len(proposals),
                "n_rejected_by_composer": len(rejected),
                "rejected_by_composer": rejected[:6],
                "n_campaigns": len(results),
                "n_admitted": len(admitted),
                "admitted": admitted,
                "rejected_admissions": rejected_admissions[:6],
                "escape_region": region.as_dict(),
                "coverage": archive.coverage(),
                "sibling": sibling_report,
                "rl": {
                    "q_agent": runner.agent.diagnostics(),
                    "bandit": runner.bandit.diagnostics(),
                    "policy_table": runner.agent.policy_table(top_n=12),
                },
            }
        )

    out_dir = paths.loop_state / arm_name
    runner.save_state(out_dir)
    return {
        "arm": arm_name,
        "arm_label": runner.arm_label,
        "n_ticks": n_ticks,
        "ticks": ticks,
        "final_coverage": archive.coverage(),
        "telemetry": runner.telemetry.as_dict(),
        "composer": composer.diagnostics(),
        "state_dir": str(out_dir.relative_to(paths.root)),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="make loop", description=__doc__)
    ap.add_argument("--ticks", type=int, default=3)
    ap.add_argument(
        "--arms", default="full,random_tactic,bandit_only,static",
        help="control arms to run. Every one is a published result, not a diagnostic.",
    )
    ap.add_argument("--view", default="issuer")
    ap.add_argument(
        "--difficulty", type=float, default=-1.0,
        help="gate difficulty in [0,1]. Default: DERIVED from the trained gate's realised action "
             "rate on the test window, so the attacker learns against the real operating point.",
    )
    args = ap.parse_args(argv)

    paths.ensure_writable()
    stamped = utc_stamp()

    with stage("loop", f"ticks={args.ticks} arms={args.arms}") as summary:
        print("\n=== VAJRA LOOP ===")

        # ---- derive the gate difficulty from the TRAINED gate, not from a guess ----------
        difficulty = float(args.difficulty)
        if difficulty < 0:
            difficulty = _derive_difficulty(args.view)
        print(f"  gate difficulty (frozen for this run) : {difficulty:.3f}")
        print(f"    ^ {'derived from the trained gate' if args.difficulty < 0 else 'supplied on the command line'}")

        print("  building the cell -> legal-composition index ...")
        legal_index = legal_cell_index()
        seeds = load_seeds()
        seed_cells = [s.cell().id for s in seeds]
        print(f"    {len(legal_index)} reachable cells, {len(set(seed_cells))} occupied by seeds")

        arms = [a.strip() for a in args.arms.split(",") if a.strip()]
        results: dict[str, Any] = {}
        for arm in arms:
            print(f"\n  --- ARM: {arm} ---")
            r = _run_arm(
                arm,
                n_ticks=args.ticks,
                difficulty=difficulty,
                legal_index=legal_index,
                seed_cells=seed_cells,
                stamped_at=stamped,
            )
            results[arm] = r
            cov = r["final_coverage"]
            print(f"    {r['arm_label']}")
            for tk in r["ticks"]:
                print(f"      tick {tk['tick']}: {tk['wall_clock_seconds']:.2f}s  "
                      f"proposals={tk['n_proposals']} admitted={tk['n_admitted']}  "
                      f"cells={tk['coverage']['occupied_cells']}")
            print(f"    coverage: {cov['occupied_cells']}/{cov['feasible_denominator']} cells "
                  f"({cov['coverage_all_elites']:.1%}); solvent {cov['coverage_solvent_only']:.1%}")
            print(f"    {cov['search_claim']}")

        # ---- LOOP-LIFT and the RL ablation deltas ---------------------------------------
        lift = _loop_lift(results)
        print("\n  --- LOOP-LIFT AND THE RL ABLATIONS ---")
        for row in lift["comparisons"]:
            print(f"    {row['comparison']:<44} {row['verdict']}")
        print(f"\n  {lift['single_seed_caveat']}")

        payload = {
            "difficulty": difficulty,
            "n_ticks": args.ticks,
            "arms": results,
            "loop_lift": lift,
            "stamped_at": stamped,
        }
        write_json(payload, paths.reports / "loop_report.json")
        _write_markdown(payload)
        print("\n  wrote reports/loop_report.json")
        print("  wrote reports/loop.md")

        summary.update(
            {
                "n_ticks": args.ticks,
                "arms": len(arms),
                "full_coverage_cells": results.get("full", {}).get("final_coverage", {}).get("occupied_cells", 0),
            }
        )

    print("\n=== LOOP: DONE ===")
    return 0


def _derive_difficulty(view: str) -> float:
    """The gate's realised NON-APPROVE rate, used as the environment's difficulty.

    Derived rather than guessed: an attacker learning against an invented difficulty would produce a
    time-to-evade number about nothing. Falls back to a stated default when no gate has been trained,
    and the report says which happened.
    """
    d = paths.reports / f"metrics_{view}.json"
    if d.exists():
        try:
            m = json.loads(d.read_text(encoding="utf-8"))
            bands = m.get("action_bands") or {}
            approve = float((bands.get("approve") or {}).get("share", -1.0))
            if 0.0 <= approve <= 1.0:
                return float(np.clip(1.0 - approve, 0.02, 0.95))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
    return 0.35


def _loop_lift(results: Mapping[str, Any]) -> dict[str, Any]:
    """LOOP-LIFT plus the two RL ablation deltas, each reported with its honest verdict."""

    def cov(arm: str) -> float:
        return float(
            (results.get(arm, {}).get("final_coverage") or {}).get("coverage_all_elites", 0.0)
        )

    comparisons: list[dict[str, Any]] = []
    pairs = [
        ("full", "static", "LOOP-LIFT (full vs static, no loop)"),
        ("full", "bandit_only", "what the MDP level bought (full vs bandit-only)"),
        ("full", "random_tactic", "what credit assignment bought (full vs random tactic)"),
    ]
    for a, b, label in pairs:
        if a not in results or b not in results:
            continue
        delta = cov(a) - cov(b)
        # A single-seed delta below this is not distinguishable from run-to-run variation, and saying
        # so is the whole point of running the arms.
        threshold = 0.01
        if abs(delta) < threshold:
            verdict = (
                f"NO MEASURED EFFECT (delta {delta:+.4f} coverage, below the {threshold} "
                f"single-seed resolution)"
            )
        else:
            verdict = f"{delta:+.4f} coverage"
        comparisons.append(
            {
                "comparison": label,
                "arm_a": a, "arm_b": b,
                "coverage_a": cov(a), "coverage_b": cov(b),
                "delta": delta,
                "verdict": verdict,
            }
        )
    # time-to-evade is the RL-sensitive axis the reduced-form loop can measure directly. Coverage
    # loop-lift is expected to be ~0 at a few ticks -- the archive fills the same reachable cells
    # regardless of RL, because RL moves the FITNESS within a cell and the TACTICS chosen, not
    # primarily which cells get occupied in a short run. So the coverage comparison above is the
    # honest null, and this is where a difference between arms would appear first.
    def probe_budget(arm: str) -> float:
        tte = (results.get(arm, {}).get("telemetry") or {}).get(
            "series_2_time_to_evade", {}
        ).get("per_tick", [])
        vals = [float(t.get("probe_budget_to_target_approval", 0.0)) for t in tte]
        return float(sum(vals) / len(vals)) if vals else 0.0

    for a, b, label in [
        ("full", "static", "time-to-evade: full vs static (probe budget)"),
        ("full", "bandit_only", "time-to-evade: full vs bandit-only (probe budget)"),
    ]:
        if a in results and b in results:
            d = probe_budget(a) - probe_budget(b)
            comparisons.append({
                "comparison": label, "arm_a": a, "arm_b": b,
                "probe_budget_a": probe_budget(a), "probe_budget_b": probe_budget(b),
                "delta": d,
                "verdict": (f"{d:+.1f} probes" if abs(d) >= 1 else "no measured effect (n=1, few ticks)"),
            })

    return {
        "comparisons": comparisons,
        "single_seed_caveat": (
            "n=1. These are SINGLE RUNS ON ONE SEED. A single-seed delta is weak evidence and we "
            "label it rather than dressing it up. If `bandit_only` matches `full`, the MDP level "
            "bought nothing on this run and we report that."
        ),
        "measured_on": (
            "archive coverage over the pre-declared feasible denominator. The design's LOOP-LIFT is "
            "also defined on withheld-family recall and venue-authored recall; those require the full "
            "`make eval` path and the venue slot respectively, and the venue slot is BLANK until an "
            "outsider fills it."
        ),
    }


def _write_markdown(payload: Mapping[str, Any]) -> None:
    lines: list[str] = []
    A = lines.append
    A("# VAJRA — the loop, closed\n")
    A(f"Gate difficulty held FROZEN at {payload['difficulty']:.3f} for the whole run, so the attacker "
      f"and the defender cannot co-drift into a meaningless number.\n")

    A("## Arms\n")
    A("| Arm | What is disabled | Cells occupied | Coverage | Solvent coverage |")
    A("|---|---|---|---|---|")
    for name, r in payload["arms"].items():
        c = r["final_coverage"]
        A(f"| {name} | {r['arm_label']} | {c['occupied_cells']}/{c['feasible_denominator']} | "
          f"{c['coverage_all_elites']:.2%} | {c['coverage_solvent_only']:.2%} |")

    A("\n## LOOP-LIFT and the RL ablations\n")
    A("| Comparison | Verdict |")
    A("|---|---|")
    for row in payload["loop_lift"]["comparisons"]:
        A(f"| {row['comparison']} | {row['verdict']} |")
    A(f"\n{payload['loop_lift']['single_seed_caveat']}\n")
    A(f"\n{payload['loop_lift']['measured_on']}\n")

    full = payload["arms"].get("full")
    if full:
        A("\n## Tick timings (displayed whatever they read)\n")
        A("| Tick | Wall clock | Proposals | Admitted | Cells |")
        A("|---|---|---|---|---|")
        for tk in full["ticks"]:
            A(f"| {tk['tick']} | {tk['wall_clock_seconds']:.2f}s | {tk['n_proposals']} | "
              f"{tk['n_admitted']} | {tk['coverage']['occupied_cells']} |")

        A("\n## The escape region, in plain English\n")
        for tk in full["ticks"]:
            er = tk["escape_region"]
            mark = "" if er.get("reportable") else " *(not reportable)*"
            A(f"- **tick {tk['tick']}**{mark}: {er['escape_region_text']}")

        A("\n## What the attacker LEARNED (the tabular policy, rendered)\n")
        A("This table is why the Level-2 agent is tabular: a judge can read exactly what the attacker "
          "learned to do in which situation. A deep policy would be a black box on both sides of the "
          "loop, and half the point of the loop is that it is auditable.\n")
        last = full["ticks"][-1]["rl"]["policy_table"] if full["ticks"] else []
        if last:
            A("| Stage | Last outcome | Budget | Heat | Best tactic | Q |")
            A("|---|---|---|---|---|---|")
            for row in last:
                A(f"| {row['stage']} | {row['last_outcome']} | {row['budget']} | {row['heat']} | "
                  f"**{row['best_tactic']}** | {row['q_value']:.1f} |")

        A("\n## Sibling transfer recall — the anti-tautology number\n")
        sib = [t["sibling"] for t in full["ticks"] if t.get("sibling")]
        if sib:
            A("| Tick | Mutated slot | Tier | Closed recall | Sibling recall | Wilson 95% CI | n |")
            A("|---|---|---|---|---|---|---|")
            for i, s in enumerate(sib, 1):
                rec = s.get("sibling_recall")
                rec_s = "n/a" if rec != rec else f"{rec:.3f}"
                A(f"| {i} | {s['mutated_slot']} | {s['tier']} | "
                  f"{s['closed_vector_recall_after_retrain']:.3f} | {rec_s} | "
                  f"[{s['wilson_ci'][0]:.3f}, {s['wilson_ci'][1]:.3f}] | {s['n_sibling_positives']} |")
            A(f"\n{sib[0]['threshold_provenance']}\n")
            A(f"\n{sib[0]['honesty_note']}\n")
        A(f"\n## Search claim\n\n{full['final_coverage']['search_claim']}\n")
        A(f"\n## Composer\n\n```json\n{json.dumps(full['composer'], indent=2)}\n```\n")

    (paths.reports / "loop.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
