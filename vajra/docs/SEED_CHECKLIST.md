# Seed self-review checklist

The 51 hand-authored seed compositions in `grammar/seeds.yaml` are **self-reviewed against this
checklist**. No outside practitioner has reviewed them, and nothing in this repo says
practitioner-reviewed or expert-audited — we are 2–4 builders with no payments practitioner on the
team, and any team claiming thousands of expert-validated attacks in three weeks is not telling the
truth. This checklist is the standard each row was held to, published so the review is auditable
rather than asserted.

Each row must satisfy:

1. **It is a composition, not prose.** The six-slot grammar string type-checks against
   `grammar/typing.yaml`. `make grammar` asserts this for every row — a prose row fails the build.
2. **≥ 3 RESOLVED observable signatures.** Each signature resolves to a canonical schema field or a
   registry feature via `grammar/signatures.py`. Design-only observables (real, but not built) stay
   listed for breadth and do **not** count. A row that cannot reach three resolved signatures must be
   marked `double_dagger: true` (excluded from every scored result) — a row we cannot compute three
   observables for cannot be a scored family.
3. **A named observer.** At least one party whose `gate/views.yaml` view grants the signals. `†` marks
   a signal held by no single party in our two personae (reachable only via the bloom stub or the
   no-exchange fallback); `‡` marks a signal outside both personae entirely (excluded from scoring).
4. **Abstraction level only.** Kill-chain shape, attacker economics, observable signatures. No
   operational tradecraft, no vendor-specific bypass, no real BINs/IINs/IFSCs/VPAs/PII. `genai_delta`
   describes changes in cost, scale and adaptivity — never method. Enforced by
   `attack/dual_use_lint.py`, which fails the build.
5. **`stages`.** The kill-chain stage list, which is what determines KILL-CHAIN DEPTH (depth is not a
   grammar slot). The declared depth must be admissible for the composition.
6. **A `why_hard` sentence.** Why a competent incumbent misses it — the detection challenge, in one
   sentence a reviewer can disagree with.

**The audit that carries weight is at the booth.** A judge picks five rows and audits them live
against this checklist — a real practitioner review of a small sample, rather than a claimed review of
a large one. The `make grammar` machine gate plus a 10% self-audit at freeze (published as n, reject
count and a Wilson 95% interval) is what stands behind the rest.
