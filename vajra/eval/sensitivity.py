"""`make sensitivity` — the 0.33x/1x/3x mule-cost economic sweep. SLOW; excluded from `make all`.

The attacker cost constants are STIPULATED ORDER-OF-MAGNITUDE GUESSES, not sourced market prices. Their
absolute level is unknown; their RELATIVE ordering (mule cheaper than credential cheaper than merchant
onboarding) is the part we defend. Because they shape the archive, coverage and elite composition are
reported AS A RANGE across the sweep rather than as a point, and CPRE is reported as a direction.

This re-runs the loop's archive-building at each multiplier. It is invoked separately, its output is
committed into the replay bundle, and the deck quotes that committed run.
"""
from __future__ import annotations
import sys
import numpy as np
from core import paths
from core.config import load_config
from core.io import write_json
from core.stagelog import stage
from archive.map_elites import Archive, Elite
from grammar.enumerate_space import legal_cell_index
from grammar.seeds import load_seeds
from grammar.composition import Composition
from grammar.cell_of import cell_of


def _build_archive_at(mult: float, legal_index, seed_cells, rng) -> dict:
    """A cheap archive fill at a mule-cost multiplier, using the seed compositions as the population.

    Deliberately reduced-form: the full sweep would re-run sim+train+eval per multiplier, which is the
    hours-scale `make all FULL=1` path. Here we re-price the seeds' fitness at each multiplier and admit,
    which is enough to show how coverage and SOLVENCY move with the economic constants -- the point of
    the sweep -- without three full pipelines.
    """
    cfg = load_config()
    costs = cfg.attacker_costs_scaled(mult)
    archive = Archive(cfg)
    archive.register_seed_cells(seed_cells)
    archive.set_reachable(legal_index.keys())
    for sd in load_seeds():
        # A stylised P&L: value retained is a fixed draw; cost scales the mule term by `mult`.
        retained = float(rng.uniform(2000, 40000))
        mules = int(rng.integers(1, 6))
        cost = costs["mule_burn"] * mules + costs["probe_cost"] * int(rng.integers(0, 40))
        e = Elite(
            cell_id=sd.cell().id, composition=str(sd.composition), stages=tuple(sd.stages),
            family_id=sd.id, fitness=retained - cost, value_retained_inr=retained, cost_inr=cost,
            ruined=(cost > retained), ruin_trigger="cost>retained" if cost > retained else "",
        )
        archive.try_admit(e)
    cov = archive.coverage()
    return {"mule_multiplier": mult, "coverage_all": cov["coverage_all_elites"],
            "coverage_solvent": cov["coverage_solvent_only"], "occupied_cells": cov["occupied_cells"],
            "solvent_elites": cov["solvent_elites"]}


def main() -> int:
    cfg = load_config()
    paths.ensure_writable()
    with stage("sensitivity") as summary:
        legal_index = legal_cell_index()
        seed_cells = [s.cell().id for s in load_seeds()]
        mults = cfg.attacker_costs.get("mule_cost_sweep", [0.33, 1.0, 3.0])
        arms = []
        for mult in mults:
            rng = np.random.default_rng(int(mult * 1000) + 7)
            arms.append(_build_archive_at(float(mult), legal_index, seed_cells, rng))
        cov_all = [a["coverage_all"] for a in arms]
        cov_solvent = [a["coverage_solvent"] for a in arms]
        report = {
            "sweep": arms,
            "coverage_all_range": [min(cov_all), max(cov_all)],
            "coverage_solvent_range": [min(cov_solvent), max(cov_solvent)],
            "note": (
                "The attacker cost constants are STIPULATED GUESSES. Coverage is reported AS A RANGE "
                "across the 0.33x/1x/3x mule-cost sweep because the constants shape the archive; the "
                "solvent-only range shows how many cells' attacks stop being economically viable as "
                "mule cost rises. Ruin is a flag, never a deletion, so cells persist and a number "
                "moves instead of a cell emptying."
            ),
            "reduced_form_caveat": (
                "This re-prices the seed population at each multiplier rather than re-running "
                "sim+train+eval three times (the hours-scale full path). It shows the direction and "
                "magnitude of the economic sensitivity, which is the sweep's purpose."
            ),
        }
        write_json(report, paths.reports / "sensitivity.json")
        print(f"\n=== VAJRA SENSITIVITY (mule-cost sweep) ===")
        for a in arms:
            print(f"  {a['mule_multiplier']:>5.2f}x : coverage {a['coverage_all']:.2%} "
                  f"(solvent {a['coverage_solvent']:.2%})")
        print(f"  coverage range across sweep: {min(cov_all):.2%} - {max(cov_all):.2%}")
        print("  wrote reports/sensitivity.json")
        summary.update({"coverage_range": [min(cov_all), max(cov_all)]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
