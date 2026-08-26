"""`make diagnose-bands` — per-rail band diagnosis for a candidate fusion arm, off the cached
components, so it costs seconds rather than a retrain.

WHY: committing the `g1_only` arm at the full preset collapsed the ladder on two rails
(`agentic-commerce`, `card-clearing-dispute`), each reporting BOTH `review == friction` and
`decline == review`. That specific double-collapse has exactly one cause, visible in
gate/policy.py:393-412: `t_friction` is fitted PER RAIL from that rail's friction cap, while
`t_review` and `t_decline` are GLOBAL, and `_enforce_ordering` reconciles a conflict by raising
review and decline UP to meet friction. So any rail whose own friction-cap quantile sits above the
global decline threshold loses both its friction band and its review band at once, and every row it
would have frictioned is DECLINED instead.

That is a policy change, not a cosmetic one, so it needs the volumes before anyone decides. This
prints, per rail: how much of the calibration window the rail is, how many distinct scores it has,
its thresholds, and the share of its traffic landing in each band -- plus the same table for the
CURRENTLY SHIPPED arm, so the comparison is like-for-like.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from core import paths
from core.config import load_config
from core.io import write_json
from gate.fusion import COMPONENTS, Fusion
from gate.policy import ActionTable, CostMatrix
from scripts.refit_fusion import _arms, load_components


def _fit(d: dict, arm: dict) -> tuple[Fusion, ActionTable, np.ndarray, np.ndarray, np.ndarray]:
    cfg = load_config()
    comps = {c: d[f"stats__{c}"] for c in COMPONENTS}
    y = d["stats__y_pit"].astype(int)
    f = Fusion(weights=dict(arm["weights"]), tail_transform=bool(arm.get("tail")))
    f = f.fit(comps, labels=np.where(y < 0, -1, y))
    s = f.score(comps)
    rails = np.asarray([str(x) for x in d["stats__rail"]], dtype=object)
    at = ActionTable.fit(
        s, rails.tolist(), d["stats__amount_inr"].astype(np.float64),
        np.where(y < 0, -1.0, y.astype(float)),
        cfg=cfg, costs=CostMatrix.from_config(cfg),
        population_label=f"diagnosis (arm={arm['name']})",
    )
    return f, at, s, rails, y


def _table(at: ActionTable, s: np.ndarray, rails: np.ndarray, y: np.ndarray, label: str) -> list[dict]:
    n = s.size
    print(f"\n  === {label} ===")
    print(f"    global: friction {at.global_t_friction:.6g}  review {at.global_t_review:.6g}  "
          f"decline {at.global_t_decline:.6g}")
    print(f"    {'rail':<26}{'n':>9}{'% vol':>7}{'distinct':>9}{'t_fric':>9}{'t_rev':>9}"
          f"{'t_dec':>9}{'appr%':>7}{'fric%':>7}{'rev%':>6}{'dec%':>6}{'pos':>6}  flag")
    rows = []
    for rail in sorted(set(rails.tolist())):
        m = rails == rail
        sm = s[m]
        fri, rev, dec = at.t_friction[rail], at.t_review[rail], at.t_decline[rail]
        d_ = float((sm >= dec).mean())
        r_ = float(((sm >= rev) & (sm < dec)).mean())
        f_ = float(((sm >= fri) & (sm < rev)).mean())
        a_ = float((sm < fri).mean())
        bad = []
        if abs(rev - fri) <= 1e-12:
            bad.append("REV==FRI")
        if abs(dec - rev) <= 1e-12:
            bad.append("DEC==REV")
        rec = {
            "rail": rail, "n": int(m.sum()), "volume_share": float(m.mean()),
            "n_distinct_scores": int(np.unique(sm).size),
            "t_friction": float(fri), "t_review": float(rev), "t_decline": float(dec),
            "approve_share": a_, "friction_share": f_, "review_share": r_, "decline_share": d_,
            "visible_positives": int((y[m] == 1).sum()), "collapsed": bad,
        }
        rows.append(rec)
        print(f"    {rail:<26}{rec['n']:>9,}{rec['volume_share']*100:>7.2f}"
              f"{rec['n_distinct_scores']:>9,}{fri:>9.4f}{rev:>9.4f}{dec:>9.4f}"
              f"{a_*100:>7.2f}{f_*100:>7.2f}{r_*100:>6.2f}{d_*100:>6.2f}"
              f"{rec['visible_positives']:>6,}  {','.join(bad)}")
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="make diagnose-bands", description=__doc__)
    ap.add_argument("--view", default="issuer")
    ap.add_argument("--arm", default="g1_only")
    ap.add_argument("--against", default="current", help="arm to compare with (the shipped one)")
    args = ap.parse_args(argv)

    d = load_components(args.view)
    arms = {a["name"]: a for a in _arms()}
    for name in (args.arm, args.against):
        if name not in arms:
            raise SystemExit(f"unknown arm {name!r}; expected one of {sorted(arms)}")

    print("\n=== VAJRA BAND DIAGNOSIS — per rail, off the cached components ===")
    out = {"view": args.view}
    for name in (args.against, args.arm):
        _f, at, s, rails, y = _fit(d, arms[name])
        out[name] = {
            "global": {"t_friction": at.global_t_friction, "t_review": at.global_t_review,
                       "t_decline": at.global_t_decline},
            "rails": _table(at, s, rails, y, f"arm = {name}"),
            "band_distinctness": at.assert_bands_distinct(),
        }

    coll = [r for r in out[args.arm]["rails"] if r["collapsed"]]
    print(f"\n  --- VERDICT for arm={args.arm} ---")
    if not coll:
        print("    no rail collapsed.")
    else:
        vol = sum(r["volume_share"] for r in coll)
        pos = sum(r["visible_positives"] for r in coll)
        print(f"    {len(coll)} rail(s) collapsed, together {vol:.4%} of the calibration window "
              f"and {pos:,} visible positives:")
        for r in coll:
            print(f"      {r['rail']:<26} n={r['n']:,} ({r['volume_share']:.4%})  "
                  f"t_friction {r['t_friction']:.4f} vs global decline "
                  f"{out[args.arm]['global']['t_decline']:.4f}  "
                  f"-> {r['decline_share']:.2%} of the rail auto-declines, "
                  f"{r['friction_share']:.2%} frictioned")
        print("\n    READ IT THIS WAY. The collapse means these rails lost their friction AND review")
        print("    bands, so traffic that would have been frictioned is DECLINED. If the volume above")
        print("    is negligible this is the documented tiny-population case (gate/policy.py:419).")
        print("    If it is not negligible, the per-rail friction threshold must be reconciled with")
        print("    the global ladder rather than overridden.")

    write_json(out, paths.reports / f"band_diagnosis_{args.view}.json")
    print(f"\n  wrote reports/band_diagnosis_{args.view}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
