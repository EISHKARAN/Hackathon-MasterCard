"""MAP-Elites over the four behaviour axes. THE ARCHIVE IS THE SEARCH; THE SIMULATOR IS THE FITNESS.

Mouret & Clune (arXiv:1504.04909, 2015). The property we want is ILLUMINATION — mapping what is
*possible* across a behaviour space — not optimisation toward one best solution. That is why the
archive holds ONE ELITE PER CELL, and why occupied cells and archived elites are THE SAME INTEGER by
construction. Any pair of targets implying otherwise is arithmetically dead on arrival, so CI asserts
`occupied_cells == len(elites)`.

In reinforcement-learning vocabulary this is an AUTOMATIC CURRICULUM GENERATOR: it maintains a
population of tasks (cells), tracks the best solution in each, and biases sampling toward
under-explored regions. It is not itself RL, and calling it RL would be wrong — the learner is the
Level-2 Q(λ) agent and the Level-1 bandit in `attack/rl/`.

DYNAMIC QD (Gallotta, Liapis & Yannakakis, GECCO 2024): the defender retrains, so an elite's fitness
is NOT stationary. Elites are re-evaluated after each FORGE stage rather than trusting a stale
fitness, and `reevaluate_elites_after_forge` in config/rl.yaml controls the sample size.

RUIN IS A PENALTY PLUS A FLAG, NEVER A DELETION. Killing a ruined elite would make coverage a
DISCONTINUOUS FUNCTION OF COST CONSTANTS WE ADMIT ARE GUESSED: cells whose only viable attacks are
expensive would stay permanently empty, and the headline diversity integer would move for an economic
reason dressed up as a diversity result. So coverage is reported TWICE — all elites, and solvent
elites only — and the 0.33x/1x/3x mule-cost sweep moves a number instead of emptying cells.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from core.config import Config, load_config
from core.rng import stream
from grammar.cell_of import Cell, admissible_depths, cell_of, mutation_effect
from grammar.composition import SLOT_ORDER, Composition, load_slots
from grammar.feasibility import load_feasibility
from grammar.typecheck import load_typechecker


@dataclass
class Elite:
    """One archived elite: the best composition found for its cell, with its measured behaviour."""

    cell_id: str
    composition: str
    stages: tuple[str, ...]
    family_id: str
    #: Attacker P&L. THE fitness. See config/cost_matrix.yaml for why the constants are assumptions.
    fitness: float
    value_retained_inr: float
    cost_inr: float
    #: `ruined` is a FLAG, not a death sentence. See the module docstring.
    ruined: bool = False
    ruin_trigger: str = ""
    #: Detection latency versus time-to-break-even, in sim hours. The ruin comparison, kept so the
    #: report can show WHY an elite was flagged rather than only that it was.
    detection_latency_hours: float = -1.0
    break_even_hours: float = -1.0
    #: How many times this cell has been evaluated. Below ~10 we stop calling it MAP-Elites.
    evaluations: int = 0
    #: Mean detector-attribution distribution, the input to the distinctness test.
    attribution: Mapping[str, float] = field(default_factory=dict)
    #: Measured observable delta: mean shift this composition produces in the feature vector.
    observable_delta: float = 0.0
    n_events: int = 0
    caught_share: float = 0.0
    #: True when this elite was first PROPOSED BY THE COMPOSER from a Gap Miner escape region AND
    #: occupies a cell no seed composition occupied. Both conditions, computed — not curated.
    emergent_hybrid: bool = False
    discovered_tick: int = 0
    sealed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "composition": self.composition,
            "stages": list(self.stages),
            "family_id": self.family_id,
            "fitness": self.fitness,
            "value_retained_inr": self.value_retained_inr,
            "cost_inr": self.cost_inr,
            "ruined": self.ruined,
            "ruin_trigger": self.ruin_trigger,
            "detection_latency_hours": self.detection_latency_hours,
            "break_even_hours": self.break_even_hours,
            "evaluations": self.evaluations,
            "attribution": dict(self.attribution),
            "observable_delta": self.observable_delta,
            "n_events": self.n_events,
            "caught_share": self.caught_share,
            "emergent_hybrid": self.emergent_hybrid,
            "discovered_tick": self.discovered_tick,
            "sealed": self.sealed,
            "solvent": self.solvent,
        }

    @property
    def solvent(self) -> bool:
        """Reaches break-even before its ruin trigger.

        Coverage is reported over ALL elites and over SOLVENT elites only, so the economic sweep
        moves a number rather than silently emptying cells.
        """
        return (not self.ruined) and self.fitness > 0.0


class Archive:
    """The MAP-Elites grid. One elite per cell, by construction."""

    def __init__(self, cfg: Config | None = None) -> None:
        self.cfg = cfg or load_config()
        self.elites: dict[str, Elite] = {}
        self.feasible: set[str] = {c.id for c in load_feasibility().feasible()}
        #: Cells the GRAMMAR CAN ACTUALLY REACH. Selection targets these; COVERAGE is still reported
        #: over the full feasible denominator, because that is the honest denominator and shrinking it
        #: to what we can reach would be exactly the self-flattering move the design refuses.
        #: `set_reachable()` is called by the loop with the cell -> legal-composition index; until then
        #: the reachable set is the feasible set, so a caller that forgets degrades to the old
        #: behaviour rather than silently selecting nothing.
        self.reachable: set[str] = set(self.feasible)
        self.rng = stream("archive.mapelites")
        #: Every evaluation ever, per cell, so the "evaluations per occupied cell" budget is a
        #: MEASURED number rather than an intention.
        self.evaluations_per_cell: dict[str, int] = {}
        #: Cells occupied by SEED compositions, needed for the emergent-hybrid test.
        self.seed_cells: set[str] = set()
        self.tick: int = 0

    # ---- invariants -------------------------------------------------------------------
    def assert_one_elite_per_cell(self) -> None:
        """`occupied_cells == len(elites)`. THE arithmetic identity the diversity claim rests on."""
        occupied = len({e.cell_id for e in self.elites.values()})
        if occupied != len(self.elites):
            raise AssertionError(
                f"MAP-Elites holds ONE elite per cell, so occupied cells ({occupied}) and archived "
                f"elites ({len(self.elites)}) must be the same integer. They are not, which means "
                f"the diversity accounting is broken and every coverage figure derived from it is "
                f"wrong."
            )

    # ---- admission --------------------------------------------------------------------
    def try_admit(self, candidate: Elite) -> tuple[bool, str]:
        """Admit if the cell is feasible and the candidate beats the incumbent elite.

        Returns `(admitted, reason)`. The reason is carried into the tick telemetry so a rejected
        candidate is visible: an archive that silently discards is an archive whose count nobody can
        audit.
        """
        self.evaluations_per_cell[candidate.cell_id] = (
            self.evaluations_per_cell.get(candidate.cell_id, 0) + 1
        )
        if candidate.cell_id not in self.feasible:
            return False, "cell is pre-marked INFEASIBLE in grammar/feasible_cells.yaml"
        incumbent = self.elites.get(candidate.cell_id)
        candidate.evaluations = self.evaluations_per_cell[candidate.cell_id]
        if incumbent is None:
            candidate.emergent_hybrid = self._is_emergent_hybrid(candidate)
            self.elites[candidate.cell_id] = candidate
            return True, "cell was empty"
        if candidate.fitness > incumbent.fitness:
            candidate.emergent_hybrid = self._is_emergent_hybrid(candidate)
            candidate.evaluations = self.evaluations_per_cell[candidate.cell_id]
            self.elites[candidate.cell_id] = candidate
            return True, f"fitness {candidate.fitness:.1f} beats incumbent {incumbent.fitness:.1f}"
        incumbent.evaluations = self.evaluations_per_cell[candidate.cell_id]
        return False, f"fitness {candidate.fitness:.1f} does not beat incumbent {incumbent.fitness:.1f}"

    def _is_emergent_hybrid(self, e: Elite) -> bool:
        """MECHANICAL definition, not a curatorial one.

        An elite is an emergent hybrid iff BOTH: it was first proposed by the Composer from a Gap
        Miner escape region (family id prefixed GEN-), AND it occupies a cell no seed composition
        occupied. The `docs/` write-ups are selected from the machine-produced candidate list, and if
        the flag never fires we ship ZERO write-ups and say so rather than promoting a mechanically
        expanded composition.
        """
        return bool(e.family_id.startswith("GEN-") and e.cell_id not in self.seed_cells)

    def register_seed_cells(self, cells: Iterable[str]) -> None:
        self.seed_cells.update(cells)

    def set_reachable(self, cell_ids: Iterable[str]) -> None:
        """Restrict SELECTION to cells the grammar can occupy.

        Selecting a feasible-but-unreachable cell wastes an evaluation: no type-legal composition can
        occupy it, so the Composer has nothing to propose and the tick produces nothing. Coverage
        continues to be reported over the FULL feasible denominator — the unreachable remainder is
        published as honest headroom and is the slot-extension target list.
        """
        r = {c for c in cell_ids if c in self.feasible}
        self.reachable = r or set(self.feasible)

    # ---- selection: the curriculum -----------------------------------------------------
    def select_parent(self) -> tuple[Elite | None, str]:
        """Pick a parent elite, or name an under-filled cell to target.

        Returns `(parent_or_None, target_cell_id)`. Biased toward UNDER-OCCUPIED feasible cells and
        toward HIGH-P&L elites, per `config/rl.yaml::curriculum`. That bias IS the curriculum: without
        it the search concentrates where it already succeeds and coverage stops growing.
        """
        empty = sorted(self.reachable - set(self.elites))
        bias = float(_curriculum_cfg().get("under_occupied_bias", 0.55))
        if empty and self.rng.random() < bias:
            target = empty[int(self.rng.integers(0, len(empty)))]
            return None, target
        if not self.elites:
            if not empty:
                return None, ""
            return None, empty[int(self.rng.integers(0, len(empty)))]
        temp = float(_curriculum_cfg().get("pnl_selection_temperature", 0.8))
        elites = list(self.elites.values())
        f = np.asarray([e.fitness for e in elites], dtype=np.float64)
        # Softmax over standardised fitness, so selection pressure is scale-free: the P&L constants
        # are assumptions, and a selection rule sensitive to their absolute magnitude would make the
        # archive's contents a function of a guess.
        if f.size > 1 and float(np.std(f)) > 1e-9:
            z = (f - f.mean()) / (np.std(f) + 1e-9)
        else:
            z = np.zeros_like(f)
        w = np.exp(z / max(temp, 1e-6))
        w = w / w.sum()
        pick = elites[int(self.rng.choice(len(elites), p=w))]
        return pick, pick.cell_id

    # ---- mutation ---------------------------------------------------------------------
    def mutate(self, comp: Composition, stages: Sequence[str], n_mutations: int = 1) -> Composition:
        """Mutate morphemes, keeping the result TYPE-LEGAL.

        Rejection-sampled against the compatibility matrix rather than repaired, because a repair
        rule would quietly bias the search toward whatever the repair prefers.
        """
        tc = load_typechecker()
        vocab = load_slots()
        best = comp
        for _ in range(24):
            cand = comp
            for _m in range(max(1, n_mutations)):
                slot = SLOT_ORDER[int(self.rng.integers(0, len(SLOT_ORDER)))]
                values = [v for v in vocab.ids(slot) if v != cand.slot(slot)]
                if not values:
                    continue
                cand = cand.with_slot(slot, values[int(self.rng.integers(0, len(values)))])
            if tc.is_legal(cand) and cand != comp:
                return cand
            best = cand
        return best if tc.is_legal(best) else comp

    def mutate_toward_cell(self, target_cell_id: str, legal_index: Mapping[str, Sequence[str]]) -> str | None:
        """Propose a composition that can actually OCCUPY a target cell.

        Uses the precomputed cell -> legal-compositions index. Mutating blindly and discarding wastes
        the execution budget, and the budget is itself a published metric.
        """
        candidates = legal_index.get(target_cell_id) or []
        if not candidates:
            return None
        return str(candidates[int(self.rng.integers(0, len(candidates)))])

    def sibling_of(
        self, e: Elite, *, prefer_slot: str = "EVASION"
    ) -> tuple[str, str, bool] | None:
        """Construct a ONE-MORPHEME-DIFFERENT sibling. Returns (composition, slot, cell_crossing).

        THE HEADLINE SIBLING IS CROSS-CELL WITH THE EVASION MORPHEME MUTATED — the one slot with an
        identity mapping onto a cell axis, and therefore the one guaranteed to cross a cell. That is
        what makes it the hardest single-morpheme move, rather than a claim that four axes are frozen.
        """
        tc = load_typechecker()
        vocab = load_slots()
        comp = Composition.parse(e.composition)
        order = [prefer_slot] + [s for s in SLOT_ORDER if s != prefer_slot]
        for slot in order:
            for value in vocab.ids(slot):
                if value == comp.slot(slot):
                    continue
                cand = comp.with_slot(slot, value)
                if not tc.is_legal(cand):
                    continue
                if e.stages and admissible_depths(cand) and len(e.stages) not in admissible_depths(cand):
                    continue
                eff = mutation_effect(comp, cand, e.stages or ("establish", "extract"))
                return str(cand), slot, (not eff.cell_preserving)
        return None

    # ---- reporting --------------------------------------------------------------------
    def coverage(self) -> dict[str, Any]:
        self.assert_one_elite_per_cell()
        denom = len(self.feasible)
        all_n = len(self.elites)
        solvent_n = sum(1 for e in self.elites.values() if e.solvent)
        evals = list(self.evaluations_per_cell.values())
        occupied_evals = [self.evaluations_per_cell.get(c, 0) for c in self.elites]
        mean_evals = float(np.mean(occupied_evals)) if occupied_evals else 0.0
        return {
            "feasible_denominator": denom,
            "reachable_cells": len(self.reachable),
            "coverage_ceiling_reachable_over_feasible": (len(self.reachable) / denom) if denom else 0.0,
            "feasible_but_unreachable": denom - len(self.reachable),
            "occupied_cells": all_n,
            "archived_elites": all_n,
            "occupied_equals_elites": True,
            "coverage_all_elites": (all_n / denom) if denom else 0.0,
            "solvent_elites": solvent_n,
            "coverage_solvent_only": (solvent_n / denom) if denom else 0.0,
            "ruined_elites": sum(1 for e in self.elites.values() if e.ruined),
            "emergent_hybrids": sum(1 for e in self.elites.values() if e.emergent_hybrid),
            "total_evaluations": int(sum(evals)),
            "evaluations_per_occupied_cell_mean": mean_evals,
            "search_claim": _search_claim(mean_evals),
            "coverage_note": (
                "Reported TWICE — all elites and solvent elites only — so the 0.33x/1x/3x mule-cost "
                "sweep moves a number instead of silently emptying cells. Ruin is a penalty plus a "
                "flag, never a deletion."
            ),
        }

    def per_cell(self) -> list[dict[str, Any]]:
        return [self.elites[c].as_dict() for c in sorted(self.elites)]

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "tick": self.tick,
                    "coverage": self.coverage(),
                    "elites": self.per_cell(),
                    "evaluations_per_cell": dict(sorted(self.evaluations_per_cell.items())),
                    "seed_cells": sorted(self.seed_cells),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    @classmethod
    def load(cls, path: Path, cfg: Config | None = None) -> "Archive":
        a = cls(cfg)
        d = json.loads(path.read_text(encoding="utf-8"))
        a.tick = int(d.get("tick", 0))
        a.evaluations_per_cell = dict(d.get("evaluations_per_cell") or {})
        a.seed_cells = set(d.get("seed_cells") or [])
        for row in d.get("elites") or []:
            a.elites[row["cell_id"]] = Elite(
                cell_id=row["cell_id"],
                composition=row["composition"],
                stages=tuple(row.get("stages") or ()),
                family_id=row.get("family_id", ""),
                fitness=float(row.get("fitness", 0.0)),
                value_retained_inr=float(row.get("value_retained_inr", 0.0)),
                cost_inr=float(row.get("cost_inr", 0.0)),
                ruined=bool(row.get("ruined", False)),
                ruin_trigger=row.get("ruin_trigger", ""),
                detection_latency_hours=float(row.get("detection_latency_hours", -1.0)),
                break_even_hours=float(row.get("break_even_hours", -1.0)),
                evaluations=int(row.get("evaluations", 0)),
                attribution=dict(row.get("attribution") or {}),
                observable_delta=float(row.get("observable_delta", 0.0)),
                n_events=int(row.get("n_events", 0)),
                caught_share=float(row.get("caught_share", 0.0)),
                emergent_hybrid=bool(row.get("emergent_hybrid", False)),
                discovered_tick=int(row.get("discovered_tick", 0)),
                sealed=bool(row.get("sealed", False)),
            )
        return a


def _search_claim(mean_evals: float) -> str:
    """WHAT WE ARE ALLOWED TO CALL THIS, given the realised execution budget.

    Quality-diversity search with two samples per cell is not search: each cell's "elite" is simply
    its only occupant, attacker P&L selects nothing and the ruin condition never binds. So the claim
    downgrades itself rather than being defended.
    """
    if mean_evals >= 25.0:
        return (
            f"MAP-Elites quality-diversity optimisation at {mean_evals:.1f} evaluations per occupied "
            f"cell, at or above the >=25 budget."
        )
    if mean_evals >= 10.0:
        return (
            f"MAP-Elites optimisation at {mean_evals:.1f} evaluations per occupied cell — below the "
            f">=25 budget, so selection pressure is weaker than intended and the coverage trend "
            f"carries less weight."
        )
    return (
        f"AT {mean_evals:.1f} EVALUATIONS PER OCCUPIED CELL WE DO NOT CALL THIS MAP-ELITES "
        f"OPTIMISATION. It is a TYPED ENUMERATION WITH P&L ANNOTATION — still a defensible artifact, "
        f"but a different claim, and the coverage figure must be read as a count of compositions that "
        f"executed rather than as the output of a search."
    )


def _curriculum_cfg() -> dict[str, Any]:
    import yaml

    from core.paths import paths

    with (paths.config / "rl.yaml").open("r", encoding="utf-8") as fh:
        return dict((yaml.safe_load(fh) or {}).get("curriculum") or {})
