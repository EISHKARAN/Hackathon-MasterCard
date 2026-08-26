"""The label-generating PROCESS, with latency, noise, and a modelled investigator.

============================== LABELS ARE NOT A COLUMN =================================
There is no `is_fraud` field on CanonicalEvent and there never will be. Labels live in an
APPEND-ONLY table keyed `(event_id, channel, as_of_ts, label)`, and every training or evaluation
row resolves its label through an `as_of` read.

The reason is a specific leak: the default of scoring a time-forward window against fully matured
labels is a FUTURE-LABEL LEAK that an entity-id linter cannot see, and it is the single most
likely way we would accidentally publish an inflated recall. `LabelTable.resolve()` refuses to
return a label whose `as_of_ts` exceeds the caller's window end, and the leakage suite asserts it.
========================================================================================

THREE CHANNELS ON THREE CLOCKS:
    analyst disposition   hours     — fast, and NOISY, and POISONABLE
    issuer fraud tag      days
    chargeback / network  45-120+ d  [VERIFY current semantics and deadlines]

ARBITRATION PRECEDENCE, applied only among labels already VISIBLE at the as-of instant:
    chargeback/network report  >  issuer fraud tag  >  analyst disposition
Channel DISAGREEMENT is exported as a feature-free audit field, because disagreement is the
observable that ATK-D3 attacks.

PLUS THE FOUR THINGS THAT MAKE THIS A PROCESS RATHER THAN A DELAY:
    * unreported loss           — a share of true fraud never produces any label at all
    * false complaints          — benign transactions that acquire a fraud label
    * friendly-fraud contamination — first-party misuse coded as fraud
    * the never-labelled synthetic-identity cohort, booked as credit loss

AND THE MODELLED INVESTIGATOR: the analyst has a base wrong-disposition rate that DEGRADES AS
QUEUE PRESSURE RISES. That single mechanism converts ATK-Z3 (review-queue exhaustion) from a
bullet in a taxonomy into a testable attack with a measurable consequence. The rate and its
pressure response are POLICY PARAMETERS WE CHOSE, not estimates of any real ops floor, and they
get the same sensitivity sweep as the attacker economics.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Iterable, Literal

import numpy as np

from core.config import Config, load_config

Channel = Literal["analyst", "issuer_tag", "chargeback"]

#: Arbitration precedence. Higher wins. Published, not implicit.
CHANNEL_PRECEDENCE: dict[str, int] = {"analyst": 1, "issuer_tag": 2, "chargeback": 3}

CHANNELS: tuple[str, ...] = ("analyst", "issuer_tag", "chargeback")


@dataclass(frozen=True, slots=True)
class LabelRecord:
    event_id: str
    channel: str
    as_of_ts: float
    label: int              # 1 = fraud, 0 = legitimate
    #: True when this record was produced by a poisoning attack on the channel. Used ONLY to
    #: flag compromised metrics in the report; never a feature, never used to correct the label.
    poisoned: bool = False


class FutureLabelLeak(AssertionError):
    """Raised when a caller asks for a label that had not arrived yet.

    This is deliberately an AssertionError subclass rather than a soft return: a silent None
    here would look like "no label" and be treated as a negative, which is exactly the inflated
    recall we are guarding against.
    """


class LabelTable:
    """Append-only label store with point-in-time reads."""

    def __init__(self) -> None:
        self._by_event: dict[str, list[LabelRecord]] = {}
        self._count = 0

    # ---- writing ----------------------------------------------------------------------
    def append(self, rec: LabelRecord) -> None:
        rows = self._by_event.setdefault(rec.event_id, [])
        # Keep sorted by as_of_ts so point-in-time reads are a bisect rather than a scan.
        ts_list = [r.as_of_ts for r in rows]
        idx = bisect.bisect_right(ts_list, rec.as_of_ts)
        rows.insert(idx, rec)
        self._count += 1

    def extend(self, recs: Iterable[LabelRecord]) -> None:
        for r in recs:
            self.append(r)

    # ---- reading ----------------------------------------------------------------------
    def visible(self, event_id: str, as_of_ts: float) -> list[LabelRecord]:
        """Every label record for an event that had ARRIVED by `as_of_ts`."""
        rows = self._by_event.get(event_id) or []
        ts_list = [r.as_of_ts for r in rows]
        cut = bisect.bisect_right(ts_list, float(as_of_ts))
        return rows[:cut]

    def resolve(
        self, event_id: str, as_of_ts: float, *, strict: bool = True
    ) -> tuple[int | None, str, bool]:
        """Point-in-time label resolution.

        Returns `(label, winning_channel, channels_disagree)`. `label is None` means NO LABEL HAD
        ARRIVED YET — which is genuinely different from a label of 0, and treating the two as the
        same is the positive-unlabelled structure that nnPU / Elkan-Noto exists to correct.
        """
        rows = self.visible(event_id, as_of_ts)
        if strict:
            all_rows = self._by_event.get(event_id) or []
            future = [r for r in all_rows if r.as_of_ts > float(as_of_ts)]
            # Not an error -- future labels existing is normal. The error case is a CALLER that
            # reads them, which `resolve` structurally cannot do.
            del future
        if not rows:
            return None, "", False
        best = max(rows, key=lambda r: (CHANNEL_PRECEDENCE[r.channel], r.as_of_ts))
        labels = {r.label for r in rows}
        return int(best.label), best.channel, bool(len(labels) > 1)

    def maturity(self, event_ids: Iterable[str], as_of_ts: float) -> dict[str, float]:
        """Share of events with a visible label per channel. Reported with EVERY window.

        Recall against 30% matured labels and recall against 100% are not the same metric, and a
        report that omits maturity is comparing two different quantities.
        """
        ids = list(event_ids)
        if not ids:
            return {c: 0.0 for c in CHANNELS} | {"any": 0.0}
        per: dict[str, int] = {c: 0 for c in CHANNELS}
        any_n = 0
        for eid in ids:
            rows = self.visible(eid, as_of_ts)
            if rows:
                any_n += 1
            seen = {r.channel for r in rows}
            for c in seen:
                per[c] += 1
        out = {c: per[c] / len(ids) for c in CHANNELS}
        out["any"] = any_n / len(ids)
        return out

    def positives_visible(self, event_ids: Iterable[str], as_of_ts: float) -> int:
        n = 0
        for eid in event_ids:
            lab, _, _ = self.resolve(eid, as_of_ts)
            if lab == 1:
                n += 1
        return n

    def disagreement_rate(self, event_ids: Iterable[str], as_of_ts: float) -> float:
        """Channel disagreement — the ATK-D3 observable, exported as an AUDIT field."""
        ids = list(event_ids)
        if not ids:
            return -1.0
        dis = 0
        seen = 0
        for eid in ids:
            rows = self.visible(eid, as_of_ts)
            if len(rows) < 2:
                continue
            seen += 1
            if len({r.label for r in rows}) > 1:
                dis += 1
        return (dis / seen) if seen else -1.0

    def all_records(self) -> list[LabelRecord]:
        out: list[LabelRecord] = []
        for rows in self._by_event.values():
            out.extend(rows)
        return out

    def __len__(self) -> int:
        return self._count

    def stats(self) -> dict[str, object]:
        recs = self.all_records()
        per_channel: dict[str, int] = {c: 0 for c in CHANNELS}
        pos_per_channel: dict[str, int] = {c: 0 for c in CHANNELS}
        poisoned = 0
        for r in recs:
            per_channel[r.channel] = per_channel.get(r.channel, 0) + 1
            if r.label == 1:
                pos_per_channel[r.channel] = pos_per_channel.get(r.channel, 0) + 1
            if r.poisoned:
                poisoned += 1
        return {
            "n_records": len(recs),
            "n_events_with_any_label": len(self._by_event),
            "records_per_channel": per_channel,
            "positives_per_channel": pos_per_channel,
            "poisoned_records": poisoned,
            "precedence": dict(CHANNEL_PRECEDENCE),
        }


# =======================================================================================
# The modelled investigator
# =======================================================================================

@dataclass
class Analyst:
    """An investigator whose accuracy degrades as the queue backs up.

    THE PARAMETERS ARE POLICY CHOICES, NOT ESTIMATES. We do not know any real ops floor's
    wrong-disposition rate, and we say so wherever the number appears. What the mechanism buys is
    that review-queue exhaustion becomes a MEASURABLE attack on the label channel rather than a
    rhetorical one, and the suite's result is a sensitivity analysis over the curve we chose.
    """

    base_wrong_rate: float
    pressure_knee: float
    pressure_slope: float
    max_wrong_rate: float
    latency_median_hours: float
    latency_sigma: float
    daily_capacity: int

    #: Per-day queue depth, so pressure is a real time series the report can plot.
    queue_depth: dict[int, int] = field(default_factory=dict)

    @classmethod
    def from_config(cls, cfg: Config | None = None) -> "Analyst":
        cfg = cfg or load_config()
        a = cfg.analyst
        return cls(
            base_wrong_rate=float(a["base_wrong_disposition_rate"]),
            pressure_knee=float(a["pressure_knee"]),
            pressure_slope=float(a["pressure_slope"]),
            max_wrong_rate=float(a["max_wrong_disposition_rate"]),
            latency_median_hours=float(a["disposition_latency_hours_median"]),
            latency_sigma=float(a["disposition_latency_hours_sigma"]),
            daily_capacity=int(cfg.alert_budget_per_day),
        )

    def enqueue(self, day: int, n: int = 1) -> None:
        self.queue_depth[day] = self.queue_depth.get(day, 0) + int(n)

    def pressure(self, day: int) -> float:
        """queue_depth / daily_capacity. 1.0 means exactly staffed."""
        if self.daily_capacity <= 0:
            return 0.0
        return self.queue_depth.get(day, 0) / float(self.daily_capacity)

    def wrong_rate(self, day: int) -> float:
        """Wrong-disposition rate at this day's queue pressure. Linear above the knee, saturating."""
        p = self.pressure(day)
        if p <= self.pressure_knee:
            return float(self.base_wrong_rate)
        excess = p - self.pressure_knee
        return float(min(self.max_wrong_rate, self.base_wrong_rate + self.pressure_slope * excess))

    def disposition_delay_hours(self, rng: np.random.Generator) -> float:
        mu = float(np.log(max(1e-6, self.latency_median_hours)))
        return float(np.exp(rng.normal(mu, self.latency_sigma)))

    def dispose(self, truth: int, day: int, rng: np.random.Generator) -> tuple[int, float]:
        """Return `(disposition, wrong_rate_at_this_pressure)`.

        The disposition can be WRONG in either direction, and the rate rises with pressure. A
        one-sided error model would make queue flooding harmless in the direction that matters.
        """
        w = self.wrong_rate(day)
        flipped = bool(rng.random() < w)
        return (1 - truth) if flipped else truth, w

    def pressure_series(self) -> dict[int, dict[str, float]]:
        return {
            d: {
                "queue_depth": float(n),
                "pressure": self.pressure(d),
                "wrong_rate": self.wrong_rate(d),
            }
            for d, n in sorted(self.queue_depth.items())
        }


# =======================================================================================
# The label engine
# =======================================================================================

@dataclass
class LabelEngine:
    cfg: Config
    analyst: Analyst
    table: LabelTable = field(default_factory=LabelTable)
    #: Diagnostics the sim report prints, so a suppressed channel is visible not silent.
    counters: dict[str, int] = field(default_factory=dict)

    @classmethod
    def build(cls, cfg: Config | None = None) -> "LabelEngine":
        cfg = cfg or load_config()
        return cls(cfg=cfg, analyst=Analyst.from_config(cfg))

    def _bump(self, key: str, n: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + n

    def observe(
        self,
        *,
        event_id: str,
        event_ts: float,
        day_index: int,
        oracle_is_attack: bool,
        label_morpheme: str,
        alerted: bool,
        dispute_filed_ts: float,
        poisons_channel: bool,
        rng: np.random.Generator,
    ) -> list[LabelRecord]:
        """Generate the label records this event will EVER produce, at their own latencies.

        `label_morpheme` is the composition's LABEL slot for attack events and "" for benign ones.
        It decides which channels can fire at all — which is the whole reason LABEL is a grammar
        slot rather than a delay parameter.
        """
        lat = self.cfg.label_latency
        recs: list[LabelRecord] = []

        # ---- the never-labelled cohort ------------------------------------------------
        if label_morpheme == "never-labelled":
            # NO CHANNEL FIRES. The loss books as credit loss and the family is structurally
            # invisible to any model trained on fraud tags. This is also why our labelling is
            # NOT SCAR: absence of a label is class-conditional, not random.
            self._bump("never_labelled")
            return recs

        # ---- unreported loss ----------------------------------------------------------
        if oracle_is_attack and label_morpheme == "victim-blames-self":
            if rng.random() < 0.55:
                self._bump("unreported_loss_victim_blames_self")
                return recs
        if oracle_is_attack and rng.random() < float(lat["unreported_loss_share"]):
            self._bump("unreported_loss")
            return recs

        truth = 1 if oracle_is_attack else 0

        # ---- false complaints on benign traffic ----------------------------------------
        if not oracle_is_attack and rng.random() < float(lat["false_complaint_rate"]):
            truth = 1
            self._bump("false_complaint")

        allowed = _allowed_channels(label_morpheme, oracle_is_attack)

        # ---- channel 1: analyst disposition (hours) — only if an ALERT was raised -------
        if "analyst" in allowed and alerted:
            self.analyst.enqueue(day_index)
            disp, w = self.analyst.dispose(truth, day_index, rng)
            delay_h = self.analyst.disposition_delay_hours(rng)
            recs.append(
                LabelRecord(
                    event_id=event_id,
                    channel="analyst",
                    as_of_ts=float(event_ts + delay_h * 3600.0),
                    label=int(disp),
                    poisoned=bool(poisons_channel),
                )
            )
            self._bump("analyst_disposition")
            if disp != truth:
                self._bump("analyst_wrong_disposition")
            if w > self.analyst.base_wrong_rate:
                self._bump("analyst_under_pressure")

        # ---- channel 2: issuer fraud tag (days) ----------------------------------------
        if "issuer_tag" in allowed and truth == 1:
            d = int(rng.integers(int(lat["issuer_tag_days_min"]), int(lat["issuer_tag_days_max"]) + 1))
            recs.append(
                LabelRecord(
                    event_id=event_id,
                    channel="issuer_tag",
                    as_of_ts=float(event_ts + d * 86_400.0),
                    label=1,
                    poisoned=bool(poisons_channel),
                )
            )
            self._bump("issuer_tag")

        # ---- channel 3: chargeback / network report (45-120+ days) -----------------------
        if "chargeback" in allowed:
            fires = truth == 1 or poisons_channel
            if fires:
                if dispute_filed_ts > 0:
                    as_of = float(dispute_filed_ts)
                else:
                    d = int(
                        rng.integers(
                            int(lat["chargeback_days_min"]), int(lat["chargeback_days_max"]) + 1
                        )
                    )
                    as_of = float(event_ts + d * 86_400.0)
                # Friendly-fraud contamination: a first-party dispute arrives CODED AS FRAUD even
                # though the transaction genuinely was the cardholder.
                label = 1
                if truth == 0 and rng.random() < float(lat["friendly_fraud_share"]):
                    self._bump("friendly_fraud_contamination")
                recs.append(
                    LabelRecord(
                        event_id=event_id,
                        channel="chargeback",
                        as_of_ts=as_of,
                        label=int(label),
                        poisoned=bool(poisons_channel),
                    )
                )
                self._bump("chargeback_label")

        self.table.extend(recs)
        return recs

    def report(self) -> dict[str, object]:
        return {
            "table": self.table.stats(),
            "counters": dict(sorted(self.counters.items())),
            "analyst": {
                "base_wrong_rate": self.analyst.base_wrong_rate,
                "max_wrong_rate": self.analyst.max_wrong_rate,
                "daily_capacity": self.analyst.daily_capacity,
                "peak_pressure": max(
                    (self.analyst.pressure(d) for d in self.analyst.queue_depth), default=0.0
                ),
                "peak_wrong_rate": max(
                    (self.analyst.wrong_rate(d) for d in self.analyst.queue_depth), default=0.0
                ),
                "parameter_provenance": (
                    "POLICY PARAMETERS WE CHOSE, not estimates of any real operations floor. "
                    "They receive the same sensitivity sweep as the attacker economics, and the "
                    "AUTOIMMUNE queue-exhaustion result is a sensitivity analysis over this "
                    "curve rather than a prediction about real operations."
                ),
            },
            "scar_note": (
                "Labelling is NOT SCAR. The never-labelled synthetic-identity cohort makes label "
                "absence class-conditional, so nnPU / Elkan-Noto are exercised in their "
                "favourable case (pi known, positivity held by the epsilon-randomised incumbent) "
                "and reported with sensitivity to a misspecified propensity model and pi off by "
                "+-2x. We state the violation rather than assuming it away."
            ),
        }


def _allowed_channels(label_morpheme: str, oracle_is_attack: bool) -> frozenset[str]:
    """Which channels a LABEL morpheme permits. Mirrors grammar/slots/label.yaml."""
    if not oracle_is_attack:
        # Benign traffic can still acquire a label through a false complaint or friendly fraud,
        # and can be dispositioned by an analyst if it was alerted on.
        return frozenset({"analyst", "chargeback"})
    return {
        "victim-complains": frozenset({"analyst", "issuer_tag", "chargeback"}),
        "victim-blames-self": frozenset({"analyst"}),
        "never-labelled": frozenset(),
        "label-poisoned": frozenset({"analyst", "issuer_tag", "chargeback"}),
        "label-delayed": frozenset({"chargeback"}),
    }.get(label_morpheme, frozenset({"analyst", "issuer_tag", "chargeback"}))
