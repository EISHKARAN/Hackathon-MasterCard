# VAJRA: Technical Document

**A closed-loop red-team / blue-team system for GenAI-era payment fraud**
Mastercard Innovation Challenge 2026 · Global Fintech Fest, Mumbai

---

## 0. How to read this document

This is the complete technical account: what the system is, how every part works, how it was
measured, what the numbers mean, and where it falls short. It is written so that a reviewer can
check any claim without running anything, and reproduce any claim by running one command.

Three conventions hold throughout.

**Every number carries its denominator.** A recall figure without the population it was measured
on is not a result. Wherever a metric appears, the row count and the positive count appear with it.

**Every number carries a provenance tier.** *Measured* means computed by this system on this data.
*Derived* means arithmetic on measured quantities. *Design-only* means a target set during design
that has not been measured. Design-only quantities are never presented as results, and where a
measured value supersedes a design target, the measured value governs.

**Adverse findings are stated by us, in the same voice as favourable ones.** Section 17 lists five
defects our own instruments found in our own system, two places where our simulator flatters us,
and one comparison in which a conventional baseline beats us. None of that was volunteered under
questioning; all of it was found by instruments we chose to build.

---

## 1. The problem, precisely stated

Generative AI has changed the economics of payment fraud in a specific way that most detection work
does not address. It has not primarily made individual attacks more sophisticated. It has made the
*generation of variants* nearly free.

A fraud operation that previously ran one script against one rail can now run a hundred variations
of that script across twelve rails, each varying in how access is obtained, whose trust is borrowed,
how the transaction is kept beneath a threshold, and how the value is extracted. The defensive
consequence is not that any single attack is harder to catch. It is that the *space* of attacks a
defence must cover has expanded faster than any labelled dataset can follow.

This produces two coupled difficulties.

### 1.1 The label problem

Fraud labels arrive long after the decision that needed them.

| label channel | typical latency |
|---|---|
| analyst disposition | hours |
| issuer tag | days |
| chargeback / network report | 45–120 days |

In our training window, **2.50%** of rows carry any visible label at all. This is not a defect of
our simulation; it is the defining constraint of the real problem. A model trained as though labels
were available is a model evaluated on information it will not have on the day.

The naive handling, treating every unlabelled row as legitimate, is worse than useless. It teaches
the model that *absence of a complaint is evidence of innocence*, which is precisely false for the
fraud that succeeds.

### 1.2 The coverage problem

You cannot collect a labelled dataset of attacks that have not happened yet. Any detector trained
only on historical fraud is, by construction, calibrated to last year's attack distribution.

The standard response is to enumerate scenarios (twenty or thirty named attack types) and test
against them. This produces a number that is uninformative about the case that matters: the attack
composed differently from anything in the list.

### 1.3 What follows from these two

Both problems point the same way. If labels are scarce and the attack space is larger than any
dataset, then the useful artefacts are not a bigger dataset and a better classifier. They are:

1. a **generator** that can produce attacks across the whole space, not a sample of it;
2. a **learning procedure** honest about label scarcity rather than papering over it;
3. an **evaluation protocol** that measures performance on attacks deliberately withheld; and
4. a **feedback path** so that the gaps the defence leaves determine what the generator produces
   next.

That is the system described below.

---

## 2. Scope: what is and is not claimed

Stating this early, because the strongest claims in this document depend on the weakest ones being
disowned.

### 2.1 Claimed

- **Mechanism-level fidelity.** The synthetic stream obeys the message semantics, ordering
  constraints, clearing behaviour and lifecycle timing of the twelve payment rails it models. This
  is enforced at build time by 126 invariants, not asserted.
- **Compositional coverage.** The attack space is a typed grammar of 15,271 legal compositions, and
  the fraction of that space actually reached is measured and published rather than assumed.
- **Generalisation to withheld compositions.** Detection performance is measured on attack
  compositions excluded from training at the entity level, including one entire evasion technique
  withheld wholesale.
- **Operational realisability.** Every score maps to an action the specific rail can actually
  execute, carries a reason code, and is produced within a measured latency budget.
- **Reproducibility.** One command regenerates every number in this document, seeded and ordered.

### 2.2 Not claimed

- **Distributional fidelity to any real portfolio.** Our transaction amounts, session durations,
  merchant mixes and device populations are drawn from parameterised distributions. They are not
  claimed to match Mastercard's book or any issuer's. This is untestable without the portfolio, and
  asserting it would be exactly the kind of unfalsifiable claim this design refuses elsewhere. Two
  specific places where our draws are measurably too clean are quantified in §17.6.
- **That the absolute metrics transfer to production.** The base rate, the label latency mix and the
  incumbent policy are all modelled. A production deployment would re-fit against real data. What
  transfers is the methodology and the relative comparisons, not the digits.
- **That a language model invents novel attack categories.** The generative component operates as a
  *variation operator inside a fixed grammar*. It composes and mutates within a typed space. It does
  not conjure attack categories outside that space, and we do not claim it does. §4.5 states this
  bound explicitly, and the interactive demo restates it on the screen where a reviewer might
  otherwise infer more.
- **Currency figures as money.** All rupee amounts are simulator-internal and labelled as such.

---

## 3. System overview

Three subsystems and one return path.

```
   ┌──────────────────────────────────────────────────────────────────────────┐
   │  THE ATTACKER  ── invents attacks in regions where the defence is blind  │
   └────────────────────────────────┬─────────────────────────────────────────┘
                                    │  campaigns (typed compositions)
                                    ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │  THE WORLD  ── executes them on 12 payment rails, emits messages,        │
   │                runs the incumbent policy in shadow, resolves labels late │
   └────────────────────────────────┬─────────────────────────────────────────┘
                                    │  event stream + late labels
                                    ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │  THE DEFENCE  ── structural guards → supervised score → novelty and      │
   │                  confidence → per-rail action                           │
   └────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                    ┌───────────────┘  what escaped, clustered into named gaps
                    ▼
          raises the sampling weight of the regions that produced it
                    └──────────────────────────► back to THE ATTACKER
```

The return path is the load-bearing element. Without it this is a pipeline that runs once. With it,
the defence's measured weakness is the attacker's next objective, and the system's coverage of the
attack space is driven by where it is currently failing rather than by where data happens to exist.

---

## 4. The attack grammar

### 4.1 Six slots

An attack is not a scenario. It is a sentence in a typed language with six slots, each answering one
question about how the fraud works:

| slot | question it answers | cardinality |
|---|---|---|
| ACCESS | how does the attacker obtain the ability to transact? | 8 |
| TRUST | whose trust or credential is being borrowed? | 7 |
| RAIL | which payment rail carries it? | 12 |
| EVASION | how does it avoid the existing controls? | 8 |
| MONETISATION | how does the value actually leave? | 7 |
| LABEL | what will this eventually be called, if anything? | 5 |

Cross-product: 8 × 7 × 12 × 8 × 7 × 5 = **188,160** raw strings.

### 4.2 Typing, and why most strings are illegal

Most of those 188,160 strings describe events that cannot physically occur. A pairwise compatibility
relation over slot values rejects them, leaving **15,271 type-legal compositions**: a pruning rate
of 91.9%, with **172,889** strings rejected.

The rejections are not filtering for plausibility; they are type errors. Two worked examples:

- A monetisation step that names a beneficiary account is illegal on a rail that terminates in
  physical cash at an assisted withdrawal point. There is no beneficiary leg to name: the cash
  leaves the system at the counter.
- An evasion technique that depends on a step-up authentication challenge is illegal on a rail that
  has no challenge in its message flow.

Rejection is *explanatory*: the compiler returns which pairwise constraint failed, not a boolean.
This matters operationally: in the interactive demo, an illegal composition produces a sentence
explaining why that combination cannot exist on that rail, which is more informative than a
generator that silently declines to emit.

### 4.3 The twelve rails

UPI pay · UPI collect · UPI autopay mandate · UPI Lite offline · card e-commerce with 3-D Secure ·
card e-commerce key-entered · card present with chip · card clearing and dispute · card token
provisioning · account-to-account credit transfer · assisted cash-out at a micro-ATM · agentic
commerce.

The set was chosen to span the structural variation that matters for detection: real-time push
versus deferred settlement, present versus not-present, mandate-based recurring versus one-shot,
online versus offline-capable, and one rail (agentic commerce) where the initiating party is
software acting under a delegated mandate.

### 4.4 Seed families and reason codes

**51 seed families** span the twelve rails and provide the starting points from which the attacker
composes. **54 reason codes** form the fixed vocabulary in which any decision must explain itself
(§11.3).

### 4.5 The honest bound on novelty

What the system generates is *novel composition within a fixed grammar*. A composition the model has
never seen is genuinely new to the model, which is what §14.3 measures, but it is not an attack
category outside the six slots.

This bound is stated here, restated on the interactive screen where a reviewer composes an attack,
and restated in §21. We prefer a defensible smaller claim to an impressive one we cannot support.

---

## 5. Quality-diversity search and the control hierarchy

### 5.1 The archive as a map of the attack space

The attacker does not sample compositions randomly. It maintains a quality-diversity archive: the
attack space is partitioned into behavioural cells along descriptor axes, and the archive retains the
best-performing composition found in each cell.

Census of that space:

| quantity | value |
|---|---|
| nominal cells | (descriptor cross-product) |
| feasible cells | **380** |
| cells reached | **268** |
| coverage ceiling reached | **70.5%** |

**We publish 70.5% rather than implying 100%.** The unreached 112 cells require morpheme
combinations our 51 seed families do not currently produce. That is a stated limitation with a known
cause, which is more useful to a reviewer than a coverage claim with no denominator.

### 5.2 Three levels of control

| level | mechanism | what it decides |
|---|---|---|
| curriculum | quality-diversity archive | *which region* of the attack space to attack next |
| campaign | Watkins Q(λ) over a campaign MDP | *how a campaign unfolds*: escalate, persist, or abandon |
| family selection | Thompson sampling over seed families | *which family* to draw from, under uncertainty |

The archive is the curriculum, and this is the sentence that matters: **cells where the defence
detects nothing get sampled more.** The defence's blind spots set the attacker's agenda, which is
what makes the loop adversarial rather than merely iterative.

### 5.3 The generative model as a variation operator

A language model proposes variations, and does so **once per tick, never once per transaction.**

This placement is deliberate and has three consequences. The run stays seeded and byte-reproducible,
because the stochastic element is called a bounded number of times at known points. The cost is
bounded and does not scale with event volume. And the generated content is a *composition proposal*
that must still pass the type checker in §4.2, so the model cannot emit something structurally
impossible even if it tries.

### 5.4 The campaign budget

Each campaign operates under a profit-and-loss budget and must earn its continuation. An attacker
whose attempts are being declined burns budget and abandons; one that is succeeding escalates. This
is not decoration: it produces the *temporal shape* real fraud campaigns have (probe, escalate,
exit) rather than a uniform stream of attempts, and that shape is itself a detectable signal, so
generating it correctly matters for fidelity.

---

## 6. The simulator

### 6.1 Scale

| quantity | value |
|---|---|
| payment events generated | **9,899,667** |
| label records emitted | **374,077** |
| rails | 12 |
| realised attack share | **0.69%** (configured target 0.50%) |

### 6.2 Message flows and lifecycle

Each rail is modelled at the message level, not as a single row per transaction. A card e-commerce
purchase produces an authorisation, then a presentment, then possibly a chargeback, each a separate
event with its own timestamp, and each subject to ordering constraints (§7).

This matters because much of the detectable signal in real fraud is *in the relationship between
messages*: a presentment that never arrives, a reversal pattern, a mandate whose amount drifts across
executions. A one-row-per-transaction simulation cannot express any of that and therefore cannot be
used to evaluate a detector that would rely on it.

### 6.3 The label engine

Labels are emitted through three channels with three latencies (§1.1), and crucially:

- a label arrives strictly **after** the event it describes;
- it arrives inside a channel-appropriate window;
- **a majority of attacks never receive a label at all**, matching the real regime.

The third point is what makes the learning procedure in §9 necessary rather than optional.

### 6.4 The incumbent policy, run in shadow

A modelled incumbent fraud policy runs alongside the simulation and records what it would have
blocked. This provides two things: a controlled comparison arm (§15.1), and the logged treatment
propensities that the reject-inference correction in §9.2 requires. Without the shadow policy, the
selection effect that policy creates would be invisible and uncorrectable.

### 6.5 Base-rate control

The attack base rate is not assumed; it is driven onto target by a controller. Before control, the
realised rate diverged from configuration by up to **4.1×**. After control, divergence is **1.38×**:
realised 0.69% against a configured 0.50%.

The trainer then uses the **realised** value, not the configured one. This is not a detail: the
class-prior correction in §9.1 is parameterised by the true positive rate, and feeding it the
configured value would silently mis-specify the estimator.

---

## 7. Fidelity: invariants as build gates

### 7.1 126 invariants, enforced at build time

Fidelity is a judged criterion, so we made it checkable rather than asserted. **126 rail invariants**
are enforced as build gates. A violation does not produce a warning in a log; it stops the build.

Representative classes:

- **Ordering.** Authorisation precedes presentment. A reversal cannot precede the authorisation it
  reverses. A derived leg is strictly after its antecedent.
- **Clearing direction.** Presentment spills forward to the next settlement window, never backwards.
- **Mandate consistency.** An execution against a mandate cannot exceed the mandate's own
  authorisation band, and cannot occur before the mandate exists.
- **Time convention.** A single hour convention is enforced at one chokepoint, so a boundary
  condition cannot be handled two different ways in two places.
- **Identity coherence.** An entity's attributes cannot change in ways the rail does not permit
  mid-lifecycle.

### 7.2 Why they are gates and not tests

At one point during development these invariants failed the build **13,009 times.**

We fixed the generator, not the invariants. That sentence is the whole argument for making them
gates: a test suite that is run occasionally and whose failures are triaged will, under deadline,
have its assertions relaxed. A gate that stops the build cannot be relaxed quietly, because
relaxing it is a visible change to the gate.

### 7.3 Observables and provenance tiers

**236 distinct observables** are resolved from the grammar's morphemes down to concrete fields:

| tier | count | meaning |
|---|---|---|
| schema-tier | 58 | present as a field in the emitted event schema |
| feature-tier | 115 | computed by the feature layer from schema fields |
| design-only | 63 | specified during design, not yet realised as a field |

**Zero observables are unresolved.** Every morpheme in the grammar either maps to something the
detector can read, or is explicitly recorded as design-only. There is no third category of
"mentioned in the design and quietly absent", which is the failure mode this accounting exists to
prevent.

---

## 8. Features and the visibility model

### 8.1 The feature set

**392 features** in total. They fall into families: velocity and fan-out over entity graphs,
deviation from an entity's own historical baseline, cross-field plausibility (does the declared
timezone agree with the geography, does the verification method agree with the device age),
mandate-specific features, session behaviour, and the incumbent policy's own score as an input.

Boosting selected iteration **221 of 600** as best, on early stopping against the validation slice.

### 8.2 Four deployment positions

A detector's inputs depend on where it is installed. We model four positions and measure each:

| position | features available | recall @ 0.1% FPR |
|---|---|---|
| **issuer** | **319** | **0.3142** |
| network | 316 | 0.2885 |
| acquirer | 212 | 0.2088 |
| payee PSP | 191 | 0.2075 |

### 8.3 Absent, not zero

**A feature an institution genuinely cannot construct is absent from the matrix, not filled with
zero.**

This is a substantive modelling decision. Filling in zero asserts *"this account has no token
fan-out"*, a factual claim, and usually a false one. Marking it absent asserts *"this institution
cannot observe this account's token fan-out"*, which is the true claim. Gradient-boosted trees handle
genuine absence natively through their missing-value branch; they cannot distinguish a real zero from
an imputed one.

### 8.4 What this ablation actually shows, including the inconvenient part

**The issuer position is the most informative, not the network position.** We report that, although
the opposite result would tell a better story at a Mastercard event.

The defensible claim that follows is different and, we think, stronger: what the network uniquely
provides is not a better vantage point but **distribution**. A privacy-preserving risk exchange
(§11.6) lets an issuer *receive* cross-issuer mule priors that it could never observe from its own
book, without any personal data crossing an institutional boundary. The network's role is as a
signal distributor, and that role is not diminished by the issuer having the better local view.

---

## 9. Learning when labels do not exist yet

Three corrections, each addressing a distinct bias introduced by §1.1. They compose; none is
sufficient alone.

### 9.1 Non-negative positive-unlabelled learning

With 2.50% label visibility, the training data is not positive/negative: it is positive/unlabelled.
Treating unlabelled as negative biases the model toward the fraud that gets *reported*, which is
systematically the fraud that *failed*.

We use non-negative PU learning with the class prior set to the **realised** attack rate from §6.5.
The non-negative variant is specifically chosen because the unbiased PU risk estimator can go
negative with a flexible model class and overfit into that region; the non-negative correction
bounds it.

### 9.2 Inverse-propensity reject inference

The incumbent policy already declined some transactions. For those, the counterfactual outcome is
unobservable: we will never learn what would have happened. Training on the surviving population
only fits a model to *the transactions the old policy allowed*, which is a biased sample of the
population the new model must score.

The shadow policy (§6.4) logs its own treatment propensities, and we weight by the inverse of those
propensities to correct the selection effect.

### 9.3 Label-maturity weighting

A label observed 3 days after the event and a label observed 90 days after are not equally
informative about what was knowable at decision time. Rows are weighted by label maturity, so the
optimiser is not pulled toward information that would not have existed.

### 9.4 The consequence, stated plainly

**These three corrections make the model's headline number worse and its honesty better.** A model
trained without them scores higher on any test set that shares their biases, which is exactly what
happens in §15.2, where a conventional baseline beats us. We consider that comparison the point, not
an embarrassment, and §15.2 gives the natural experiment that isolates why.

---

## 10. The detection stack

Four layers. Each has a distinct job and a distinct failure mode.

### 10.1 Layer 0: structural guards

Refuses what is structurally impossible on the rail: a message sequence that cannot occur, a mandate
execution outside its band, a field combination the rail does not permit.

This layer has **no model dependency**, which makes it the kill switch: with the model unavailable,
the system still refuses the impossible. That is a degraded mode, not an outage, a distinction that
matters for a production fraud control, where "the model is down" must not mean "everything is
approved".

### 10.2 Layer 1: the supervised channel

Gradient-boosted trees over the feature matrix in §8, trained with the corrections in §9. This is
the workhorse: standalone PR-AUC **0.3505** of the final **0.3512**.

### 10.3 Layer 2: novelty and confidence

Two mechanisms, answering two different questions.

**Mondrian conformal prediction** answers *how confident is this score?* Calibrated per stratum
(Mondrian, rather than a single global calibration) so that the confidence claim holds within rail
and segment, not just on average. Standalone PR-AUC **0.2753**.

**Density estimation (ECOD)** answers *how unusual is this event?* It is an unsupervised channel that can
in principle fire on an attack shape no label has ever described. Standalone PR-AUC **0.0083.**

We report that second number as measured. The density channel is the theoretically appealing route to
catching genuinely novel attacks, and empirically it contributes very little at this scale. Reporting
the disappointing measurement is more useful than describing the appealing mechanism.

### 10.4 Fusion, and the calibration path

Channels are combined and mapped to a calibrated probability through isotonic regression, then to
one of three action bands (§11).

The combine rule was selected by ablation across eight named arms, not chosen by intuition. That
ablation found a serious defect in the rule we had been about to ship (§17.1).

---

## 11. From a score to an action

A score is not a fraud control. This section is the part most detection work omits.

### 11.1 Three bands

Three ordered strengths of response: **add friction ≤ route to review ≤ decline.** Thresholds are
fitted per rail against a cost matrix.

The ordering is enforced structurally. A configuration in which a rail's friction threshold exceeds
its review threshold is incoherent, and a guard refuses to ship it, which caught a real bug
(§17.2).

### 11.2 The action is rail-specific because the band is abstract

The same band means different things on different rails:

| rail | add friction | stop it |
|---|---|---|
| card, online with 3-D Secure | step-up challenge | decline |
| UPI payment | interstitial warning | cooling-off delay |
| UPI autopay mandate | refuse the mandate | refuse the mandate |
| account-to-account transfer | name-mismatch warning | hold the funds |
| card clearing and dispute | route to review | route to review |
| agentic commerce | refuse the mandate | refuse the mandate |

**Look at the clearing row.** You cannot decline a clearing record: the transaction has already
happened; the record is a settlement artefact. Both bands therefore map to review. A system that
emitted "decline" for a clearing record would be emitting an instruction no rail can execute.

Similarly for a mandate: the meaningful intervention is to refuse the mandate itself rather than to
decline one execution, because declining one execution leaves the standing authority in place.

### 11.3 Reason codes

Every decision carries one of **54 fixed reason codes.** Not free text, not a feature-importance
vector, but a code from a closed vocabulary that an operations team can build a runbook against and an
analyst can dispute.

A score with no explanation is not something an issuer can act on, and it is not something a customer
can be told.

### 11.4 Abstention, priced

Conformal abstention routes uncertain cases to a human rather than guessing. **We count what that
costs.** Abstention that is treated as free is a way to make a metric look good by moving the work
somewhere the metric does not measure.

### 11.5 Operational properties

Model version pinning, so a scored decision can be attributed to a specific model. Measured tail
latency rather than an average. The layer-0 fallback of §10.1.

### 11.6 The cross-issuer risk exchange

Mule-account risk is shared between institutions through a Bloom-filter-based exchange: an issuer can
learn that an account has been seen in mule-like patterns elsewhere **without any personal data
crossing the boundary,** and without either party learning the other's book. This is the mechanism
that turns the network's position from a vantage point into a distribution channel (§8.4).

---

## 12. Evaluation protocol

The protocol is the part of this work we would most want a reviewer to attack, so it is specified in
full.

### 12.1 Time-forward split, with purge and embargo

**No random splits anywhere.**

| slice | rows |
|---|---|
| train | 5,444,817 |
| statistics fitting | 989,967 |
| test | 2,672,910 |
| boundary rows discarded | **791,973** |

A **5.3-day purge** and a **5.2-day embargo** sit at the boundary, and the 791,973 rows inside them
are discarded rather than assigned to either side. The reason is label latency: an event just before
the boundary may have a label that resolves just after it, so including it leaks the future in a way
a naive time split does not prevent.

### 12.2 Entity-level sealed holdout

**1,791,118 rows are excluded from training** to keep the holdout genuinely held out. Sealing is at
the **entity** level, not the row level: if an account, device or merchant appears in a sealed
family, all of its rows are excluded, including its benign ones.

Row-level sealing would leak. The model would learn the entity's benign behaviour, and at test time
face an attack by an entity whose baseline it already knows, a materially easier problem than the
one we claim to measure.

Sealed content: **12 whole attack families**, plus a **leave-one-morpheme-out arm** in which one
entire EVASION morpheme (low-visibility-rail) is withheld across every family that uses it.

The leave-one-morpheme-out arm is the stronger test. Withholding a family withholds a combination;
withholding a morpheme withholds an entire *technique*, everywhere it appears.

### 12.3 Truth definition

The headline is measured against **oracle attack truth**: ground truth about which events were
generated as attacks.

Agreement with the realised late-arriving label channel is a **different question**, and we report it
separately rather than letting it hide inside the headline: PR-AUC **0.2573** over 21,723 flagged
cases, of which **6,805 (31.3%) were not attacks at all.**

Both numbers are reported. Neither is presented as the other. An earlier version of our evaluation
used a union of the two truth sources, which made the headline unfalsifiable, a case where our own
review found a contradiction and we changed the reported quantity.

### 12.4 The reportability guard

Any metric computed at reduced scale is stamped **not reportable** inside the artefact that carries
it, with the minimum positive count required for a headline recorded alongside. A smoke-scale number
therefore cannot travel into a slide by accident, because the artefact itself refuses the promotion.

### 12.5 Metric selection, and why not ROC-AUC

We report PR-AUC, recall at a fixed low false-positive rate, precision at a capacity-derived k, and a
value-detection rate.

**ROC-AUC is computed and is not the headline.** At a base rate of 0.5581%, ROC-AUC is dominated by
the true-negative mass and sits near 1.0 for any competent model. That is why nearly every submission
in this space reports ~0.99 and none of those numbers are comparable to each other. Ours is 0.7221 on
a metric that actually moves.

We compute it anyway, because refusing to produce a number a judge asks for reads as evasion.

### 12.6 k is derived from staffing, not chosen

**k = 641** is not a round number and was not selected to flatter a curve. It is analysts × cases ×
shifts from the operations configuration, scaled to the test population. Alerts above review capacity
are not alerts; they are a backlog.

---

## 13. Anti-leakage suite: six controls, all gating

All six run on every build. Any failure stops the build.

| # | control | what it proves | result |
|---|---|---|---|
| 1 | commit-order audit | the sealed attack manifest was committed **before** any detector code existed | PASS |
| 2 | RNG stream audit | all 51 seed families derive distinct key-derived random streams, so no two families share a draw sequence | PASS |
| 3 | label-time audit | every label used arrived **after** its own event and inside its channel window | PASS |
| 4 | entity audit | no entity identifier is shared between training rows and holdout-family rows | PASS |
| 5 | statistic-fit audit | cohort baselines, quantile edges and cold-start priors are fitted on the training slice only | PASS |
| 6 | leakage linter | no feature name, configuration value or rule string references a held-out family | PASS |

**Control 1 deserves emphasis.** It reads version-control history to prove the holdout was written
down before the detector was written. This is not a modelling control: it is a control on the team.
Nobody asks for it, and it is the cheapest available proof that the holdout was not adjusted after
seeing results.

*A disclosure about where control 1 passes.* Its PASS is recorded in the evidence produced on the
training host, whose repository carried the fine-grained commit history the check reads. The
published repository squashes that early development history into a single initial commit, so a
fresh clone reports control 1 as **SKIPPED-UNVERIFIABLE** rather than PASS. The check refuses to
assert an ordering it cannot see, which is the correct behaviour. The other five controls verify
from the published repository unchanged. We state this rather than let a reviewer re-run the suite
and find a skip where this table says PASS.

Control 5 covers a leak that is easy to miss and easy to make: fitting a quantile edge or a cohort
baseline on the full timeline leaks distributional information about the test window into a feature
definition, without any row crossing the split.

---

## 14. Results

Issuer position. Test window **2,672,910 rows**, **14,918 attacks**, base rate **0.5581%**. Leakage
suite 6/6 PASS. All figures measured.

### 14.1 Headline

| metric | value | denominator / note |
|---|---|---|
| **PR-AUC** | **0.3512** | 62.9× lift over the base rate |
| **recall @ 0.1% FPR** | **0.3142** | realised FPR 0.000999 |
| **precision @ k = 641** | **0.9953** | 638 of 641 alerts are real attacks |
| **value-detection rate** | **0.5517** | share of fraud *value* caught |
| precision / recall / F1 | 0.6382 / 0.3142 / 0.4211 | at the fitted operating threshold |
| ROC-AUC | 0.7221 | computed, not the headline; see §12.5 |

### 14.2 How to state precision@k without misleading

**0.9953 at k = 641 against 14,918 attacks means the queue is nearly pure. It does not mean we catch
nearly everything.** Always paired with recall 0.3142.

A precision figure quoted alone, at a k the reader cannot see, is the oldest way to mislead with a
fraud metric. Both numbers are true simultaneously: of what we hand analysts, 99.5% is real fraud; of
all fraud, we hand them 31%. Those are answers to different questions and both are operationally
meaningful: the first sets analyst trust, the second sets loss exposure.

### 14.3 Generalisation to withheld compositions

The question the challenge actually asks.

| population | attacks | recall at operating threshold |
|---|---|---|
| compositions **never** trained on | **7,785** | **0.2507** |
| compositions trained on | 7,133 | 0.3834 |
| generalisation gap | n/a | **0.1327** (65% retained) |

**52.2% of test attacks are compositions the model has never seen.** Withheld: 12 families plus the
entire low-visibility-rail EVASION morpheme.

Two observations. First, a model trained on a random split **cannot produce this number at all**,
because it has seen every composition, so this is not a metric on which we can be compared to a
conventionally-trained model, and that asymmetry is the reason the protocol matters. Second, **the
gap is the honest cost of generalisation.** A gap of zero would be evidence that the holdout was not
actually held out.

### 14.4 Against the incumbent

Recall at 0.1% FPR, **+0.2832** over the modelled incumbent policy, 95% CI **[0.2760, 0.2918]**.

Reporting rule applied throughout: **any delta whose confidence interval includes zero is reported as
"no measured effect", not as a pass.** Absolute numbers appear only alongside their deltas.

### 14.5 Economics

Measured on withheld populations only, with every loop-discovered composition excluded, so the
economic figure is not contaminated by the circularity of scoring attacks our own loop found. Both
figures are **simulator-internal rupees**, labelled as such.

Reported as a pair (value of fraud stopped, and value of good customers declined) because a system
that stops nothing and a system that declines everything both look good on a single number. The
declined figure covers the **automatic-decline band only**; friction and review are priced
separately, and exist precisely to move volume out of decline.

The band thresholds are fitted against a cost matrix that is a **swept parameter, not a claim.** A
different assumed lifetime cost of a false decline moves this trade-off directly, which is why it
ships as a trade-off rather than a headline.

---

## 15. Controlled comparisons

### 15.1 The modelled incumbent

Runs in shadow over the same stream (§6.4), so the comparison is same-rows, same-truth. Result in
§14.4.

### 15.2 The baseline replica, which beats us

We **executed** the conventional approach rather than describing it. Same feature matrix, same
gradient-boosting library, same hyper-parameters. **Six methodology differences only:**

1. random split spanning the whole timeline, instead of time-forward;
2. fully matured labels, instead of point-in-time visibility;
3. unlabelled treated as negative, instead of PU learning;
4. no reject inference for the incumbent policy's selection effect;
5. no entity-level sealed holdout;
6. no purge or embargo at the split boundary.

On the same rows with the same truth vector:

| arm | PR-AUC | note |
|---|---|---|
| the replica, on rows it never trained on | **0.4168** | |
| VAJRA, same rows, same truth | **0.3464** | |
| **delta** | **−0.0704** | **the replica wins** |

The replica's own published-style headline would be ROC-AUC **0.8558**, a *different metric*, not
comparable to the three PR-AUC figures beside it, and shown separately for exactly that reason.

**Why we show this.** The replica is not a better model; it is a model that was told the answers. It
trained on a random slice spanning our test window and on labels that had months to mature. Neither
of its numbers is attainable at decision time. We could have omitted this comparison and nobody would
have known to ask for it.

**The natural experiment that isolates the cause.** We added five features closing a genuine coverage
hole on two rails. The replica gained **+0.0047** PR-AUC from them. We gained **−0.0024**. The
features are identical; the only difference on that axis is label maturity. The replica could learn
from them because its labels had resolved; we could not because ours had not. That is a direct
measurement of the mechanism, not an argument about it.

### 15.3 A comparison we retracted

An earlier draft compared our 0.3511 against a replica figure of 0.2262. That comparison was
**invalid** and we withdrew it: the 0.2262 was computed on a different truth vector, over a different
row subset, in a different window: three mismatches presented as one comparison. It was replaced by
the same-rows / same-truth block in §15.2, which is the comparison that makes the replica look
*better*, not worse.

---

## 16. Ablations

### 16.1 Per-channel, scored alone

| channel | PR-AUC alone | ROC-AUC alone |
|---|---|---|
| supervised | 0.3505 | 0.7234 |
| conformal | 0.2753 | 0.7233 |
| density | 0.0083 | 0.6404 |
| sketch | 0.0044 | **0.3632** |
| beneficiary | 0.0056 | **0.5000** |

Two of these are broken, and this cheap diagnostic is how we found out (§17.1).

### 16.2 Fusion arms

| arm | PR-AUC |
|---|---|
| equal weights | 0.0317 |
| **the weights we were about to ship** | **0.0842** |
| drop the dead channels | 0.1865 |
| Fisher tail combination | 0.3264 |
| supervised + conformal, 75/25 | 0.3450 |
| supervised + conformal, 90/10 | 0.3509 |
| **supervised alone** | **0.3515** |

Selected: **supervised alone**, and the same arm was selected independently at **all four deployment
positions**. Selection was subject to a hard constraint that the resulting action ladder must remain
non-degenerate at every rail (§17.2).

### 16.3 Visibility

§8.2.

### 16.4 The loop itself

The loop is run with control arms, including the arm with the return path cut. **A closed loop that
cannot show its own contribution is a claim, not a mechanism**, and the reason to run the arms is to
avoid making one. Where the measured lift is small, the interface and the record say so.

---

## 17. Self-audit: what our instruments found in our own system

This section exists because the instruments existed. Every finding below was produced by a check we
chose to build, and several were in the configuration we would otherwise have submitted.

### 17.1 The fusion combiner was discarding a 4× better model

**Found by:** scoring every channel alone (§16.1).

Two channels were dead. One returned an **identically constant value across all 2,672,910 rows** (one
distinct value) because the five features it needs are among the 73 an issuer genuinely cannot
observe (§8.3), so at this position it had nothing to compute. The other was **anti-predictive**, at
ROC-AUC 0.3632: reliably worse than a coin. **Between them they carried 0.22 of the fused score.**

The shipped rank-average fusion scored **0.0842** PR-AUC. The supervised channel alone scored
**0.3505**, 4.2× higher.

**Attribution:** **+0.2673 to the combine rule, +0.0026 to calibration.** This was a design error,
not a tuning miss.

**Why it was invisible:** a rank average is scale-free, so a channel weighted 0.10 can reorder any two
rows whose fused ranks lie within 0.10 of each other, and the top-641 rows span a rank gap of
**0.00024**. A constant channel and an inverted channel therefore had authority over exactly the
region that determines precision@k.

**Two proposed fixes were refuted by measurement.** Both took the form "report on the fused ranking
instead"; measurement showed the top-641 sets were 641/641 identical, so neither proposal changed
anything. They were dropped rather than shipped as improvements.

### 17.2 A friction cap could escalate an entire rail into automatic declines

**Found by:** a guard that refuses to ship a collapsed action ladder.

The capacity-driven friction cap interacted with band-ordering enforcement such that, on committing
the selected fusion arm, two rails collapsed, one carrying 8.07% of volume, mapping their friction
band into decline. That is a rail-wide outage dressed as a threshold.

**Fix:** a second friction pass that computes the share already above the review band and targets the
cap at the union, then clamps the friction threshold to the review threshold, so friction can never
be stricter than review.

**On the regression test:** our first two synthetic scenarios both *passed on the old code*: they did
not reproduce the bug and so proved nothing. Reproducing it required at least five bulk rails plus a
hot rail at roughly 0.5% volume. A regression test that does not fail against the unfixed code is not
a regression test, and we rewrote it until it did.

### 17.3 Two perfect one-sided separators, deleted

Two features separated attacks perfectly in one direction. A perfect separator at this base rate is
overwhelmingly more likely to be an artefact of the generator than a discovery about fraud. Both were
deleted.

### 17.4 An instrument reporting a fabricated zero

One instrument reported 0.0000 for a quantity it was not actually computing. A fabricated zero is
worse than a missing value, because it reads as a measurement. Fixed.

### 17.5 An artefact magnitude we got wrong twice before getting it right

We reported an artefact exposure of 0.5907, then repeated an external review's figure of 0.949,
before establishing the correct value of **0.0560**. Both errors had the same cause: measuring on the
feature's own support rather than on the full population. Recorded here because the error class,
conditioning a population-level claim on a subpopulation, is one a reviewer should check us for
elsewhere.

### 17.6 Where our generator flatters us

We ranked every feature by how well it alone separates attacks and went looking for signals that were
suspiciously strong. Flag threshold: 25% of the headline. **Nothing exceeds 21.1%.** Two disclosures:

**Session duration**: standalone recall **0.0662**, bounded at **21.1%** of the headline on 12.66% of
rows. Ordinary sessions are drawn |N(6, 4)| minutes; coerced attack sessions |N(145, 70)|. The
distributions barely touch: benign **maximum 36.5** against attack **5th percentile 33.9**.

The mechanism is real: authorised-push-payment fraud genuinely does involve hour-long coerced
sessions. But a real benign session-duration distribution is heavy-tailed, so the separation here is
sharper than production would give. **The right fix is generator realism, not deleting a legitimate
signal because we drew it too cleanly.**

**Token assurance against device age**: ROC-AUC **0.9652**, but on only **2.23%** of rows, worth
**6.8%** of the headline. Every attacked provisioning draws a uniform device age, and our generator
**omits the commonest benign case**: a customer adding an existing card to a newly purchased phone.

**And one feature we chose not to build.** Attack cash-out withdrawals are quantised to exactly
₹5,000. An amount-collision feature would have topped this chart and fired almost exclusively on
attacks. **We did not add it**, and recorded that as a decision rather than leaving it as an
omission, because the signal would have been a property of our generator, not of fraud.

**Also, pre-empting a likely question:** 8 of the top 25 features have standalone ROC-AUC below 0.5.
That is expected, not a defect. A tree ensemble uses those features through interactions, and
marginal predictive power is not the quantity that matters for them.

---

## 18. Reproducibility and determinism

**One command regenerates every number in this document.** Seeded, ordered, and single-threaded on
the paths where thread scheduling would otherwise affect floating-point reduction order, so a rebuild
is byte-comparable rather than merely statistically similar.

Every stage writes a structured machine-readable record, and a single evidence index ties each claim
to the record that produced it. The reportability guard of §12.4 prevents reduced-scale numbers from
being quoted as results.

Random streams are key-derived per family, so adding a family does not perturb the draws of existing
ones, verified as control 2 of §13. Without that property, adding one attack family would silently
change every previously measured number.

**The demo runs against a committed replay bundle.** No training, no network. A live demo that
depends on either is a demo that fails in a room with three hundred people on one access point.

---

## 19. The interactive surface

Six screens, each answering one question. The design constraint throughout: **show how the attack
happened and how it was identified**, not just the verdict.

| screen | question |
|---|---|
| economics | what does this stop, and what does it cost good customers? |
| attack space | how many distinct attacks, and how much of the space is reached? |
| fidelity | what does the build refuse to emit? |
| results | what does it catch, and against what comparisons? |
| the loop | did the closed loop actually buy anything? |
| author an attack | compose one yourself and watch it run |

### 19.1 Author-an-attack

A reviewer composes a six-slot attack. The picker is **constrained to type-valid combinations**:
illegal values are shown disabled with the reason, so the type system is visible rather than
described. The composition then compiles, executes in the simulator, passes the invariant gate, and
is scored against the **promoted** model, not one retrained for the demo.

What comes back is the walkthrough, in three steps: **did it compile** (with the archive cell it
occupies and the observable signatures it resolves), **how the attack happened** (events generated,
invariant violations, end-to-end latency), and **how we identified it** (the outcome split across
caught / abstained / structurally blocked / slipped through, plus a per-event score trace showing the
band and the reason codes the decision actually carried).

The screen states the §4.5 bound on the same page: what you authored is new to the model but inside
the grammar.

### 19.2 An architectural note worth recording

The read-only screens render **entirely on the server**, reading committed records directly from disk.
They make no client-side data request at all.

This was a rewrite, and the reason is instructive. The original screens fetched through a proxy to a
local service. That chain has four independent failure modes (the service dying, the runtime
resolving localhost to IPv6 against an IPv4-only bind, a stale client bundle, and a hydration error),
and **all four present identically**, as a loading skeleton that never resolves. During preparation we
spent real time distinguishing between them.

Reading from disk on the server removes all four. The only remaining requirement is that the record
exists, and when one does not, the screen says which one rather than hanging. One interactive island
remains for live authoring, isolated so that if the composer service is unreachable it degrades to a
message while the surrounding walkthrough still renders.

One further detail, small and worth knowing: the record writer emits bare `NaN` for undefined
statistics, which is not valid JSON and which a strict parser rejects outright. A single such value
blanked an entire screen. The loader now rewrites non-finite values to null in value position only,
so one undefined statistic renders as an absent field instead of destroying the page.

---

## 20. What is new here

### 20.1 An honest statement of what kind of novelty this is

The components are published methods. Quality-diversity archives, Watkins Q(λ), Thompson sampling,
non-negative PU learning, inverse-propensity reject inference, Mondrian conformal prediction, ECOD
density estimation and gradient-boosted trees are all prior work, and we cite them as such rather
than dressing them up. **No new algorithm is claimed.**

What is new is the *system*, and specifically six choices that we have not seen made together. Each
of them is a choice to make something checkable that is usually asserted, and each has a measured
consequence somewhere in this document. That is the edge we would defend: not a better estimator,
but an architecture in which the claims can be falsified.

### 20.2 The six choices

**1. Attacks are a typed language, not a list.** Nearly all work in this space enumerates scenarios,
twenty or thirty named attack types, and reports performance on them. Here an attack is a sentence in
a six-slot grammar with a pairwise compatibility relation, giving 15,271 legal compositions out of
188,160 raw. The type system is not a filter for plausibility; it is a semantic constraint, and it
makes rejection *explanatory*. Asking for a beneficiary leg on a rail that terminates in physical
cash returns the constraint that failed, not a boolean. The practical consequence is that novelty
becomes measurable: a composition can be withheld and then presented, which a scenario list cannot
do.

**2. The adversary is driven by the defence's measured blind spots.** The quality-diversity archive is
not a diversity metric computed after the fact; it is the curriculum. Cells where the defence detects
nothing are sampled more on the next round. This is what makes the loop adversarial rather than
iterative, and we run it with the return path cut as a control arm so the contribution is compared
instead of asserted (§16.4).

**3. Rail semantics are build gates, not tests.** 126 invariants stop the build rather than logging a
warning. The distinction matters under deadline pressure: a test suite whose failures are triaged
gets its assertions relaxed, whereas relaxing a gate is a visible edit to the gate. These gates
failed 13,009 times during development and we fixed the generator every time (§7.2). We know of no
comparable submission where fidelity is a build-time constraint rather than a claim in a write-up.

**4. Label scarcity is the primary design constraint, not an inconvenience.** Only 2.50% of the
training window carries any visible label. Rather than train on matured labels and report the
resulting number, three composed corrections address the three distinct biases: PU learning at the
*realised* class prior, reject inference against the logged incumbent policy, and explicit
label-maturity weights. **These corrections make our headline worse and our honesty better**, which
is precisely why §15.2 exists.

**5. Generalisation is measured by construction, not inferred.** Sealing is at the entity level, so an
account in a withheld family contributes none of its rows, not even its benign ones. Row-level
sealing would let the model learn an entity's baseline and then face that entity's attack, which is a
materially easier problem. On top of the twelve withheld families sits a leave-one-morpheme-out arm
that removes an entire evasion *technique* everywhere it appears. The result is that 52.2% of test
attacks are compositions never trained on, and **a model trained on a random split cannot produce
this number at all**, because it has seen every composition. That asymmetry is the point of the
protocol.

**6. The output is an action, not a score.** Three ordered bands map to what each rail can actually
execute, which is why a clearing record routes to review in both bands: you cannot decline a
transaction that has already happened. Every decision carries one of 54 fixed reason codes.
Abstention is priced rather than treated as free. With no model at all, the structural layer still
refuses the impossible. Most detection work stops at the score and leaves this to somebody else.

### 20.3 The instruments are the contribution

The clearest evidence that the architecture works is that it caught our own mistakes.

Scoring each channel alone is a cheap diagnostic that almost nobody runs. It showed two dead channels
holding 0.22 of the fused score, which led to a combiner that was discarding a model **4.2× better**
than we were reporting, with the improvement attributed **+0.2673 to the combine rule against +0.0026
to calibration** (§17.1). A band-ordering guard caught a friction cap that could escalate an entire
rail into automatic declines (§17.2). An artefact audit found and bounded the two places our own
generator flatters us, and a deliberate decision not to build a third (§17.6).

The same discipline produced three disclosures that cost us: a conventional baseline that beats us by
0.0704 PR-AUC, published together with the natural experiment isolating why (§15.2); a comparison we
withdrew as invalid once we noticed it mismatched truth, population and window (§15.3); and a
magnitude we got wrong twice before getting it right (§17.5).

**A system that cannot find its own defects has not been instrumented, it has been demonstrated.**
That is the distinction we would want judged.

---

## 21. Limitations and known-open items

Stated by us. A limitation a reviewer finds is worth more against us than one we hand over.

### 21.1 Limitations of the approach

**Everything is simulated.** We validate mechanism fidelity, not distributional fidelity to any real
portfolio (§2.2). This is the ceiling on every absolute number in §14.

**Two signals are too clean.** Quantified and bounded at 21.1% and 6.8% of the headline (§17.6).

**Novelty is bounded by the grammar.** Compositional novelty within six typed slots, not open-ended
invention of attack categories (§4.5).

**A single global operating threshold penalises low-value rails.** Attacks whose entire mechanism is
to stay beneath a floor are exactly the ones a single cut-off handles worst. Per-rail thresholds exist
for the *bands*; the operating threshold used for the headline recall figure is global.

### 21.2 Known-open items: found, not yet fixed

**The queue-capacity check measures the wrong quantity.** It counts the **review band**, but real
human workload is set by the **action mapping**, and one rail (card clearing and dispute) maps all
three bands to review. True load is therefore approximately **0.54% of volume against a 0.0240%
staffed budget**, roughly 22× over. The check as written does not catch this. Found by us; not fixed
at submission.

**Two rails remain weak.** Assisted cash-out and offline UPI Lite carry observables our feature layer
now reads, but at 2.50% label maturity the model cannot learn them: the measured gain from adding
those features was **+0.0001 PR-AUC**. **We report the null result** rather than dropping the work
and rather than claiming the features helped.

**The density channel underperforms its rationale.** 0.0083 PR-AUC standalone (§10.3). It is the
theoretically right mechanism for genuinely novel attacks and it is not currently earning its place.

### 21.3 What we would do next

Replace the parameterised session-duration and device-age draws with heavy-tailed distributions fitted
to published aggregate statistics, which would retire the §17.6 disclosures rather than bound them.
Re-derive the capacity check from the action mapping rather than the band. Extend the seed families to
reach the 112 unreached archive cells. Fit per-rail operating thresholds rather than one global cut.

---

## 22. Number index

Every figure quoted in this document, with its denominator. All measured at the full preset unless
marked.

**Generation**
| quantity | value |
|---|---|
| payment events | 9,899,667 |
| label records | 374,077 |
| rails | 12 |
| seed families | 51 |
| realised attack share | 0.69% (configured 0.50%) |
| base-rate divergence, before → after control | 4.1× → 1.38× |

**Attack space**
| quantity | value |
|---|---|
| raw slot cross-product | 188,160 |
| type-legal compositions | 15,271 |
| rejected as impossible | 172,889 |
| feasible archive cells | 380 |
| cells reached | 268 (70.5%) |
| reason codes | 54 |

**Fidelity**
| quantity | value |
|---|---|
| rail invariants, enforced at build | 126 |
| peak build-stopping violations during development | 13,009 |
| observables resolved | 236 (58 schema / 115 feature / 63 design-only) |
| unresolved observables | 0 |

**Split**
| quantity | value |
|---|---|
| train / statistics / test rows | 5,444,817 / 989,967 / 2,672,910 |
| purge / embargo | 5.3 d / 5.2 d |
| boundary rows discarded | 791,973 |
| rows excluded for the sealed holdout | 1,791,118 |
| label maturity in the training window | 2.50% |

**Test population**
| quantity | value |
|---|---|
| rows | 2,672,910 |
| attacks | 14,918 |
| base rate | 0.5581% |

**Detection**
| quantity | value |
|---|---|
| PR-AUC | 0.3512 |
| recall @ 0.1% FPR | 0.3142 (realised FPR 0.000999) |
| precision @ k = 641 | 0.9953 (638 / 641) |
| precision / recall / F1 | 0.6382 / 0.3142 / 0.4211 |
| value-detection rate | 0.5517 |
| ROC-AUC | 0.7221 |

**Generalisation**
| quantity | value |
|---|---|
| recall, never-trained compositions | 0.2507 over 7,785 attacks |
| recall, trained compositions | 0.3834 over 7,133 attacks |
| gap | 0.1327 (65% retained) |
| share of test attacks never trained on | 52.2% |
| withheld EVASION morpheme | low-visibility-rail |

**Comparisons**
| quantity | value |
|---|---|
| vs modelled incumbent, recall @ 0.1% FPR | +0.2832, 95% CI [0.2760, 0.2918] |
| vs baseline replica, same rows / same truth PR-AUC | −0.0704 (0.3464 vs 0.4168) |
| replica's own-style headline | ROC-AUC 0.8558 (a different metric) |
| natural experiment: gain from 5 added features | replica +0.0047, us −0.0024 |
| label-channel agreement PR-AUC | 0.2573 over 21,723 flagged, 31.3% not attacks |

**Model**
| quantity | value |
|---|---|
| features total / at issuer | 392 / 319 |
| best boosting iteration | 221 of 600 |
| leakage controls | 6 / 6 PASS |

**Channels alone**: supervised 0.3505 · conformal 0.2753 · density 0.0083 · sketch 0.0044 ·
beneficiary 0.0056 (PR-AUC)

**Fusion arms**: equal 0.0317 · about-to-ship 0.0842 · drop-dead 0.1865 · Fisher 0.3264 ·
90/10 0.3509 · **supervised alone 0.3515 (selected, all four positions)**

**Deployment positions**: issuer 0.3142 (319 features) · network 0.2885 (316) · acquirer 0.2088
(212) · payee PSP 0.2075 (191)

**Artefact bounds**: session duration 21.1% of headline on 12.66% support · token assurance vs
device age 6.8% on 2.23% support · flag threshold 25% · maximum observed 21.1%

**Known-open**: queue load ≈ 0.54% of volume against a 0.0240% staffed budget · weak-rail feature
gain +0.0001 PR-AUC
