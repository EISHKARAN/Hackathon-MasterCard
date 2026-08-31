# VAJRA

**A closed-loop red-team / blue-team system for GenAI-era payment fraud.**
Built for the Mastercard Innovation Challenge 2026 · Global Fintech Fest, Mumbai.

Generative AI did not mainly make individual payment attacks cleverer. It made *producing variants*
nearly free — so the space a defence must cover now grows faster than any labelled dataset can
follow. VAJRA answers that with a loop rather than a classifier: an adversary that invents attacks as
**compositions in a typed grammar**, a simulator that executes them at message level across twelve
payment rails, a detector that has to catch them, and a return path where whatever escaped raises the
adversary's interest in that region next round.

The defence's measured weakness sets the attacker's agenda. That arrow is the system.

---

## Results

Issuer deployment position. Test window **2,672,910 events**, **14,918 attacks**, base rate
**0.5581%**. Time-forward split with a purge and an embargo; sealed entities excluded from training.

| metric | value | what the denominator is |
|---|---|---|
| **PR-AUC** | **0.3512** | 62.9× lift over the base rate |
| **recall @ 0.1% FPR** | **0.3142** | realised FPR 0.000999 |
| **precision @ k = 641** | **0.9953** | 638 of 641 alerts are real attacks; k derived from staffing, not chosen |
| **value-detection rate** | **0.5517** | share of fraud *value* caught, not event count |
| **recall on attacks never trained on** | **0.2507** | 7,785 attacks whose composition was withheld — 52.2% of test positives |
| vs. the modelled incumbent | **+0.2832** recall | 95% CI [0.2760, 0.2918] |

Two numbers to read together, because either alone misleads: **99.5% of what we hand analysts is real
fraud, and we hand them 31% of the fraud.** Both are true, and they answer different questions.

**ROC-AUC is 0.7221 and is deliberately not the headline.** At a base rate under 1%, ROC-AUC is
dominated by the true-negative mass and sits near 1.0 for any competent model — which is why nearly
every submission in this space reports ~0.99 and none of those figures are comparable.

### A conventional baseline beats us, and we show it

We *executed* the standard approach rather than describing it — same features, same library, same
hyper-parameters, six methodology differences only. On the same rows against the same truth it scores
**0.4168 PR-AUC against our 0.3464**.

It is not a better model. It trains on a random slice spanning our test window, on labels that had
months to mature, counting everything unlabelled as clean. None of that is available at decision
time. The gap is the price of measuring honestly, and it is in the repository rather than omitted
from it.

---

## The hard part

**Only 2.50% of the training window carries any visible label.** A fraud label arrives hours later
from an analyst, days later from an issuer, or **45–120 days** later as a chargeback. Every design
choice here follows from that: positive-unlabelled learning at the realised class prior, inverse
propensity reject inference against the logged incumbent policy, and explicit label-maturity
weights.

The easy alternative — treat unlabelled as legitimate — teaches a model that *absence of a complaint
is evidence of innocence*, which is exactly false for the fraud that succeeds.

---

## What makes it checkable

| | |
|---|---|
| **15,271** | type-legal attack compositions from 188,160 raw; the other 172,889 are impossible on the rail, and rejection explains which constraint failed |
| **126** | rail invariants enforced as **build gates**, not tests. They once stopped the build 13,009 times; we fixed the generator, not the invariants |
| **6 of 6** | anti-leakage controls, each gating the build — including one that reads version-control history to prove the holdout was written down before the detector was |
| **268 / 380** | attack-space regions reached, a **70.5% coverage ceiling we publish** rather than let you assume was 100% |
| **54** | reason codes, so every decision carries an explanation an operations team can act on |
| **0** | unresolved observables — every grammar morpheme maps to a readable field or is recorded as design-only |

### Five defects our own instruments found

Reported here because the instruments are the contribution, not just the metrics.

Our fusion layer was discarding a model **4× better** than we were reporting — two channels were
dead, one returning an identical constant across all 2.6M rows and one reliably worse than a coin,
and between them they held 0.22 of the fused score. A friction cap could escalate an entire rail into
automatic declines. Two features separated attacks perfectly and were deleted as generator artefacts.
An instrument reported a fabricated zero. A guard refused to ship a collapsed action ladder.

We also disclose the **two places our simulator flatters us**, bounded at 21.1% and 6.8% of the
headline — and one feature we chose *not* to build even though it would have topped the chart,
because the signal was a property of our generator rather than of fraud.

Full accounting: [TECHNICAL.md](TECHNICAL.md) §17.

---

## Repository layout

| path | what it is |
|---|---|
| [`vajra/`](vajra/) | the system — grammar, simulator, detector, loop, evaluation, service, web interface |
| [`TECHNICAL.md`](TECHNICAL.md) | the complete technical account: design, protocol, results, ablations, self-audit, limitations |
| `VAJRA.pptx` | the presentation deck |

Two branches:

- **`main`** — the system and its deliverables. This is the branch to read.
- **`beta`** — full working history, including design notes, research material and the deck's source.

---

## Running it

```bash
cd vajra
make venv                # no GPU, no compiler needed
make all                 # small preset: the committed replay-bundle population
make all PRESET=full     # the population quoted above (long)
```

Seeded, ordered, and single-threaded where thread scheduling would otherwise change
floating-point reduction order — so a rebuild is byte-comparable, not merely similar. Every stage
writes a structured record, and any figure produced at reduced scale is stamped **not reportable**
inside the record itself, so a smoke-scale number cannot end up quoted as a result.

### The interactive demo

```bash
make demo                # service on :8000, interface on :3000
```

Six screens. The read-only ones render server-side from the committed evidence and need no service at
all. The sixth lets you **compose an attack yourself** from the six grammar slots — the picker is
constrained to type-valid combinations — then watch it compile, execute, pass the invariant gate, and
get scored by the promoted model, with the per-event band and reason codes it actually carried.

What you author is genuinely new to the model, but it is a novel *composition inside the grammar*,
not an attack category outside it. The screen says so where you might otherwise infer more.

Setup details, host-specific notes and every make target: [`vajra/README.md`](vajra/README.md).

---

## What is not claimed

**Everything here is simulated.** We validate *mechanism* fidelity — rail semantics, message flow,
lifecycle timing — and we do not claim distributional fidelity to any real portfolio, because that is
untestable without the portfolio. The absolute numbers above are a ceiling set by that fact; what
transfers is the methodology and the relative comparisons.

Also open and stated rather than found: one capacity check measures the review band when real
workload is set by the action mapping, so true analyst load is ~0.54% of volume against a 0.0240%
staffed budget. Two rails remain weak, and the measured gain from the features meant to fix them was
+0.0001 PR-AUC — a null result we report instead of dropping.

[TECHNICAL.md](TECHNICAL.md) §2 and §21 carry the complete list.
