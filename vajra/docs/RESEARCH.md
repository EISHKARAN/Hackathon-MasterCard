# Research grounding

Every architectural choice in VAJRA that could have gone another way is argued here
against literature rather than taste. Two conventions, applied without exception:

*   **`[retrieved]`** — the citation was pulled from a live literature search during the
    build and the title/authors/venue/year below are as returned by that search.
*   **`[from-memory]`** — a standard reference we cite from knowledge, where we have
    **not** re-verified the exact venue or year in this build. Treat the bibliographic
    details as `[VERIFY]`; the *claim* attributed to it is standard enough that the
    argument does not rest on the citation being exact.

We do not claim novelty for any component below. The novelty claim is confined to the
four things §2 of the solution design names. What this file establishes is that the
conventional parts are conventional *for a reason we can cite*.

---

## 1. Why the inline scorer is a gradient-boosted tree ensemble, not a deep tabular model

This is the single most consequential model choice in the repo and it is the one a judge
is most likely to poke, because "we used a transformer" sounds more modern.

| Source | What it establishes |
|---|---|
| Grinsztajn, Oyallon & Varoquaux, *Why do tree-based models still outperform deep learning on typical tabular data?*, NeurIPS 2022 `[retrieved]` (~3.9k citations) | On typical tabular data, tree ensembles beat deep architectures; the causes named are robustness to uninformative features, invariance to feature rotation, and the ability to learn irregular target functions. All three describe our feature matrix exactly: ~380 heterogeneous, human-authored, individually-meaningful features with irregular thresholds. |
| Shwartz-Ziv & Armon, *Tabular data: Deep learning is not all you need*, Information Fusion 2022 `[retrieved]` (~3.3k citations) | Deep tabular models that beat GBDTs in their own papers fail to do so under a uniform hyper-parameter search protocol. Directly relevant: we cannot afford a large HPO budget, and a model whose advantage is contingent on one is the wrong choice. |
| McElfresh et al., *When do neural nets outperform boosted trees on tabular data?*, NeurIPS 2023 Datasets & Benchmarks `[retrieved]` | Characterises *when* NNs win: large row counts and low feature heterogeneity. Our regime is the opposite corner — high heterogeneity, and a positive count in the low thousands even at `--preset full`. |
| Shmuel, Glickman & Lazebnik, arXiv:2408.14817, 2024 `[retrieved]` | A later, broader benchmark reaching the same conclusion, which matters because "that was 2022" is the obvious rebuttal to Grinsztajn. |
| Schmitt, *Deep learning vs. gradient boosting … for credit scoring*, arXiv:2205.10535, 2022 `[retrieved]` | The same finding inside the financial-risk domain specifically. |

**Decision: LightGBM for G1.** Additionally, and separately from accuracy: LightGBM
exports to a Treelite `.so`, which is what makes the inline latency story credible, and
it produces exact SHAP values via TreeSHAP in microseconds, which is what makes the
fixed reason-code vocabulary derivable rather than decorative. A deep model would cost us
both.

**Where deep models are used, and why that is consistent.** G3 (GRU over event sequences)
and G4 (RGCN over the entity graph) are deep, and they run **near-line, off the critical
path**, writing entity risk back to the online store. That is not a contradiction: the
literature above is about *tabular* prediction, and sequence and graph structure are
exactly the two regimes where the tabular result does not apply.

| Source | What it establishes |
|---|---|
| Johannessen & Jullum, *Finding money launderers using heterogeneous graph neural networks*, J. Finance and Data Science 2025 `[retrieved]` | Heterogeneous GNNs on real bank transaction networks add signal over tabular baselines for laundering-shaped behaviour — the GATE-B / ATK-G family regime. |
| Arslan et al., *Fraud Detection Using Graph Neural Networks: A Survey*, 2026 `[retrieved]` | Surveys GNN use for mule-account detection in payment networks specifically; also the source for the standard caveat that graph inference is not an authorisation-path operation. |

That caveat is why the **cold-graph fix** exists: cheap streaming sketch counters inline
so graph signal exists at t=0, GNN embeddings near-line. We do not claim live graph
traversal in the authorisation path.

## 2. Why the metric set is what it is

| Source | What it establishes |
|---|---|
| Dal Pozzolo, Caelen, Le Borgne, Waterschoot & Bontempi, *Learned lessons in credit card fraud detection from a practitioner perspective*, Expert Systems with Applications 2014 `[retrieved]` (~860 citations) | The alert-precision framing: a fraud model's useful output is bounded by investigator throughput, so evaluation must be at a k the institution can staff. This is the source of **precision@k with k derived from `config/ops.yaml` staffing**, not from an arbitrary threshold. |
| Dal Pozzolo, Boracchi, Caelen, Alippi & Bontempi, *Credit card fraud detection: a realistic modeling and a novel learning strategy*, IEEE TNNLS 2017 `[retrieved]` (~1k citations) | Two things we implement directly: (a) **undersampling shifts the posterior** and requires an explicit correction before probabilities can be fed a cost matrix — implemented in `gate/fusion/calibration.py`; (b) **verification latency** — labels arrive late, so a realistic evaluation must be time-forward with delayed supervision, which is the whole of `sim/labels/` and `eval/splits/`. |
| Dal Pozzolo et al., *Credit card fraud detection and concept-drift adaptation with delayed supervised information*, IJCNN 2015 `[retrieved]` | The delayed-label + drift combination our three-channel label engine models. |
| Carcillo, Dal Pozzolo, Le Borgne, Caelen et al., *SCARFF: a scalable framework for streaming credit card fraud detection with Spark*, Information Fusion 2018 `[retrieved]` | Establishes undersampling > oversampling in this regime; we therefore do not ship SMOTE and say why. |
| Saito & Rehmsmeier, 2015 `[from-memory]` | PR curves are more informative than ROC under extreme class imbalance. This is why PR-AUC/average precision is a headline and **ROC-AUC on a random split is on the "will not report" list** — though we compute ROC-AUC anyway, because refusing to compute a number a judge asks for reads as evasion. |

**Decision: the headline set is** recall @ fixed low FPR (per rail), PR-AUC / average
precision, precision@k at staffed capacity, value-detection rate, per-family recall with
Wilson intervals, recall stratified by entity age, and ROC-AUC reported *alongside* with
the one-sentence explanation of why it is not the headline. `make eval` computes all of
them; `eval/metrics/` has one module per metric and no metric is computed inline.

## 3. Why feature engineering looks like this

| Source | What it establishes |
|---|---|
| Bahnsen, Aouada, Stojanovic & Ottersten, *Feature engineering strategies for credit card fraud detection*, Expert Systems with Applications 2016 `[retrieved]` (~700 citations) | Two results we implement: **transaction-aggregation features** (velocity panels over entity keys and windows), and **periodic time-of-day features via the von Mises distribution**, which the paper reports as worth an average 13% increase in savings over aggregation alone. `features/temporal.py` implements the von Mises encodings and cites this paper in the registry lineage field. |

The dual encoding of every velocity feature — **as a ratio to the entity's own trailing
baseline** *and* as a peer-cohort percentile — is our addition on top, and its motivation
is adversarial rather than statistical: an attacker who keeps every per-token counter
sub-threshold defeats a single absolute encoding.

## 4. Why abstention is Mondrian conformal, and why we say coverage is *measured*

| Source | What it establishes |
|---|---|
| Barber, Candès, Ramdas & Tibshirani, *Conformal prediction beyond exchangeability*, Annals of Statistics 2023 `[retrieved]` (~800 citations) | Conformal validity rests on exchangeability, and time-series/drifting data violates it; the paper gives the framework for what survives. This is the source of our stated admission that **time-forward payment data violates exchangeability, so we measure empirical coverage against nominal rather than assuming it.** |
| Zhou, Chen, Gui & Cheng, *Conformal prediction: a data perspective*, ACM Computing Surveys 2025 `[retrieved]` | Survey coverage of Mondrian (group-conditional) CP and its use where marginal coverage would hide per-group failure — our channel × MCC-band × region conditioning. |
| Althani, *Class-Conditional Conformal Prediction for Reliable Anomaly Detection Under Extreme Class Imbalance*, MAKE 2026 `[retrieved]` | Mondrian CP specifically under extreme imbalance, including the thin-stratum problem. This is why `gate/g2_novelty/conformal.py` enforces a **minimum calibration count per stratum with an explicit merge rule** and publishes which strata merged. |

**Decision:** Mondrian conformal p-values for abstention, with (a) empirical vs nominal
coverage published per stratum, (b) a minimum-count merge rule, (c) **abstention priced**
— the benign abstention rate per rail is reported next to every "caught" number, because
an abstention that fires on ordinary traffic is friction an issuer pays for.

The unsupervised density channel is **ECOD** (Li et al., IEEE TKDE 2022 `[from-memory]`;
the method is confirmed as standard by several `[retrieved]` papers that benchmark
against it). Chosen because it is parameter-free, deterministic and O(nd) — no
autoencoder to train, no reproducibility caveat. **The one implementation trap, recorded
because it silently destroyed a previous build:** the raw ECOD score is a *sum* of
per-feature negative-log tail probabilities over ~380 features, so its natural range is in
the hundreds, and comparing it against a z-score threshold of 3.0 flags every row. Our
implementation calibrates its own score distribution at `fit()` and exposes `score_z()`;
if it is uncalibrated it escalates nothing rather than everything.

## 5. Why the label problem is PU learning plus reject inference

| Source | What it establishes |
|---|---|
| Elkan & Noto, *Learning classifiers from only positive and unlabeled data*, KDD 2008 `[from-memory]` | The estimator we use to correct the recent, unmatured window where absence of a fraud label is not evidence of legitimacy. |
| Kiryo, Niu, du Plessis & Sugiyama, *Positive-unlabeled learning with non-negative risk estimator*, NeurIPS 2017 `[from-memory]` | nnPU: the non-negative correction that stops the unbiased PU risk from diverging with a flexible model. |

**Non-SCAR, stated up front.** Both estimators are usually presented under SCAR
(selected completely at random). Our labelling is **not** SCAR: the never-labelled
synthetic-identity cohort makes labelling class-conditional. We therefore exercise these
estimators in their *favourable* case — π known from the simulator, and the incumbent
policy deciding with an **ε-randomised threshold so positivity actually holds** — and we
publish the propensity histogram, a sensitivity analysis to a misspecified propensity
model, and π off by ±2×. A deterministic rule engine would put propensities in {0,1},
leaving no overlap and undefined IPW weights; that is why `config/ops.yaml` carries an ε.

## 6. Why the archive is MAP-Elites

| Source | What it establishes |
|---|---|
| Mouret & Clune, *Illuminating search spaces by mapping elites*, arXiv:1504.04909, 2015 `[retrieved]` (~1.3k citations) | The algorithm: a behaviour-space grid holding **one elite per cell**, which is why occupied cells and archived elites are the same integer in our accounting and why CI asserts `occupied_cells == len(elites)`. Also the source of the property we actually want: illumination (mapping what is *possible*) rather than optimisation (finding one best). |
| Chen & Liu, *Illuminating Heuristic Design: Language-Model-Driven Quality-Diversity Evolution for Combinatorial Optimization*, IEEE TEVC 2026 `[retrieved]` | **An LLM as the variation operator inside a quality-diversity loop** — precisely our Composer's role. Establishes the pattern is a recognised design rather than an improvisation, and that the LLM belongs at the *mutation* step, not in the inner evaluation loop. |
| Gallotta, Liapis & Yannakakis, *Dynamic quality-diversity search*, GECCO 2024 `[retrieved]` | QD where the fitness landscape *moves*. This is exactly our situation — the defender retrains, so an elite's fitness is not stationary — and it is the citation behind re-evaluating archived elites after each FORGE stage rather than trusting a stale fitness. |

**Decision:** MAP-Elites over four interpretable behaviour axes, LLM as variation
operator at the plan level only, elites re-evaluated after each retrain, and coverage
reported **post** Jensen–Shannon distinctness merging so the number can go down.

## 7. Why the attacker is a reinforcement learner, and at which level

This is the part the design's ARENA is, formally, and `docs/RL_LOOP.md` gives the full
MDP. The literature it is built on:

| Source | What it establishes |
|---|---|
| Lunghi, Molinghen, Simitsis et al., *Fraud-RLA: A Reinforcement Learning Adversarial Attack Against Credit Card Fraud Detection*, IEEE Transactions on Dependable and Secure Computing 2026 `[retrieved]` | The closest prior work to our red side: an RL agent that learns to evade a card-fraud detector by interacting with it, observing only what an attacker can observe. Establishes (a) the formulation is sound, (b) the reward should be attacker profit rather than a detector score, and (c) evaluation must hold the detector frozen while the attacker searches, or attacker and defender co-drift into a meaningless number. Our **time-to-evade against a frozen GATE** is that control. |
| Vimal, Kayathwal, Wadhwa & Dhama, *Application of deep reinforcement learning to payment fraud*, arXiv 2021 `[retrieved]` | The mirror image — RL on the *defender* side, framing detection as a sequential decision problem under a cost structure. We deliberately do **not** do this (see below). |
| Chapelle & Li, *An empirical evaluation of Thompson sampling*, NeurIPS 2011 `[from-memory]`; Agrawal & Goyal, *Thompson sampling for contextual bandits with linear payoffs*, ICML 2013 `[from-memory]` | Thompson sampling's regret behaviour and its practical dominance over ε-greedy/UCB in the noisy-reward, non-stationary regime — which is what a fraud detector's feedback is. |
| Rahman, Redino, Nandakumar & Cody, *Reinforcement Learning for Cyber Operations*, 2025 `[retrieved]` | The general red-team-as-RL framing and the standard caveat that a simulator-trained cyber RL agent's competence is bounded by the simulator's fidelity — which is why our F1 invariant gate is *inside* the loop as the reward's feasibility gate. |

**Decision, and the deliberate asymmetry:** the **attacker learns; the defender does
not.** The attacker is an RL agent (§docs/RL_LOOP.md). The defender's fusion layer is
deliberately a rank-average plus isotonic calibration with monotone constraints — not a
learned stacker, and not an RL policy. The reason is stated as a decided position rather
than an omission: with simulator-derived fraud counts a learned stacker overfits, and a
promotion gate judged against a false-positive budget *we generated ourselves* is not a
gate. If the rank-average underperforms a stacker on our own data we will say so and
still ship the rank-average, because the number we would be optimising is not
trustworthy. Applying RL to the defender's threshold policy would compound that problem,
not fix it.

## 8. Simulator design

| Source | What it establishes |
|---|---|
| CardSim — *a Bayesian simulator for payment card fraud detection research* `[from-memory]`, surfaced via the Fraud-RLA paper `[retrieved]` | That a purpose-built payment-card simulator is an accepted research instrument, and the standard shape: priors over actor behaviour rather than row-level generative fitting. |
| PaySim, Sparkov, AMLSim `[from-memory]` | **Controls to beat in F2, never calibration targets.** Calibrating our simulator to another simulator is circular by construction, and we refuse it explicitly. |
| Grinsztajn et al. (above) | Indirectly relevant to the *generator*: because tree ensembles are robust to uninformative features, a generator that gets marginals right but structure wrong will still be caught by a discriminator on the **structure subspace**. That is why F2 reports two subspaces and expects CTGAN to be competitive on the aligned-marginal one by construction. |

## 9. What the literature does **not** support, stated so we do not lean on it

*   **No paper here supports our India-rail conditionals.** There is no public
    transaction-level UPI/RTP fraud corpus we are aware of `[VERIFY]`, so 3DS field
    co-occurrence, mandate conformance, clearing divergence, chargeback timing and UPI
    collect-accept behaviour are **T3: mechanistically enforced and self-reviewed against
    a published checklist**, not validated against real rows. No citation changes that.
*   **No paper here supports sibling-transfer recall**, because we have not found it
    reported in this literature. That is a novelty claim, and it is also an admission
    that it is unbenchmarked: we have no external number to compare ours to.
*   **The GNN papers report metrics on their own datasets.** We do not inherit their
    numbers, and no number in `reports/metrics.md` is imported from any paper above.
