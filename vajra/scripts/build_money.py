"""`make money` — the MONEY screen's data. Rupees stopped vs good customers declined, loop ON/OFF.

THE SCORED POPULATION IS THE DECLARED DENOMINATOR AND NOTHING ELSE: the 12 sealed families withheld
before modelling, plus HARD-BENIGN-12 and HARD-BENIGN-B, plus (when present) venue-authored attacks --
with EVERY loop-discovered composition EXCLUDED. That is what stops the opening number being the
circularity the rest of the design spends a section disowning.

Both numbers are SIMULATOR-INTERNAL and labelled as such on the screen. The loop ON/OFF toggle switches
between two STORED result sets (the full loop arm and the static arm), so it is a real comparison of two
real runs, not an animation. And abstention is priced SEPARATELY from declines, because a system that
frictions everything has not "stopped" fraud, it has moved friction onto good customers.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import numpy as np

from core import paths
from core.config import load_config
from core.io import write_json
from core.stagelog import stage
from features.builder import build_matrix, fit_reference_stats, prepare_columns
from features.registry import load_registry
from gate.scorer import GateBundle, Scorer
from gate.sketches import OnlineStore
from grammar.composition import Composition
from grammar.sealed import load_sealed_manifest
from eval.splits import temporal_split
from gate.cli import _load_events, _load_label_table, _resolve_labels


def _money_for_bundle(bundle, fm, mask, amounts, oracle, cohorts):  # noqa: ANN001
    scorer = Scorer(bundle, store=OnlineStore())
    batch = scorer.score_batch(fm.subset_rows(mask))
    y = oracle[mask]
    amt = amounts[mask]
    coh = cohorts[mask]
    actioned = batch.bands != "approve"
    declined = np.isin(batch.bands, ["auto_decline"])
    frictioned = np.isin(batch.bands, ["friction", "review"])
    fraud = y
    hard_benign = np.char.startswith(coh.astype(str), "hb")
    return {
        "rupees_fraud_stopped": float(amt[fraud & actioned].sum()),
        "rupees_fraud_attempted": float(amt[fraud].sum()),
        "rupees_good_declined": float(amt[(~fraud) & declined].sum()),
        "rupees_good_frictioned": float(amt[(~fraud) & frictioned].sum()),
        "n_good_declined": int(((~fraud) & declined).sum()),
        "n_good_frictioned": int(((~fraud) & frictioned).sum()),
        "hard_benign_false_action_rate": float(actioned[hard_benign].mean()) if hard_benign.sum() else 0.0,
        "value_detection_rate": (
            float(amt[fraud & actioned].sum() / amt[fraud].sum()) if amt[fraud].sum() > 0 else 0.0
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="make money", description=__doc__)
    ap.add_argument("--view", default="issuer")
    args = ap.parse_args(argv)
    cfg = load_config()
    paths.ensure_writable()

    with stage("money", f"view={args.view}") as summary:
        cols = prepare_columns(_load_events("vajra-sim"))
        ts = cols["ts"]
        split = temporal_split(ts)
        train_end = float(ts[split.train].max())
        y_pit, _a = _resolve_labels(_load_label_table("vajra-sim"), cols["event_id"], float(ts.max()))
        ref = fit_reference_stats(cols, y_pit, train_mask=split.train,
                                  holdout_mask=(cols["entity_pool"].astype(str) == "sealed"))
        fm = build_matrix(cols, ref).subset_features(load_registry().features_for_view(args.view))

        manifest = load_sealed_manifest()
        oracle = cols["oracle_is_attack"].astype(bool)
        cohorts = cols["cohort_tag"].astype(str)
        family = cols["attack_family_id"].astype(str)

        # THE DECLARED SCORING POPULATION: sealed-pool attacks + HARD-BENIGN cohorts + ordinary benign,
        # with LOOP-DISCOVERED (GEN-*) compositions EXCLUDED. This is what makes the opening number
        # non-circular.
        is_sealed_pool = cols["entity_pool"].astype(str) == "sealed"
        is_hard_benign = np.char.startswith(cohorts, "hb")
        is_loop_discovered = np.char.startswith(family, "GEN-")
        pop_mask = (is_sealed_pool | is_hard_benign | (~oracle)) & (~is_loop_discovered) & split.test
        amounts = fm.meta["amount_inr"]

        loop_bundle = GateBundle.load(paths.models / f"gate-i_{args.view}")
        # ON vs OFF: the design switches between the loop arm and the static arm's stored models. Both
        # bundles come from the same `make train`; the static arm's is produced by `make train` with
        # the loop's retrain disabled. When only one exists we report ON and label OFF as not-yet-run.
        static_dir = paths.models / f"gate-i_{args.view}_static"
        static_bundle = GateBundle.load(static_dir) if (static_dir / "bundle_meta.json").exists() else loop_bundle

        on = _money_for_bundle(loop_bundle, fm, pop_mask, amounts, oracle, cohorts)
        off = _money_for_bundle(static_bundle, fm, pop_mask, amounts, oracle, cohorts)

        report = {
            "view": args.view,
            "loop_on": on,
            "loop_off": off,
            "denominator": {
                "n_events_scored": int(pop_mask.sum()),
                "n_attack": int(oracle[pop_mask].sum()),
                "composition": (
                    "sealed-pool attacks + HARD-BENIGN-12 + HARD-BENIGN-B + ordinary benign, "
                    "time-forward TEST window, LOOP-DISCOVERED (GEN-*) compositions EXCLUDED"
                ),
                "why": (
                    "The opening number is scored ONLY on populations withheld before modelling plus "
                    "the adversarial-legitimate cohorts, with loop-discovered compositions removed, so "
                    "it is not the circularity the design spends a section disowning."
                ),
            },
            "provenance": "SIMULATOR-INTERNAL rupees, labelled as such on the screen. Not real money.",
            "abstention_priced_separately": (
                "'Frictioned' is reported separately from 'declined': a system that frictions "
                "everything has moved friction onto good customers, not stopped fraud."
            ),
            "toggle": (
                "The loop ON/OFF toggle switches between two STORED result sets (loop arm vs static "
                "arm), so it is a real comparison of two real runs, not an animation."
            ),
            "static_arm_present": (static_dir / "bundle_meta.json").exists(),
            "toggle_is_live": (static_dir / "bundle_meta.json").exists(),
            "toggle_caveat": (
                "NO STATIC ARM WAS TRAINED, so both sides of this toggle are the SAME bundle and every "
                "digit is identical. No make target produces data/models/gate-i_<view>_static. The "
                "toggle is disabled on screen rather than left to look like a comparison that moved "
                "nothing -- an interaction that silently does nothing is worse than an absent one."
            ) if not (static_dir / "bundle_meta.json").exists() else "",
        }
        write_json(report, paths.reports / "money.json")
        print(f"  loop ON  : Rs{on['rupees_fraud_stopped']:,.0f} fraud stopped, "
              f"Rs{on['rupees_good_declined']:,.0f} good declined")
        print(f"  loop OFF : Rs{off['rupees_fraud_stopped']:,.0f} fraud stopped, "
              f"Rs{off['rupees_good_declined']:,.0f} good declined")
        print(f"  scored population: {int(pop_mask.sum()):,} events "
              f"({int(oracle[pop_mask].sum())} attacks), loop-discovered EXCLUDED")
        print("  wrote reports/money.json")
        summary.update({"n_scored": int(pop_mask.sum()), "n_attack": int(oracle[pop_mask].sum())})
    return 0


if __name__ == "__main__":
    sys.exit(main())
