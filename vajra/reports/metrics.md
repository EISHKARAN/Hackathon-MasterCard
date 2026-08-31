# VAJRA — reported metrics

> Every number below is a MEASUREMENT from this run, not a target. Each carries its denominator, its interval, and the two deltas the reporting contract requires.

**Population.** 2,672,910 rows in the time-forward TEST window (never trained on, never calibrated on). 14,918 attack events. Base rate configured 0.500%, realised 0.558%. Label maturity: 3.3% of rows have any visible label at the window end.

## Headline

| Metric | Value | Notes |
|---|---|---|
| Recall @ 0.10% FPR | 0.3142 | realised FPR 0.0009996 on 2,657,992 legitimate rows |
| PR-AUC (average precision) | 0.3512 | degrades honestly under imbalance where ROC-AUC does not |
| Precision@k (operational) | 0.9953 | k=641; derived from config/ops.yaml: 40 analysts x 60 cases x 1 shifts = 2400/day = 0.02400% of a 10,000,000-authorisation reference portfolio, scaled to this test population (2,672,910 rows) |
| Precision@k (stability companion) | 0.9953 | k=641; NOT the operational k — the capacity k above governs |
| Value-detection rate | 0.5517 | count-recall 0.3142 — they diverge, and the divergence is the informative part |
| Precision / Recall / F1 | 0.6382 / 0.3142 / 0.4211 | at the fixed-FPR operating threshold |
| Accuracy | 0.9952 | reported for completeness; at this base rate a model that approves everything scores near-perfect accuracy |
| ROC-AUC | 0.7221 | **not the headline**, and the reason is in the JSON next to it |

## The two deltas every metric carries

- **vs the modelled incumbent:** 0.2832 (95% CI [0.276, 0.2918], n=2672910)
- **vs the baseline-equivalent replica:** -0.06167 (95% CI [-0.06712, -0.0545], n=2672910)

ANY DELTA WHOSE CI INCLUDES ZERO IS REPORTED AS 'NO MEASURED EFFECT', NOT AS A PASS. Absolute numbers appear only alongside both deltas.

## The baseline, executed rather than described

One model. One feature matrix. One library. Three numbers.

| What is being measured | Number |
|---|---|
| (1) What a random-split submission puts on a slide | ROC-AUC 0.8558 |
| (2) Same model on our test window, WITHOUT removing rows it trained on | PR-AUC 0.2386 (contaminated: 75.0% of the window was in its own training set) |
| (3) Same model on rows it genuinely never saw | PR-AUC 0.2196 (n=668,794) |

Three numbers from ONE model, one feature matrix and one library. (1) `self_reported_headline.roc_auc`: what a random-split submission puts on a slide. (2) `contaminated_metrics_on_our_test_set`: the same model on our time-forward test window WITHOUT removing the rows it already trained on -- this is what happens if you evaluate a random-split model on a temporal holdout naively, and it is inflated because a share of that window was in its own training set. (3) `honest_metrics_on_our_test_set`: the same model on the rows it genuinely never saw. The gap between (2) and (3) is a DIRECT MEASUREMENT of what a random split buys you, and the gap between (1) and (3) is what the whole protocol buys.

## Per-family recall — no aggregation, no minimum target

No aggregation and NO MINIMUM TARGET. Families at zero recall are NAMED, because a pooled number would hide exactly the families that matter most.

| Family | Positives | Caught | Recall | Wilson 95% CI | Underpowered |
|---|---|---|---|---|---|
| ATK-A2 | 35 | 0 | 0.000 | [0.000, 0.099] |  |
| ATK-U11 | 936 | 0 | 0.000 | [0.000, 0.004] |  |
| ATK-U6 | 2408 | 0 | 0.000 | [0.000, 0.002] |  |
| ATK-U10 | 357 | 1 | 0.003 | [0.000, 0.016] |  |
| ATK-U2 | 152 | 1 | 0.007 | [0.001, 0.036] |  |
| ATK-K3 | 207 | 6 | 0.029 | [0.013, 0.062] |  |
| ATK-G2 | 343 | 14 | 0.041 | [0.024, 0.067] |  |
| ATK-X2 | 206 | 14 | 0.068 | [0.041, 0.111] |  |
| ATK-Z4 | 471 | 36 | 0.076 | [0.056, 0.104] |  |
| ATK-G1 | 397 | 32 | 0.081 | [0.058, 0.112] |  |
| ATK-Z2 | 111 | 9 | 0.081 | [0.043, 0.147] |  |
| ATK-X1 | 92 | 11 | 0.120 | [0.068, 0.202] |  |
| ATK-P1 | 74 | 13 | 0.176 | [0.106, 0.278] |  |
| ATK-S1 | 192 | 48 | 0.250 | [0.194, 0.316] |  |
| ATK-Z1 | 238 | 61 | 0.256 | [0.205, 0.315] |  |
| ATK-A1 | 195 | 53 | 0.272 | [0.214, 0.338] |  |
| ATK-M1 | 184 | 59 | 0.321 | [0.257, 0.391] |  |
| ATK-U1 | 266 | 91 | 0.342 | [0.288, 0.401] |  |
| ATK-V3 | 332 | 114 | 0.343 | [0.294, 0.396] |  |
| ATK-B1 | 553 | 192 | 0.347 | [0.309, 0.388] |  |
| ATK-A3 | 158 | 55 | 0.348 | [0.278, 0.425] |  |
| ATK-G5 | 224 | 84 | 0.375 | [0.314, 0.440] |  |
| ATK-X3 | 202 | 83 | 0.411 | [0.345, 0.480] |  |
| ATK-M3 | 355 | 147 | 0.414 | [0.364, 0.466] |  |
| ATK-M2 | 924 | 386 | 0.418 | [0.386, 0.450] |  |
| ATK-C2 | 262 | 111 | 0.424 | [0.365, 0.484] |  |
| ATK-U7 | 226 | 100 | 0.442 | [0.379, 0.508] |  |
| ATK-S2 | 249 | 113 | 0.454 | [0.393, 0.516] |  |
| ATK-P3 | 265 | 126 | 0.475 | [0.416, 0.536] |  |
| ATK-C1 | 256 | 125 | 0.488 | [0.428, 0.549] |  |
| ATK-C5 | 137 | 69 | 0.504 | [0.421, 0.586] |  |
| ATK-U5 | 152 | 77 | 0.507 | [0.428, 0.585] |  |
| ATK-U9 | 63 | 32 | 0.508 | [0.388, 0.627] |  |
| ATK-U3 | 165 | 85 | 0.515 | [0.439, 0.590] |  |
| ATK-U4 | 336 | 174 | 0.518 | [0.465, 0.571] |  |
| ATK-D1 | 321 | 174 | 0.542 | [0.487, 0.596] |  |
| ATK-U8 | 226 | 130 | 0.575 | [0.510, 0.638] |  |
| ATK-C3 | 160 | 93 | 0.581 | [0.504, 0.655] |  |
| ATK-Z3 | 212 | 124 | 0.585 | [0.518, 0.649] |  |
| ATK-T1 | 74 | 45 | 0.608 | [0.494, 0.711] |  |
| ATK-D3 | 250 | 160 | 0.640 | [0.579, 0.697] |  |
| ATK-C4 | 249 | 167 | 0.671 | [0.610, 0.726] |  |
| ATK-V1 | 242 | 167 | 0.690 | [0.629, 0.745] |  |
| ATK-K2 | 191 | 132 | 0.691 | [0.622, 0.752] |  |
| ATK-D2 | 106 | 74 | 0.698 | [0.605, 0.777] |  |
| ATK-T4 | 200 | 142 | 0.710 | [0.644, 0.768] |  |
| ATK-T3 | 191 | 139 | 0.728 | [0.661, 0.786] |  |
| ATK-P2 | 155 | 119 | 0.768 | [0.695, 0.827] |  |
| ATK-G4 | 303 | 240 | 0.792 | [0.743, 0.834] |  |
| ATK-V2 | 150 | 120 | 0.800 | [0.729, 0.856] |  |
| ATK-T2 | 165 | 139 | 0.842 | [0.779, 0.890] |  |

**Families at zero recall, named rather than averaged away:** ATK-A2, ATK-U11, ATK-U6


## Recall stratified by entity age

The 0-1d bucket is reported WITHOUT EXCUSE. A model that only works on aged entities is a model that only works on the fraud you already stopped.

| Age band | Positives | Recall | Wilson 95% CI |
|---|---|---|---|
| 0-1d | 6074 | 0.235 | [0.225, 0.246] |
| 1-7d | 862 | 0.622 | [0.589, 0.654] |
| 7-30d | 136 | 0.272 | [0.204, 0.352] |
| 30d+ | 5912 | 0.291 | [0.280, 0.303] |
| unknown | 1934 | 0.497 | [0.475, 0.520] |

## False positives on the adversarially-legitimate cohorts

The design's +-0.05pp guardrail needs ~1e5-1e6 rows per cohort per arm. What we assert is: UPPER BOUND OF THE BOOTSTRAP 95% CI ON FP MOVEMENT <= +0.25pp, with the realised MDE printed beside every cohort.

These cohorts are OUR construction, not a validated public benchmark. The claim is 'we tested the twelve hardest benign cases we could specify', not 'we tested the industry's'.

| Cohort set | n | FPR | Wilson 95% CI | Realised MDE (pp) |
|---|---|---|---|---|
| hard_benign_12 | 6,744 | 0.1028 | [0.0957, 0.1102] | 0.1525 |
| hard_benign_b | 2,870 | 0.0006969 | [0.0002, 0.0025] | 0.2338 |
| ordinary benign | 2,648,378 | 0.0007408 | | |

## Action bands, in absolute daily counts

Scaled to a stated 10,000,000-authorisation reference portfolio. Absolute counts matter because a '0.05pp' movement is thousands of events per day — roughly twice the whole staffed queue.

| Band | Share | Count in population | Scaled daily count |
|---|---|---|---|
| approve | 97.3892% | 2,603,125 | 9,738,918 |
| friction | 2.0463% | 54,696 | 204,631 |
| review | 0.0228% | 609 | 2,278 |
| auto_decline | 0.5417% | 14,480 | 54,173 |

**The queue ceiling, printed rather than left to be derived:** at a 0.500% base rate on 10,000,000 authorisations/day, 50,000 frauds/day against a staffed budget of 2,400 cases/day — so the REVIEW BAND ALONE cannot exceed **4.8% recall** before precision is even discussed.


## Abstention, priced

ABSTENTION IS PRICED, NOT FREE. These rates are reported next to every 'caught' number, because a system that abstains on everything has caught nothing.

- benign abstention rate, ordinary traffic: 5.2228%
- benign abstention rate, HARD-BENIGN-12: 41.6815%
- benign abstention rate, HARD-BENIGN-B: 5.9582%
- attack abstention rate: 44.2150%


## Single-institution visibility ablation (never cut)

We expect recall materially lower at the acquirer and payee-PSP views and set NO FLOOR there. An acquirer cannot construct PAN-canonical aggregation because it does not hold the token-to-PAN map; the features are ABSENT, not zeroed.

| View | Recall | Delta vs full | Share of full |
|---|---|---|---|
| acquirer | 0.2088 | -0.1054 | 0.6646 |
| issuer | 0.3142 | +0.0000 | 1 |
| network | 0.2885 | -0.0257 | 0.9183 |
| payee_psp | 0.2075 | -0.1067 | 0.6603 |

## Leakage suite

| Control | Level | Status |
|---|---|---|
| commit_order_audit | simulator | PASS |
| rng_stream_audit | simulator | PASS |
| label_time_audit | label | PASS |
| entity_audit | aggregate | PASS |
| statistic_fit_audit | statistic | PASS |
| leakage_linter | feature | PASS |

Any FAIL fails the build. A SKIPPED-UNVERIFIABLE is reported as a skip and never counted as a pass — a pass we did not earn would be the most misleading line in the whole report.

