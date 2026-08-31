---
title: VAJRA
emoji: 🛡️
colorFrom: red
colorTo: blue
sdk: gradio
app_file: app.py
pinned: false
license: mit
short_description: Closed-loop red-team / blue-team system for GenAI payment fraud
---

# VAJRA

A closed-loop red-team / blue-team system for GenAI-era payment fraud, measured on attacks it was
never trained on. Built for the Mastercard Innovation Challenge 2026.

This Space runs the **whole prototype as one service**: six screens and the scoring API behind them.

## The six screens

| screen | question it answers |
|---|---|
| economics | what does this stop, and what does it cost good customers? |
| attack space | how many distinct attacks, and how much of the space is reached? |
| fidelity | what does the build refuse to emit? |
| results | what does it catch, and against which comparisons? |
| the loop | did the closed loop actually buy anything? |
| author an attack | compose one yourself and watch it run |

On the last screen you pick one value from each of six grammar slots. The picker is constrained to
type-valid combinations, so illegal values are shown disabled with the reason. What you compose then
compiles, executes in the payment simulator, passes the rail invariant gate, and is scored by the
promoted model, which returns the per-event band and the reason codes the decision actually carried.

Attacks you author are novel **within** a fixed grammar. They are not attack categories outside it,
and the screen says so where you might otherwise infer more.

## Headline

Test window 2,672,910 events, 14,918 attacks, base rate 0.5581%.

| metric | value |
|---|---|
| PR-AUC | 0.3512 |
| recall at 0.1% FPR | 0.3142 |
| precision at a staffed queue of 641 | 0.9953 |
| recall on attacks never trained on | 0.2507 over 7,785 attacks |

ROC-AUC is 0.7221 and is deliberately not the headline: under a 1% base rate it is dominated by the
true-negative mass and is near 1.0 for any competent model.

## Not claimed

Everything here is simulated. Mechanism fidelity is validated and enforced by 126 rail invariants
that gate the build; distributional fidelity to a real portfolio is not claimed, because it cannot be
tested without the portfolio. A conventional baseline beats this system by 0.0704 PR-AUC and that
comparison is published rather than omitted.

The full technical account, including five defects found by our own instruments, is in the repository.

## Free-tier behaviour

The Space stops when idle. On wake it re-fetches its code, model bundle and evidence, which adds
roughly half a minute to the first request.
