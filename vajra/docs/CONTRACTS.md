# VAJRA interface contracts

This file is authoritative. Where a subsystem's code and this document disagree, the
document is the bug report. Every boundary below has a test in `tests/` that asserts the
shape actually crossing it.

Five boundaries carry the whole system:

```
GRAMMAR ──strings+cell──▶ ARENA ──CampaignIntent──▶ vajra-sim ──CanonicalEvent──▶ GATE
                             ▲                           │                          │
                             │                           └──matured labels──▶ FORGE │
              AttackHypothesisRequest                                               │
                             └────────────── GAP MINER ◀────escapes+attributions────┘
```

---

## 1. GRAMMAR → ARENA

A **composition** is a six-slot typed string:

```
ACCESS=<a>/TRUST=<t>/RAIL=<r>/EVASION=<e>/MONETISATION=<m>/LABEL=<l>
```

Slot order is fixed and canonical. `grammar.composition.Composition.parse()` is the only
parser; nothing else may split on `/`.

A composition **type-checks** iff every pairwise constraint in `grammar/typing.yaml`
admits it. Type-checking is a property of the string alone.

A composition's **cell** is `cell_of(composition, plan)` — published as executable code
in `grammar/cell_of.py`, not left implied. It returns
`(rail_class, locus, evasion, depth)`.

> Two of the four axes are **many-to-one projections** of a slot (RAIL 12 → RAIL-CLASS 6,
> ACCESS 8 → LOCUS 4). One axis, **KILL-CHAIN DEPTH, is not a slot at all** — it is
> derived from the plan's stage count. So a grammar string alone does **not** determine
> its cell, and `cell_of` takes the plan too. Anyone reading "a cell freezes rail, locus,
> evasion and depth" would be misled and we do not write that.

The mutation taxonomy that follows, computed by the same function:

| Mutation | Cell effect |
|---|---|
| MONETISATION, LABEL, TRUST | **always cell-preserving** |
| EVASION (identity mapping), any depth change | **always cell-crossing** |
| ACCESS, RAIL | **conditionally either**, decided by the projection; printed per pair by `make archive-report` |

Therefore: same-cell sibling recall is the **easy tier**; the headline is a
**cross-cell sibling whose EVASION morpheme is mutated**.

## 2. ARENA → sim: `CampaignIntent`

`loop/contracts.py::CampaignIntent`. JSON-serialisable, seeded.

| Field | Type | Meaning |
|---|---|---|
| `campaign_id` | `str` | `CMP-<8 hex>`, derived from the intent content — same intent, same id |
| `grammar_str` | `str` | the six-slot composition |
| `family_id` | `str` | `ATK-*` for seeds, `GEN-*` for Composer output; selects the RNG stream |
| `arm` | `dict` | bandit arm: `amount_band`, `mcc`, `entry_mode`, `acquirer`, `hour`, `fan_out` |
| `budget_inr` | `float` | attacker currency budget; the campaign stops when spent |
| `rng_stream` | `str` | `attack.family.<family_id>` — the separate-stream holdout control |
| `expected_signatures` | `list[str]` | schema field paths the composition claims to move |
| `stages` | `list[str]` | kill-chain stages; `len(stages)` drives KILL-CHAIN DEPTH |
| `sealed` | `bool` | true iff `family_id` is in `grammar/sealed_manifest.yaml` |
| `blind_composer` | `bool` | true iff authored with no defender feedback |

**Invariant asserted at the boundary:** every string in `expected_signatures` resolves to
a field name in `sim/schema.py::CANONICAL_FIELDS`. A composition claiming a signature no
observer can see is rejected at admission, not archived.

## 3. sim → GATE: `CanonicalEvent`

One schema for all rails (`sim/schema.py`). Two rules:

*   **Semantic field-group names on every surface.** `emv_cryptogram_*`,
    `threeds_*`, `cvm_result`, `avs_result`, `cvv2_result`, `acceptor_descriptor`.
    Exact numbering lives only in `sim/field_map.yaml` with a per-entry
    `verified: true|false`, and never reaches a screen. One wrong subelement number
    spoken confidently to a payments judge costs the room.
*   **Labels are never a column on the event.** They live in an append-only label table
    keyed `(event_id, channel, as_of_ts, label)` and every training or evaluation row
    resolves its label through an `as_of` read.

## 4. GATE → everything: `Decision`

`gate/decision.py::Decision`.

| Field | Type | Notes |
|---|---|---|
| `event_id` | `str` | |
| `persona` | `"GATE-I" \| "GATE-B"` | one codebase, two personae |
| `score` | `float` | calibrated, **never rounded on the wire** — a real 2.2e-12 must not render as "0.0000" and look like a broken model |
| `reason_codes` | `list[str]` | from the fixed vocabulary in `governance/reason_codes.yaml`; free text is not permitted in a review queue |
| `action` | `str` | `approve \| friction \| review \| decline \| hold \| freeze_recommend \| collect_suppress \| mandate_refuse` |
| `band` | `str` | `approve \| friction \| review \| auto_decline` — the three-band decomposition |
| `latency_ms` | `float` | measured, not budgeted |
| `attribution` | `dict[str,float]` | per-component contribution; the input to the distinctness test |
| `component_scores` | `dict[str,float]` | `g0,g1,g2_conformal,g2_density,sketch,gate_b` |
| `conformal_p` | `float \| None` | low p = "unlike anything in my calibration set" |
| `abstained` | `bool` | abstention is **priced, not free**: benign abstention rate is reported per rail |
| `guard_rule` | `str \| None` | the triggering G0 rule id, if any |

## 5. GAP MINER → ARENA: `AttackHypothesisRequest`

| Field | Meaning |
|---|---|
| `escape_region_text` | plain English conjunction over reviewable features, e.g. `"approved region: authenticated-ECI, token assurance low, device age <1d, ticket ₹1,800–2,000"` |
| `cell_id` | the archive cell the escapes concentrate in |
| `signatures` | schema fields the region is expressed over |
| `n_escapes` / `n_caught` | the region's support, so a one-row "region" is visibly not a finding |

That sentence does three jobs: it is the Composer's payload, it is the human-readable
justification for firing the red team (which is what makes the autonomy auditable rather
than magical), and it is the most legible thing on the LOOP screen.

---

## Determinism: what we guarantee and what we do not

**Guaranteed, and tested:**

*   Byte-stable **logical** Parquet hash for the simulator at fixed seed + config
    (`core/io.py::table_hash`, `tests/test_determinism.py`). We hash the logical table,
    not the file bytes, because writer-version strings move on a pyarrow bump and a
    file-hash test that goes red on a dependency upgrade is a test that gets deleted.
*   Byte-identical LightGBM artifacts at fixed seed, fixed feature order and
    `num_threads=1`. Multithreaded histogram binning is **not** bit-reproducible, so the
    CI training run pins one thread and the demo run may use all cores and says so.
*   Named RNG streams derived by KDF from the stream **name**, so adding a stream or
    reordering execution cannot perturb another stream (`core/rng.py`).
*   Composer responses content-hash-cached into `attack/cache/`; `LLM_MODE=cached` is the
    default and never touches the network.

**Not guaranteed, stated rather than implied:** the GRU (G3) and RGCN (G4) are not
bit-reproducible across BLAS/cuDNN builds. We assert metric reproducibility within a
stated tolerance band for those two and label it.

---

## The five leakage controls, and which file enforces each

| Level | Control | Enforced by |
|---|---|---|
| Simulator | separate RNG stream per family; sealed manifest hash-committed pre-modelling | `core/rng.py::family_stream`, `eval/leakage/commit_order.py` |
| Label | no row may read a label whose `as_of_ts` exceeds its window end | `eval/leakage/label_time.py` |
| Aggregate | no training row shares entity/device/mule/campaign id with a holdout family | `eval/leakage/entity_audit.py` |
| Statistic | cohort baselines, quantile edges, scalers, isotonic and conformal calibration sets fitted **causally on the training window with holdout-family rows excluded** | `eval/leakage/statistic_fit.py` |
| Feature | no feature name, rule string or config value references a held-out family id | `eval/leakage/linter.py` |

The statistic-level control is the one an entity-id audit cannot see: a cohort baseline
fitted over a pool containing sealed-family rows imports holdout information into *every*
training feature without a single id crossing the boundary.

---

## Metric reporting contract

No metric is a bare absolute. Every rate in `reports/metrics.md` carries:

1.  a bootstrap 95% CI (Wilson for per-family recall),
2.  a delta versus the **modelled incumbent** on identical traffic,
3.  a delta versus the **baseline-equivalent replica** — XGBoost-style GBDT on a pooled
    non-temporal split with no G0, no G2 and no GATE-B, scored through the identical
    harness,
4.  the base rate and label-maturity fraction it was measured at.

**Any metric whose CI includes zero effect is reported as "no measured effect", not as a
pass.** `eval/metrics/reporting.py::Measured` enforces this at the type level: a
`Measured` renders itself as `no measured effect` when its interval spans zero, so a
caller cannot accidentally print a point estimate as a result.
