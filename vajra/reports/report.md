# VAJRA — evidence index

> Every number here is a MEASUREMENT from this run. Sections marked 'not generated' need their `make` target run first.

## Grammar (`make grammar`)

- type-legal compositions: **15,271** (of 188,160 raw, 91.9% pruned) — the string-space size, NOT the diversity headline
- feasible cells: **380** / 576 nominal; reachable 268 (ceiling 70.5%)

## Simulator (`make sim`)

- events: **9,899,667** over 120 days, 68170 attacks
- **F1 invariant gate: 0 violations** across 126 invariants — the never-cut gate
- events logical hash: `f78a17b59801bb282198a716dc3004c4`

## Fidelity (`make fidelity`)

- provenance: T1=2 (exactly the two conditionals), T2=4, T3=7
- F1: 0 violations; F3/F5/F6 pass-rate 85% (2 failures SHIPPED VISIBLE)

## Detection (`make eval`)

- recall @ 0.1% FPR: 0.314; PR-AUC: 0.351; ROC-AUC 0.722 (not the headline)
- vs baseline replica: -0.06167 (95% CI [-0.06712, -0.0545], n=2672910)
- leakage suite: PASSED (0 skipped-unverifiable)

## Archive (`make archive-report`)

- pre-merge cells==elites: 144; post-merge: 1 (coverage 0.3%, can only fall)
- MAP-Elites optimisation at 10.4 evaluations per occupied cell — below the >=25 budget, so selection pressure is weaker than intended and the coverage trend carries less weight.

## Loop (`make loop`)

- LOOP-LIFT (full vs static, no loop): NO MEASURED EFFECT (delta +0.0053 coverage, below the 0.01 single-seed resolution)
- what the MDP level bought (full vs bandit-only): NO MEASURED EFFECT (delta +0.0000 coverage, below the 0.01 single-seed resolution)
- what credit assignment bought (full vs random tactic): NO MEASURED EFFECT (delta +0.0000 coverage, below the 0.01 single-seed resolution)
- time-to-evade: full vs static (probe budget): -3.9 probes
- time-to-evade: full vs bandit-only (probe budget): +1.2 probes

## Latency (`make bench`)

- end-to-end p99: **911.5 ms** (target 25.0, met=False), predictor: LightGBM predictor (treelite absent)
- sizing: 257 cores for the reference portfolio; NOT extrapolated to network scale

## Honesty instruments

- [VERIFY] markers: 65 — verifiable claims we refused to fake
- dual-use lint: 12 rules, 0 rejections logged

