# The reinforcement loop

VAJRA's red side is a **hierarchical reinforcement learner** with three levels operating
on three different clocks, plus an LLM acting as a semantic variation operator. This file
specifies it formally, because "we used RL" is otherwise unfalsifiable.

Literature grounding is in [`RESEARCH.md`](RESEARCH.md) §7. The closest prior work is
**Fraud-RLA** (Lunghi et al., IEEE TDSC 2026), which establishes the formulation, the
attacker-profit reward, and the frozen-detector evaluation protocol.

```
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ LEVEL 3 — CURRICULUM (per tick)          MAP-Elites archive              │
 │   not RL: it is the task distribution. Chooses WHICH cell to attack,     │
 │   biased toward under-occupied feasible cells and high-P&L elites.       │
 │   → emits a parent elite + a target cell                                 │
 └───────────────────────────┬──────────────────────────────────────────────┘
                             │  LLM Composer: ONE call per tick.
                             │  Semantic variation operator over morphemes.
                             ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ LEVEL 2 — CAMPAIGN MDP (per stage, ~4 steps per campaign)                │
 │   Q-learning with eligibility traces over a small discrete state space.  │
 │   Solves CREDIT ASSIGNMENT ACROSS THE KILL CHAIN — which a bandit        │
 │   structurally cannot, because probing costs now and pays later.         │
 │   → emits a TACTIC                                                       │
 └───────────────────────────┬──────────────────────────────────────────────┘
                             │
                             ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ LEVEL 1 — ARM BANDIT (per transaction batch, hundreds per campaign)      │
 │   Thompson sampling, contextual. Chooses the numeric parameters inside   │
 │   the tactic: amount band, MCC, entry mode, acquirer, hour, fan-out.     │
 │   → emits transactions into vajra-sim                                    │
 └──────────────────────────────────────────────────────────────────────────┘
```

**Why three levels and not one.** Each level exists because the level below it cannot do
its job:

*   A bandit alone cannot do **credit assignment**. In a kill chain the reward is delayed:
    probing spends `probe_cost` now to raise the approval rate later; extending mule dwell
    pays `λ·elapsed_steps` now to avoid a beneficiary freeze later. A bandit maximises
    immediate reward and will therefore never learn to spend early. Temporal-difference
    learning is exactly the tool for this and it is the reason Level 2 exists.
*   Q-learning alone cannot handle the **parametric** action space. Amount band × MCC ×
    entry mode × acquirer × hour × fan-out is thousands of arms with a noisy reward;
    discretising it into the Q-table would destroy the tabular tractability that makes
    Level 2 fast and deterministic. Thompson sampling handles it in a few hundred lines of
    numpy.
*   Neither can propose a **new composition**. Choosing which morpheme to mutate given a
    plain-English description of where the detector is weak is a combinatorial-semantic
    act, and that is the only thing the LLM does. It is invoked once per tick, never per
    transaction — per-transaction adaptation is precisely what the bandit does better and
    three orders of magnitude more cheaply.

---

## Level 2 in full: the Campaign MDP

`attack/rl/campaign_mdp.py`

### State — deliberately small, and deliberately attacker-observable only

`S = stage × last_outcome × budget_bucket × heat`

| Component | Values | Count |
|---|---|---|
| `stage` | `recon`, `establish`, `extract`, `cashout` | 4 |
| `last_outcome` | `approve`, `decline`, `step_up`, `credit_landed`, `credit_held`, `onward_blocked`, `account_frozen`, `none` | 8 |
| `budget_bucket` | `high` (>66% remaining), `mid`, `low` (<33%) | 3 |
| `heat` | `cold`, `warm`, `hot` — the attacker's own running estimate of adverse-event rate over its last window, **not** a detector score | 3 |

|S| = 288, |A| = 11, so the Q-table is 3,168 floats. It converges in the execution budget
we actually have (TARGET ≥25 evaluations per occupied cell), which a deep policy would
not, and it is fully inspectable — the LOOP screen renders the learned policy as a
readable table, which is the point of choosing tabular.

### The hard observability constraint, enforced in code

`attack/rl/observation.py::AttackerObservation` is a frozen dataclass whose fields are
**exactly** what a real adversary observes:

*   payer side: `approved`, `declined`, `stepped_up`, `reason_code`, `response_latency_ms`
*   beneficiary side: `credit_landed`, `credit_held`, `onward_send_blocked`,
    `account_frozen`, `seconds_to_freeze`

It has **no** `score`, no `conformal_p`, no feature vector, no attribution. This is not a
convention: `tests/test_attacker_observability.py` asserts the dataclass field set
exactly, and fails if a field carrying defender-internal information is ever added. Without
that test, "the attacker observes only what an attacker observes" is a sentence in a
document rather than a property of the system, and the whole time-to-evade metric would be
measuring an attacker with oracle access.

The beneficiary-side half of that vector is load-bearing and not decoration. A payer-side-only
observation would close the loop around half the system, and the mule-layering families
(ATK-G1, ATK-G2, ATK-A2) are exactly the ones that would adapt against a beneficiary gate.
An adversarially unstressed GATE-B number is the first thing an adversarial-ML judge would
find. If the beneficiary-side observation is cut for time, every GATE-B number is labelled
**non-adversarial** wherever it appears.

### Actions — 11 tactics

| Tactic | What it changes | Which EVASION morpheme it serves |
|---|---|---|
| `probe` | spend budget on low-value discovery, no extraction | oracle-probing |
| `escalate_amount` | move up the amount band | — |
| `deescalate_amount` | move down | threshold-hugging |
| `hug_threshold` | pin amounts just under the nearest policy threshold | threshold-hugging |
| `split_velocity` | same value, more transactions, smaller each | velocity-splitting |
| `rotate_entity` | fresh PAN / token / device / VPA | cohort-splitting |
| `inherit_trust` | route via the highest-trust envelope available | trust-inheritance |
| `switch_acquirer` | move to a different acquirer / MID population | low-visibility-rail |
| `extend_dwell` | hold funds longer at the mule before onward send | graph-camouflage |
| `pad_payer_set` | add unrelated inbound payers to the mule's payer set | graph-camouflage |
| `cash_out` | attempt the monetisation step now | — |

Actions are **masked by the composition**: a campaign whose EVASION morpheme is
`velocity-splitting` may still call `extend_dwell`, but a campaign whose RAIL has no
beneficiary leg cannot, and the mask is derived from the grammar rather than hand-listed
per family. An unmasked action set would let the RL agent learn tactics its own
composition does not license, which would silently decouple the archive's behaviour axes
from what the agent actually does.

### Reward

The per-step reward is the **increment in attacker P&L**, from `config/cost_matrix.yaml`:

```
r_t = Δvalue_retained(t)
      − probe_cost·Δprobes − mule_burn·Δmules − credential_cost·Δcredentials
      − λ·Δelapsed_steps
      − ruin_penalty·1[ruin fired at t]
```

Three properties of this reward that are decisions, not details:

1.  **`value_retained`, not gross debits.** Value is counted as funds still in attacker
    control at `t + value_horizon_hours` (default 72 h in sim clock) after auto-release
    and clawback. Crediting gross debits would reward money GATE-B already took back,
    while the agent is simultaneously observing `account_frozen` — an incoherent reward
    that would teach the agent that being frozen is fine.
2.  **Ruin is a penalty plus a flag, never a deletion.** `ruined` is evaluated as an
    explicit comparison in sim clock — detection latency versus time-to-break-even — on a
    *named observable event* (a beneficiary freeze, or an analyst-confirmed fraud
    disposition on any event in the campaign). "Detected" is not a usable trigger: at a
    0.1% base rate any multi-transaction campaign draws some declines, so a decline-based
    trigger fires either always or never.
3.  **No reward shaping from defender internals.** We do not add a potential-based shaping
    term from the detector's score, even though it would speed convergence a lot. Doing so
    would smuggle defender-internal information into the attacker through the reward
    channel and invalidate every "the attacker observes only what an attacker observes"
    claim in this repo. The convergence cost is real and we pay it.

### Learning rule

Watkins Q-learning with eligibility traces (Q(λ)), ε-greedy exploration on a decaying
schedule, and **experience replay across the archive**: every campaign ever executed is
retained as a transition list, and each tick replays a sample of them. Replay is what makes
the ≥25-evaluations-per-cell budget sufficient — without it, each cell's agent would learn
from its own handful of episodes only.

```
Q(s,a) ← Q(s,a) + α·δ_t·e(s,a),      δ_t = r_t + γ·max_a' Q(s',a') − Q(s,a)
```

Hyper-parameters live in `config/rl.yaml` and are swept, not tuned against a reported
number. Defaults: α=0.15, γ=0.92 (finite horizon, so γ<1 is a mild preference for earlier
extraction — the real horizon bound is the budget), λ_trace=0.7, ε from 0.35 → 0.05 over
the run.

### Off-policy safety: the frozen-GATE evaluation

**Time-to-evade is measured against a FROZEN defender.** If the defender retrains while
the attacker searches, attacker and defender co-drift and the resulting number is
meaningless — this is the control Fraud-RLA establishes and the one most easily forgotten.
`eval/metrics/time_to_evade.py` snapshots the promoted model, runs the RL attacker against
that snapshot with learning enabled, and reports the probe budget required to reach a
target approval rate. The promoted model keeps moving; the measurement does not.

---

## Level 1: the contextual bandit

`attack/rl/bandit.py`. Thompson sampling over independent Beta posteriors per arm within
the tactic-restricted arm set, with a context vector of
`(rail, amount_decile, hour_bucket, entity_age_bucket)` and a linear-Gaussian posterior for
the continuous amount dimension.

Non-stationarity is handled by **discounted counts** (posterior counts decay by `ρ=0.97`
per tick), which is what makes the bandit track a retrained defender instead of averaging
over its whole history. Without the discount the bandit's estimate of an arm is dominated
by the pre-retrain regime and it stops adapting, which would look like the defender winning
when it is actually the bandit's memory.

## Level 3: the curriculum, and why MAP-Elites is the right shape

MAP-Elites is not RL, and calling it RL would be wrong. What it is, in RL vocabulary, is an
**automatic curriculum generator**: it maintains a population of tasks (cells), tracks the
best-performing solution in each, and biases sampling toward under-explored regions. That
is unsupervised environment design, and it does for the RL agent what a hand-written attack
list cannot — it keeps proposing tasks the agent has not yet solved, over an axis system
that is *interpretable* rather than latent.

The archive is also where the loop's honesty lives. Coverage is reported over a
pre-declared feasible denominator, **after** Jensen–Shannon distinctness merging, so the
number can go **down** when we validate it. A curriculum that inflates its own task count
would be a curriculum that stops finding anything.

## What closes the loop on the defender's side

The return path is what makes this a mechanism rather than a diagram:

1.  **SCORE** — GATE-I and GATE-B score every event the campaign produced.
2.  **MINE** — the Gap Miner clusters *escapes*, fits a shallow surrogate tree separating
    escapes from caught attempts, and renders the escape region as an English sentence.
3.  **PLAN** — that sentence is the LLM Composer's entire input. The Composer proposes a
    morpheme mutation aimed at the escape region.
4.  **FORGE** — the defender retrains on the closed vector, **withholding a
    one-morpheme-different sibling** from the retrain batch.
5.  The sibling's recall, measured **at a fixed benign FPR using the pre-retrain action
    table**, is the loop's validity metric. Retraining on the attack you just injected and
    catching it is a tautology; catching a sibling you withheld is not.

## Ablations that make the RL claim falsifiable

Three control arms, all in `eval/control_arm/`, because "our RL agent learned" is worth
nothing without them:

| Arm | What is disabled | What its delta measures |
|---|---|---|
| `random-tactic` | Level 2 Q-learning replaced by uniform random tactic choice | what the MDP-level credit assignment bought |
| `bandit-only` | Level 2 disabled, Level 1 bandit retained | whether a bandit alone would have sufficed — the honest null for "why RL" |
| `static` | the whole loop disabled; models trained once on seeded compositions | LOOP-LIFT, the headline control |

If `bandit-only` matches the full agent, we report that the MDP level bought nothing and
say so. That outcome is survivable; hiding it is not.
