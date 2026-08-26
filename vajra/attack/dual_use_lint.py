"""The dual-use lint. A BUILD GATE, not a policy document.

WHAT IT ENFORCES: the archive's unit of content is a KILL-CHAIN SHAPE, an ATTACKER COST STRUCTURE, and
a set of OBSERVABLE SIGNATURES IN PAYMENT DATA. Those three are exactly what a detector needs and are
insufficient to execute anything. A composition like

    ACCESS=authorised-but-deceived-payer / TRUST=aged-account / RAIL=upi-collect /
    EVASION=cohort-splitting / MONETISATION=biller-giftcard-resale / LABEL=victim-blames-self

tells a fraud team where to look and tells an attacker nothing they did not already know.

WHAT IT REJECTS: vendor-named bypass procedures, executable code, enumeration procedures, patterns
matching real BIN/IIN ranges or plausible PII, persuasive scam copy, and prose that reads as
INSTRUCTION rather than as SIGNATURE.

WHY THE REJECT LOG IS THE PART THAT MATTERS: a filter whose output you cannot see is an assertion,
while a log showing what was proposed and refused DEMONSTRATES that the boundary was enforced during
the build — and lets a reviewer disagree with a specific decision rather than with our
self-description. `make duallog` renders it, and it is a committed governance artifact.

ITS LIMITS, STATED WITH IT: it is pattern-based, it will miss paraphrase, and it is a FLOOR UNDER
human review rather than a substitute for it. It is deliberately crude, because a crude filter that
fails the build is more trustworthy than a clever one that fails silently.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from core.paths import paths

# ---------------------------------------------------------------------------------------
# Rules. Each carries an id, a rationale, and what a compliant alternative looks like.
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LintRule:
    id: str
    pattern: re.Pattern[str]
    rationale: str
    compliant_alternative: str
    severity: str = "reject"


def _rx(p: str) -> re.Pattern[str]:
    return re.compile(p, re.IGNORECASE)


RULES: tuple[LintRule, ...] = (
    LintRule(
        "DU-01",
        _rx(r"\b(bypass|circumvent|defeat|evade)\s+(the\s+)?(3ds|3-d\s*secure|liveness|kyc|otp|captcha|bot\s*defence|bot\s*defense)\b"),
        "Names a control and describes defeating it — that is a bypass procedure, not a signature.",
        "Describe the OBSERVABLE the bypass produces (e.g. 'field-combination implausibility with a high field-population score').",
    ),
    LintRule(
        "DU-02",
        _rx(r"\b(step\s*1|step\s*one|first,?\s+then|procedure:|instructions:|how\s+to\s+(?:obtain|generate|produce))\b"),
        "Reads as INSTRUCTION rather than as signature. The archive describes shapes, not recipes.",
        "State the kill-chain STAGE NAMES and the observables each stage produces.",
    ),
    LintRule(
        "DU-03",
        _rx(r"(?:^|\n)\s*(?:import\s+\w+|def\s+\w+\s*\(|curl\s+|POST\s+/|SELECT\s+.+FROM|<\?php|#!/)"),
        "Executable code inside an archive entry.",
        "Remove the code. A detector consumes distributions and field co-occurrences, not programs.",
    ),
    LintRule(
        "DU-04",
        _rx(r"\b(?:4[0-9]{15}|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"),
        "Matches a real-scheme IIN/BIN range and card-number length. Our identifiers are drawn from reserved non-routable prefixes and are deliberately non-Luhn-valid.",
        "Use the reserved 999xxx prefixes in sim/graph/entities.py::RESERVED_BIN_PREFIXES.",
    ),
    LintRule(
        "DU-05",
        _rx(r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b"),
        "Matches a plausible Indian mobile number. No real PII, ever.",
        "Use a synthetic handle from the reserved space; mobile numbers are not modelled at all.",
    ),
    LintRule(
        "DU-06",
        _rx(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
        "Matches a plausible IFSC code shape. No real institutional identifiers.",
        "Use the synthetic PSP ids (PSPnnn) the world builder generates.",
    ),
    LintRule(
        "DU-07",
        _rx(r"\b(?:enumerat\w+|brute[\s-]?forc\w+|card[\s-]?test\w+)\s+(?:script|tool|procedure|routine|loop)\b"),
        "An enumeration PROCEDURE. Card testing is in the taxonomy as a signature; the procedure is not.",
        "Describe the observable: distinct-PAN-per-terminal within tight BIN prefixes, near-uniform micro-amounts, decline-reason concentration.",
    ),
    LintRule(
        "DU-08",
        _rx(r"\b(?:visa|mastercard|amex|american\s+express|rupay|npci|upi\s+api|paytm|phonepe|gpay|razorpay)\b\s*(?:\w+\s+){0,3}(?:bypass|vulnerab\w+|exploit|weakness|flaw)\b"),
        "Vendor- or scheme-named vulnerability claim. We make no claims about any named product's security.",
        "Describe the mechanism generically and mark the specifics [VERIFY].",
    ),
    LintRule(
        "DU-09",
        _rx(r"\b(?:dear\s+(?:customer|sir|madam)|your\s+account\s+(?:has\s+been|will\s+be)\s+(?:suspended|blocked|frozen)|click\s+(?:here|the\s+link)|urgent(?:ly)?\s+(?:verify|update)|congratulations,?\s+you)\b"),
        "Persuasive scam copy / smishing template. We generate template FAMILIES with labelled generators, never persuasion.",
        "The detector needs the DISTRIBUTIONAL signature (near-duplicate embedding clusters, n-gram unlikelihood, metadata uniformity), not the content.",
    ),
    LintRule(
        "DU-10",
        _rx(r"\b(?:deepfake|face[\s-]?swap|voice[\s-]?clon\w+)\s+(?:pipeline|model|code|implementation|how|tutorial)\b"),
        "Describes building a deepfake or voice-cloning capability. We build none of that.",
        "Model the OBSERVABLE COHORT STATISTIC instead: device-model entropy collapse, ASN reuse, name n-gram unlikelihood, onboarding-to-first-credit latency.",
    ),
    LintRule(
        "DU-11",
        _rx(r"\b(?:cvv|cvc|cvv2)\s*[:=]\s*\d{3,4}\b|\bexpiry\s*[:=]\s*\d{2}\s*/\s*\d{2}\b"),
        "A concrete credential value.",
        "Credential values are never content. Reference the schema field name instead.",
    ),
    LintRule(
        "DU-12",
        _rx(r"\b(?:aadhaar|aadhar)\s*(?:number|no\.?|#)?\s*[:=]?\s*\d{4}\s*\d{4}\s*\d{4}\b"),
        "A plausible Aadhaar number shape. No real or realistic national identifiers.",
        "AePS is modelled by terminal-level population statistics only; no identity numbers exist in the schema.",
    ),
)


@dataclass
class LintHit:
    rule_id: str
    rationale: str
    compliant_alternative: str
    matched_text: str
    field_name: str

    def as_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "rationale": self.rationale,
            "compliant_alternative": self.compliant_alternative,
            # The matched text is TRUNCATED and the log is a governance artifact, so the log itself
            # never becomes the thing the lint exists to prevent.
            "matched_text": self.matched_text[:80],
            "field": self.field_name,
        }


@dataclass
class LintResult:
    ok: bool
    hits: tuple[LintHit, ...] = ()

    @property
    def rejected(self) -> bool:
        return not self.ok

    def explain(self) -> str:
        if self.ok:
            return "passed the dual-use lint"
        return "; ".join(f"{h.rule_id}: {h.rationale}" for h in self.hits)


def lint_text(text: str, *, field_name: str = "text") -> LintResult:
    hits: list[LintHit] = []
    for rule in RULES:
        m = rule.pattern.search(text or "")
        if m:
            hits.append(
                LintHit(rule.id, rule.rationale, rule.compliant_alternative, m.group(0), field_name)
            )
    return LintResult(ok=not hits, hits=tuple(hits))


def lint_record(record: Mapping[str, Any]) -> LintResult:
    """Lint every string field of a record (a Composer response, an archive entry, a write-up)."""
    hits: list[LintHit] = []
    for k, v in record.items():
        if isinstance(v, str):
            r = lint_text(v, field_name=str(k))
            hits.extend(r.hits)
        elif isinstance(v, (list, tuple)):
            for i, item in enumerate(v):
                if isinstance(item, str):
                    hits.extend(lint_text(item, field_name=f"{k}[{i}]").hits)
    return LintResult(ok=not hits, hits=tuple(hits))


# ---------------------------------------------------------------------------------------
# The reject log — a committed governance artifact
# ---------------------------------------------------------------------------------------

@dataclass
class RejectLog:
    """Append-only record of what the filter refused.

    PUBLISHED DELIBERATELY. A rejection log is stronger evidence of a working filter than a claim that
    no rejections occurred, and it lets a reviewer disagree with a specific decision.
    """

    path: Path = field(default_factory=lambda: paths.governance / "dual_use_reject_log.json")
    entries: list[dict[str, Any]] = field(default_factory=list)

    def load(self) -> "RejectLog":
        if self.path.exists():
            try:
                self.entries = json.loads(self.path.read_text(encoding="utf-8")).get("entries", [])
            except (json.JSONDecodeError, OSError):
                self.entries = []
        return self

    def record(
        self,
        *,
        source: str,
        proposal_id: str,
        result: LintResult,
        stamped_at: str,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        self.entries.append(
            {
                "stamped_at": stamped_at,
                "source": source,
                "proposal_id": proposal_id,
                "outcome": "REJECTED" if result.rejected else "PASSED",
                "hits": [h.as_dict() for h in result.hits],
                "context": dict(context or {}),
            }
        )

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rejected = [e for e in self.entries if e["outcome"] == "REJECTED"]
        self.path.write_text(
            json.dumps(
                {
                    "n_entries": len(self.entries),
                    "n_rejected": len(rejected),
                    "n_passed": len(self.entries) - len(rejected),
                    "rules": [
                        {
                            "id": r.id,
                            "rationale": r.rationale,
                            "compliant_alternative": r.compliant_alternative,
                        }
                        for r in RULES
                    ],
                    "limits": (
                        "PATTERN-BASED. It will miss paraphrase. It is a FLOOR UNDER human review, "
                        "not a substitute for it. Deliberately crude, because a crude filter that "
                        "fails the build is more trustworthy than a clever one that fails silently."
                    ),
                    "why_published": (
                        "A filter whose output you cannot see is an assertion. A log showing what was "
                        "proposed and refused demonstrates the boundary was enforced during the build, "
                        "and lets a reviewer disagree with a specific decision rather than with our "
                        "self-description."
                    ),
                    "entries": self.entries,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return self.path

    def summary(self) -> dict[str, Any]:
        rejected = [e for e in self.entries if e["outcome"] == "REJECTED"]
        per_rule: dict[str, int] = {}
        for e in rejected:
            for h in e["hits"]:
                per_rule[h["rule_id"]] = per_rule.get(h["rule_id"], 0) + 1
        return {
            "n_entries": len(self.entries),
            "n_rejected": len(rejected),
            "rejections_per_rule": dict(sorted(per_rule.items())),
            "n_rules": len(RULES),
        }


def rule_count() -> int:
    return len(RULES)


def utc_stamp(now: datetime | None = None) -> str:
    """A UTC timestamp. Passed in by the caller in deterministic contexts, so a run that must be
    byte-reproducible can supply a fixed one rather than reading the clock."""
    return (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
