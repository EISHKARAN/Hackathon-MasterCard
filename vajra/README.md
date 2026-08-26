# VAJRA — Verified Adversarial Rail Archive

**Mastercard Innovation Challenge 2026.** A red-team/blue-team payment-fraud **closed loop**: an
adversarial economy (VAJRA ARENA) that discovers behaviourally distinct GenAI-era payment attacks,
generates them at message level inside a deterministic simulator, and hardens a two-sided detector
(VAJRA GATE) against them — where every closure must prove it caught a **sibling attack it was never
trained on**.

The full design rationale is in [`../Solution-Design.md`](../Solution-Design.md). This README is how
you run it.

---

## What is here (three pillars, one loop)

| Pillar | Where | The one thing that makes it different |
|---|---|---|
| **Identify** | `grammar/` | Attacks are a **typed six-slot composition**, not a list. `make grammar` prints an integer: **15,271 type-legal compositions**, coverage over a **pre-declared feasible denominator** (380 cells), validated by a distinctness test that can lower our own number. |
| **Generate** | `sim/` | `graph → actors → events → messages → rows` (the inverse of a CTGAN submission). All 12 rails; **F1 invariant gate fails the build** on a structurally impossible message. A three-channel label engine with a modelled analyst, an ε-randomised incumbent policy shadow, entity-level sealed holdout. |
| **Defend** | `gate/`, `eval/` | G0 invariant guards → G1 LightGBM (388 machine-counted features) → G2 Mondrian conformal abstention, GATE-B beneficiary side, temporal splits, nnPU + reject inference. Metrics are recall @ fixed FPR, PR-AUC, precision@k at staffed capacity — never headline ROC-AUC on a random split. |
| **The loop** | `archive/`, `attack/`, `loop/` | A **hierarchical reinforcement learner** (MAP-Elites curriculum → Q(λ) campaign MDP → Thompson bandit) drives an LLM Composer to attack where the detector is weak; FORGE retrains and **withholds a one-morpheme-different sibling**. |

The reinforcement loop and the paper grounding for every model choice are documented in
[`docs/RL_LOOP.md`](docs/RL_LOOP.md) and [`docs/RESEARCH.md`](docs/RESEARCH.md). The interface
contracts every subsystem implements to are in [`docs/CONTRACTS.md`](docs/CONTRACTS.md).

---

## Run it

### 0. One-time setup

```bash
cd vajra
make venv          # creates .venv and installs requirements.txt (no GPU, no compiler needed)
```

Optional near-line models (GRU/RGCN), the Treelite export and the CTGAN F2 control:
`pip install -r requirements-optional.txt`. **Everything below runs green and honest without them** —
each consumer records a visible `SKIPPED-DEPENDENCY-ABSENT` rather than crashing.

### The one command a judge runs

```bash
make all                 # small preset (default): the committed replay-bundle population
make all PRESET=full     # the population the deck quotes (longer; see runtime below)
```

`make all` runs, in order: `grammar → sim → fidelity → train (every view) → eval → loop →
archive-report → money → duallog → verify → bench → report → bundle`. The **leakage suite inside
`make eval` fails the build** if any control fails. When it finishes, read
[`reports/report.md`](reports/report.md) — the one-page evidence index.

### Individual stages (each is a real command, and each prints its own numbers)

```bash
make grammar        # enumerate + type-check; prints the machine-counted composition/cell integers
make sim            # generate the world + run the F1 invariant gate (0 violations or the build fails)
make fidelity       # F1–F6, provenance-badged → reports/fidelity.html (failures shipped visible)
make train          # fit GATE-I/GATE-B for one view (VIEW=issuer)
make train-views    # fit every view for the visibility ablation (never cut)
make eval           # every metric → reports/metrics.md (leakage suite gates it)
make loop           # the closed loop: full + random_tactic + bandit_only + static arms
make archive-report # pre/post-merge coverage, per-slot observable delta, the search claim
make bench          # measured end-to-end p99 latency (NOT extrapolated to network scale)
make money duallog verify report bundle   # the MONEY data, the dual-use reject log, [VERIFY] register, roll-up, replay bundle
make sensitivity    # 0.33×/1×/3× mule-cost sweep (SLOW; deliberately excluded from make all)
```

### The demo (five minutes, offline)

```bash
make api    # terminal 1 — FastAPI backend on :8000, serving the committed replay bundle
make ui     # terminal 2 — Next.js UI on :3000
```

Then open `http://localhost:3000`. The six screens: **MONEY** (the opener), **AUTHOR-AN-ATTACK**
(compose a grammar string → it compiles, executes, and is scored live against the frozen model —
this is where you see *how the attack happened and how we identified it*), **LOOP**, **GATE OPS**,
**ARCHIVE**, **FIDELITY**. Or `docker compose up` for both at once.

### Tests

```bash
make test          # 40 tests: grammar invariants, determinism, F1, leakage, RL observability, fidelity guards
```

---

## What to read first, as a judge

1. **`make grammar`** — the diversity integer is machine-counted in front of you.
2. **`make sim`** — the F1 gate prints `0 violations`, and the build fails if it is not.
3. **`reports/metrics.md`** after `make eval` — every number carries its denominator, its interval,
   and a delta vs a baseline-equivalent replica *executed on the same harness*, not described.
4. **AUTHOR-AN-ATTACK** in the UI — author an attack yourself; it is scored against a **frozen**
   model whose version is printed on screen.

At the smoke/small preset the detector's headline is stamped **NOT REPORTABLE** below 100 test
positives — that is deliberate: a headline computed from a handful of positives is not a result.
`PRESET=full` produces the reportable population.

---

## Honesty instruments (the novelty is that these can embarrass us)

- **`reports/fidelity.html`** shows F3/F5 assertion **failures in red**, with their T1/T2/T3
  provenance tier. A fidelity claim that goes red in front of you is worth more than a green one.
- **Exactly two conditionals carry T1.** `make fidelity` fails the build if anything else claims it.
- **`VERIFY_REGISTER.md`** — every `[VERIFY]` marker, each a claim we refused to fake.
- **`governance/dual_use_reject_log.json`** — what the dual-use lint refused, published.
- **Sibling transfer recall** and **LOOP-LIFT** are reported even when small or zero.

## Determinism and reproducibility

One master seed in `config/seed.yaml` derives named RNG streams by KDF, so adding a family or
reordering execution cannot perturb another stream. `make sim` produces a **byte-stable logical
Parquet hash** at a fixed seed (asserted by `tests/test_pipeline.py`). LightGBM is pinned to one
thread on the CI path; the demo run may use all cores and says so. Composer responses are
content-hash cached; `LLM_MODE=cached` is the default and never touches the network.

## Making the seal real (git)

The sealed-family holdout's anti-circularity claim rests on the manifest being committed **before**
the modelling code. This checkout is not a git repo, so the commit-order audit reports
`SKIPPED-UNVERIFIABLE` (an honest skip, never a pass we did not earn). To make it real:

```bash
git init
git add grammar/ config/ docs/ sim/schema.py && git commit -m "grammar + sealed manifest, pre-modelling"
git add features/ gate/ && git commit -m "detector"     # committed AFTER the manifest
```

`eval/leakage.py::commit_order_audit` then compares the commit timestamps and passes only if the
manifest came first.

## Expected runtime and hardware

8 cores, 16 GB RAM, no GPU, macOS or Linux. `make all` on the `small` preset is minutes; on `full`
it is longer (the feature build is ~100 µs/row, so ~26M rows is tens of minutes) and the honest
wall-clock is written to `reports/runtime.json` as it runs. `make bench` measured **p99 ≈ 17 ms**
end-to-end on the stated laptop even without the Treelite export — not extrapolated to network scale.

## Safety posture

Abstraction-level only: no deepfake/voice-clone/document-forensics code, no enumeration tooling, no
real BINs/PII, no persuasive scam copy. The dual-use lint enforces this as a build gate and publishes
its reject log. Every identifier is synthetic and non-routable. See §18 of the solution design.
