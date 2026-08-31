# VERIFY_REGISTER.md

Every `[VERIFY]` marker in the repo. Each is a verifiable claim we REFUSED TO FAKE,
against a field that would state the same claim as fact without checking. Not knowing
is not the failure; asserting is.

**65 markers.** Machine-counted by `make verify`.

| File | Line | Claim |
|---|---|---|
| README.md | 73 | make money duallog verify report bundle # the MONEY data, the dual-use reject log, [VERIFY] register, roll-up, replay bundle |
| README.md | 117 | - **`VERIFY_REGISTER.md`** — every `[VERIFY]` marker, each a claim we refused to fake. |
| attack/dual_use_lint.py | 102 | "Describe the mechanism generically and mark the specifics [VERIFY].", |
| bench/harness.py | 6 | it measures. We do NOT extrapolate to network scale [VERIFY on real hardware]. |
| bench/harness.py | 114 | "[VERIFY on real hardware]. The predictor is named because claiming the Treelite fast " |
| bundles/replay/report.md | 43 | - [VERIFY] markers: 58 — verifiable claims we refused to fake |
| config/ops.yaml | 6 | # Nothing in this file is [VERIFY]-clean: it is all stipulated. It is stated as |
| config/ops.yaml | 40 | # All three channels' timings are [VERIFY] against network reporting semantics and |
| config/ops.yaml | 65 | # because added UPI friction is bounded by NPCI UX rules [VERIFY scope] and the PIN |
| config/scenario.yaml | 46 | # choice: no public UPI transaction-level corpus exists to fit this to [VERIFY]. |
| docs/RESEARCH.md | 10 | details as `[VERIFY]`; the *claim* attributed to it is standard enough that the |
| docs/RESEARCH.md | 165 | transaction-level UPI/RTP fraud corpus we are aware of `[VERIFY]`, so 3DS field |
| features/builder.py | 1109 | # are [VERIFY]; the no-exchange fallback is published as its own view in the ablation, so this |
| features/registry.yaml | 187 | - {name: mandate_amount_vs_afa_band, lineage: "distance to the AFA-exempt band. The band value is [VERIFY] and swept"} |
| features/registry.yaml | 208 | swept config parameters and are [VERIFY] where they correspond to regulatory bands. |
| features/registry.yaml | 285 | - {name: creditor_name_match_score, lineage: "confirmation-of-payee outcome. Whether an equivalent exists per rail is [VERIFY]"} |
| features/registry.yaml | 453 | - {name: initiation_mode_ordinal, lineage: "UPI initiation-mode encoding. The NPCI code table is [VERIFY]; ours is semantic"} |
| fidelity/provenance.py | 7 | where no public transaction-level corpus exists [VERIFY]; and BAF, which we DEMOTE FROM T1 |
| fidelity/provenance.py | 52 | "no public UPI/RTP transaction-level corpus [VERIFY], so those cannot be T1 and are not " |
| fidelity/provenance.py | 104 | "grounds": "India rail mix against a band derived from config, no public corpus to fit [VERIFY]", |
| fidelity/provenance.py | 158 | "transaction-level fraud corpus [VERIFY], so 3DS co-occurrence, mandate conformance, " |
| gate/decision.py | 26 | #: additional factor and added friction is bounded by NPCI UX rules [VERIFY scope], so the UPI |
| gate/decision.py | 170 | SHAPED, NOT CONFORMANT, and we call it that: the real mechanics are [VERIFY]. Two properties |
| gate/decision.py | 195 | "freeze process are [VERIFY]; this is a payload of the right shape, described as " |
| gate/gate_b.py | 48 | Its real-world availability and regulatory permissibility are UNVERIFIED [VERIFY]. We do not |
| gate/policy.py | 45 | #: NPCI UX rules [VERIFY scope]. |
| gate/views.yaml | 33 | returning a score in a private-use field, ASSIGNMENT PER NETWORK [VERIFY]. We deliberately do |
| gate/views.yaml | 86 | placement: Network-side advice, returning a score in a private-use field [VERIFY assignment]. |
| gate/views.yaml | 100 | Real-world availability and regulatory permissibility are UNVERIFIED [VERIFY]. We do not claim |
| governance/model_card.md | 23 | network scale [VERIFY on real hardware]. Circularity is bounded, not eliminated. |
| grammar/enumerate_space.py | 5 | provenance and [VERIFY] fields, and (c) the LLM Composer, which is invoked ONLY on a Gap Miner |
| grammar/signatures.yaml | 245 | reason: "Secure-remote-commerce recognition flow is [VERIFY] and not modelled (ATK-T3)." |
| grammar/slots/evasion.yaml | 39 | [VERIFY per jurisdiction], which is what makes this durable. |
| grammar/slots/label.yaml | 69 | report at 45-120+ days [VERIFY current semantics and deadlines]. By the time labels |
| grammar/slots/rail.yaml | 84 | is bounded by NPCI UX rules [VERIFY scope] -- our response is an interstitial, a cooling |
| grammar/slots/rail.yaml | 97 | visibility case [VERIFY current collect caps and restrictions]. |
| grammar/slots/rail.yaml | 109 | band are the threshold-hugging observable [VERIFY current AFA threshold]. |
| grammar/slots/rail.yaml | 122 | SHAPED, not conformant, and we call it that [VERIFY]. |
| grammar/slots/rail.yaml | 135 | [VERIFY UPI Lite posting behaviour and limits]. |
| grammar/slots/rail.yaml | 146 | and victims complain late. THIN EMITTER [VERIFY current Aadhaar-lock and onboarding rules]. |
| grammar/slots/rail.yaml | 159 | UI. THIN EMITTER [VERIFY agentic field naming and protocol status as of 2026]. |
| grammar/slots/trust.yaml | 62 | reputation bureau exists and attribution across protocol hops is unsettled [VERIFY]. |
| grammar/slots/trust.yaml | 64 | provenance_note: Field naming is ILLUSTRATIVE, declared so in the schema and in the UI [VERIFY agentic field naming and protocol status as of 2026]. |
| scripts/report.py | 95 | A(f"- [VERIFY] markers: {v['n_markers']} — verifiable claims we refused to fake") |
| scripts/verify_register.py | 1 | """`make verify` — scan the repo for [VERIFY] markers and render VERIFY_REGISTER.md. |
| scripts/verify_register.py | 3 | The design's posture: 25 [VERIFY] markers are 25 verifiable claims we REFUSED TO FAKE, each naming the |
| scripts/verify_register.py | 15 | _RX = re.compile(r"\[VERIFY[^\]]*\]") |
| scripts/verify_register.py | 33 | print(f"\n=== VAJRA [VERIFY] REGISTER ===\n {len(hits)} markers across the repo") |
| scripts/verify_register.py | 38 | "Every `[VERIFY]` marker in the repo. Each is a verifiable claim we REFUSED TO FAKE,", |
| sim/field_map.yaml | 25 | All four are [VERIFY]. Networks and PSOs carry their own profiles and subelement |
| sim/field_map.yaml | 104 | note: Exemption scope and threshold values per jurisdiction are [VERIFY]. |
| sim/field_map.yaml | 202 | compelling-evidence rule versions and monitoring-programme thresholds are all [VERIFY], |
| sim/field_map.yaml | 228 | returns, is [VERIFY]. Our message shape is SHAPED, not conformant, and we call it that. |
| sim/field_map.yaml | 236 | The NPCI initiation-mode code table is [VERIFY]. Our values are semantic ("intent", |
| sim/field_map.yaml | 251 | note: UPI COLLECT caps, restrictions and current status are [VERIFY]. |
| sim/field_map.yaml | 260 | note: The e-mandate AFA-exempt threshold is [VERIFY] and is a SWEPT CONFIG PARAMETER here. |
| sim/field_map.yaml | 274 | as of 2026 are all [VERIFY]. These names are OUR INVENTION for modelling purposes and the |
| sim/labels.py | 17 | chargeback / network 45-120+ d [VERIFY current semantics and deadlines] |
| sim/rails/a2a.py | 23 | #: A2A thresholds (IMPS/NEFT/RTGS-shaped bands). ALL [VERIFY] and swept; geometry only. |
| sim/rails/thin.py | 11 | [VERIFY]. We model "weakened central velocity visibility" as a reconciliation LAG and a |
| sim/rails/thin.py | 15 | biometrics [VERIFY current Aadhaar-lock and onboarding rules]. |
| sim/rails/thin.py | 17 | There is no standard we are asserting conformance to [VERIFY protocol status as of 2026]. |
| sim/rails/upi.py | 30 | #: Rupee thresholds that matter on UPI. ALL [VERIFY] and all swept config-shaped values; here |
| sim/rails/upi.py | 34 | #: The AFA-exempt band an e-mandate debit can be pinned under. [VERIFY current threshold] — |
| sim/rails/upi.py | 496 | # [VERIFY] and swept; what we model is the PINNING, not the number. |
