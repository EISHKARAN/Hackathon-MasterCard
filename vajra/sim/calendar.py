"""ONE shared exogenous calendar process driving every actor.

A DIURNAL CURVE ALONE IS NOT A CALENDAR, and a practitioner plots daily volume first. A flat
week reads synthetic in five seconds. Worse, it is an internal contradiction we would have
shipped: HARD-BENIGN-12 already assumes festival travel and a small-merchant seasonal ramp,
which a diurnal-only generator cannot produce. So this module exists and every actor's activity
is multiplied through it:

*   day-of-week multipliers,
*   a month-end / payday salary-credit spike,
*   one named festival window with a pre-ramp, peak and post-ramp,
*   per-actor dormancy / reactivation / closure states, so ACCOUNT AGE IS NOT A MONOTONE PROXY
    FOR ACTIVITY.

F5 checks the realised day-of-week curve and the month-end curve against the expectation written
in config/scenario.yaml — an expectation written BEFORE the plot, which is what makes it a test
rather than a decoration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import numpy as np

from core.config import Config, load_config

#: Seconds per day. Named so the arithmetic below reads.
DAY_SECONDS = 86_400.0


@dataclass(frozen=True)
class Calendar:
    start_date: date
    tz_offset_hours: float
    dow_multiplier: tuple[float, ...]
    payday_days: frozenset[int]
    payday_multiplier: float
    festival_name: str
    festival_start: int
    festival_peak: int
    festival_end: int
    festival_peak_multiplier: float
    n_days: int

    # ---- calendar arithmetic ---------------------------------------------------------
    def date_of(self, day_index: int) -> date:
        return self.start_date + timedelta(days=int(day_index))

    def dow(self, day_index: int) -> int:
        """0 = Monday. config/scenario.yaml's start_date is a Monday so the index aligns.

        A previous build's F5 day-of-week check failed on an off-by-one here: the realised peak
        landed on Friday while the config named Saturday as heaviest. The fix is to derive the
        index from the real calendar date rather than from `day_index % 7`, because the start
        date being a Monday is a config fact that can change.
        """
        return int(self.date_of(day_index).weekday())

    def day_of_month(self, day_index: int) -> int:
        return int(self.date_of(day_index).day)

    def ts(self, day_index: int, hour_ist: float) -> float:
        """Sim clock (seconds since epoch, UTC) for an IST wall-clock hour on a day.

        We store UTC epoch seconds and carry the IST hour separately on the event, because a
        feature that wants "hour of day as the cardholder experiences it" must not have to
        re-derive a timezone, and a feature that wants elapsed time must not be given a local
        clock that jumps.
        """
        d = self.date_of(day_index)
        base = datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()
        return float(base + (float(hour_ist) - self.tz_offset_hours) * 3600.0)

    # ---- the multiplier every actor's rate passes through ----------------------------
    def volume_multiplier(self, day_index: int) -> float:
        m = self.dow_multiplier[self.dow(day_index)]
        if self.day_of_month(day_index) in self.payday_days:
            m *= self.payday_multiplier
        m *= self.festival_multiplier(day_index)
        return float(m)

    def festival_multiplier(self, day_index: int) -> float:
        """Triangular ramp: 1.0 -> peak over the pre-ramp, peak -> 1.0 over the post-ramp."""
        d = int(day_index)
        if d < self.festival_start or d > self.festival_end:
            return 1.0
        peak = self.festival_peak_multiplier
        if d <= self.festival_peak:
            span = max(1, self.festival_peak - self.festival_start)
            frac = (d - self.festival_start) / span
        else:
            span = max(1, self.festival_end - self.festival_peak)
            frac = 1.0 - (d - self.festival_peak) / span
        return float(1.0 + (peak - 1.0) * max(0.0, min(1.0, frac)))

    def in_festival_window(self, day_index: int) -> bool:
        return self.festival_start <= int(day_index) <= self.festival_end

    def is_payday(self, day_index: int) -> bool:
        return self.day_of_month(day_index) in self.payday_days

    def describe(self) -> dict[str, object]:
        """The expectation F5 checks against. Written before the plot, printed with it."""
        mults = [self.volume_multiplier(d) for d in range(self.n_days)]
        by_dow: dict[int, list[float]] = {}
        for d in range(self.n_days):
            by_dow.setdefault(self.dow(d), []).append(mults[d])
        return {
            "n_days": self.n_days,
            "start_date": self.start_date.isoformat(),
            "heaviest_dow_by_config": int(np.argmax(self.dow_multiplier)),
            "mean_multiplier_by_dow": {k: float(np.mean(v)) for k, v in sorted(by_dow.items())},
            "festival": {
                "name": self.festival_name,
                "start": self.festival_start,
                "peak": self.festival_peak,
                "end": self.festival_end,
                "peak_multiplier": self.festival_peak_multiplier,
            },
            "payday_days": sorted(self.payday_days),
            "payday_multiplier": self.payday_multiplier,
            "note": (
                "The realised day-of-week peak can differ from heaviest_dow_by_config because "
                "the festival and payday windows overlap specific weekdays. F5 therefore checks "
                "the realised curve against the MULTIPLIER-WEIGHTED expectation computed here, "
                "not against the bare dow_multiplier array."
            ),
        }

    def expected_dow_share(self) -> dict[int, float]:
        """Expected share of volume per weekday, INCLUDING festival and payday overlap.

        This is the F5 target. Comparing a realised curve against the bare `dow_multiplier`
        array is the off-by-one trap: festival and month-end windows land on particular
        weekdays, so the multiplier array is not the expectation.
        """
        totals: dict[int, float] = {}
        grand = 0.0
        for d in range(self.n_days):
            m = self.volume_multiplier(d)
            totals[self.dow(d)] = totals.get(self.dow(d), 0.0) + m
            grand += m
        return {k: (v / grand if grand else 0.0) for k, v in sorted(totals.items())}


@lru_cache(maxsize=8)
def build_calendar(n_days: int, cfg_id: int = 0) -> Calendar:
    """Build the calendar. `cfg_id` exists only to key the cache when config is reloaded."""
    cfg: Config = load_config()
    c = cfg.scenario["calendar"]
    dow = tuple(float(x) for x in c["dow_multiplier"])
    if len(dow) != 7:
        raise ValueError(
            f"config/scenario.yaml calendar.dow_multiplier must have 7 entries (Mon..Sun), "
            f"got {len(dow)}"
        )
    fest = c["festival"]
    start = date.fromisoformat(str(c["start_date"]))
    if start.weekday() != 0:
        raise ValueError(
            f"calendar.start_date must be a Monday so that dow index 0 == Monday; "
            f"{start.isoformat()} is a {start.strftime('%A')}. This is the exact off-by-one "
            f"that made a previous build's F5 day-of-week check fail."
        )
    return Calendar(
        start_date=start,
        tz_offset_hours=float(c["timezone_offset_hours"]),
        dow_multiplier=dow,
        payday_days=frozenset(int(x) for x in c["month_end_payday_days"]),
        payday_multiplier=float(c["month_end_payday_multiplier"]),
        festival_name=str(fest["name"]),
        festival_start=int(fest["start_day_offset"]),
        festival_peak=int(fest["peak_day_offset"]),
        festival_end=int(fest["end_day_offset"]),
        festival_peak_multiplier=float(fest["peak_multiplier"]),
        n_days=int(n_days),
    )


def advance_lifecycle(
    world_states: dict[str, str],
    dormant_since: dict[str, int],
    day: int,
    rng: np.random.Generator,
    cfg: Config | None = None,
) -> None:
    """Advance per-actor dormancy / reactivation / closure in place.

    The point is negative: without this, `account_age_days` is a monotone proxy for activity,
    every velocity baseline is well-populated for every aged account, and the entity-age
    stratification in the metrics table becomes uninformative.
    """
    cfg = cfg or load_config()
    lc = cfg.scenario["actor_lifecycle"]
    p_dorm = float(lc["dormancy_hazard_per_day"])
    p_react = float(lc["reactivation_hazard_per_day"])
    p_close = float(lc["closure_hazard_per_day"])

    ids = list(world_states.keys())
    if not ids:
        return
    draws = rng.random(len(ids))
    for i, cid in enumerate(ids):
        state = world_states[cid]
        u = draws[i]
        if state == "active":
            if u < p_close:
                world_states[cid] = "closed"
            elif u < p_close + p_dorm:
                world_states[cid] = "dormant"
                dormant_since[cid] = day
        elif state == "dormant":
            if u < p_react:
                world_states[cid] = "active"
                dormant_since[cid] = -1
