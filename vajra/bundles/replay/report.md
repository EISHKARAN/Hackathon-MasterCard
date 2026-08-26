# VAJRA — evidence index

> Every number here is a MEASUREMENT from this run. Sections marked 'not generated' need their `make` target run first.

## Grammar (`make grammar`)

- type-legal compositions: **15,271** (of 188,160 raw, 91.9% pruned) — the string-space size, NOT the diversity headline
- feasible cells: **380** / 576 nominal; reachable 268 (ceiling 70.5%)

## Simulator (`make sim`)

- events: **51,405** over 14 days, 421 attacks
- **F1 invariant gate: 0 violations** across 126 invariants — the never-cut gate
- events logical hash: `be26505d833be98aab453a207b35e3a8`

## Fidelity (`make fidelity`)

- provenance: T1=2 (exactly the two conditionals), T2=4, T3=7
- F1: 0 violations; F3/F5/F6 pass-rate 77% (3 failures SHIPPED VISIBLE)

## Detection (`make eval`)

> **NOT REPORTABLE at this scale** — 95 test positives, below the 100 floor. Numbers are wiring evidence. Run `make sim PRESET=full`.
- recall @ 0.1% FPR: 0.000; PR-AUC: 0.016; ROC-AUC 0.733 (not the headline)
- vs baseline replica: -0.4421 (95% CI [-0.5575, -0.3283], n=13879)
- leakage suite: PASSED (1 skipped-unverifiable)

## Archive (`make archive-report`)

- pre-merge cells==elites: 34; post-merge: 1 (coverage 0.3%, can only fall)
- AT 2.2 EVALUATIONS PER OCCUPIED CELL WE DO NOT CALL THIS MAP-ELITES OPTIMISATION. It is a TYPED ENUMERATION WITH P&L ANNOTATION — still a defensible artifact, but a different claim, and the coverage figure must be read as a count of compositions that executed rather than as the output of a search.

## Loop (`make loop`)

- LOOP-LIFT (full vs static, no loop): NO MEASURED EFFECT (delta -0.0026 coverage, below the 0.01 single-seed resolution)
- what the MDP level bought (full vs bandit-only): NO MEASURED EFFECT (delta +0.0000 coverage, below the 0.01 single-seed resolution)
- what credit assignment bought (full vs random tactic): NO MEASURED EFFECT (delta +0.0000 coverage, below the 0.01 single-seed resolution)
- time-to-evade: full vs static (probe budget): no measured effect (n=1, few ticks)
- time-to-evade: full vs bandit-only (probe budget): +2.8 probes

## Latency (`make bench`)

- end-to-end p99: **16.8 ms** (target 25.0, met=True), predictor: LightGBM predictor (treelite absent)
- sizing: 2 cores for the reference portfolio; NOT extrapolated to network scale

## Honesty instruments

- [VERIFY] markers: 58 — verifiable claims we refused to fake
- dual-use lint: 12 rules, 0 rejections logged

