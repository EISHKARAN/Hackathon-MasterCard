"""Uniform stage logging and wall-clock accounting for every `make` target.

Two things this buys that print() does not:

*   `reports/runtime.md` is generated from the recorded stage timings, so the
    per-stage runtime budget in the design becomes a MEASURED table rather than an
    unmeasured internal estimate.
*   Every stage prints a machine-readable `VAJRA-STAGE` line, which is what CI greps
    to fail the build when a target that should be green exits non-zero, and what the
    UI's provenance footer reads to say which run produced a number.
"""

from __future__ import annotations

import contextlib
import json
import os
import platform
import sys
import time
from dataclasses import dataclass, asdict
from typing import Iterator

from core.paths import paths


@dataclass
class StageRecord:
    stage: str
    seconds: float
    ok: bool
    detail: str = ""


_RECORDS: list[StageRecord] = []


def hardware_note() -> str:
    """The hardware string that must accompany every latency and runtime number.

    We refuse to publish a p99 or a wall-clock without it: a laptop figure with no
    hardware named is not a measurement, it is a decoration.
    """
    return (
        f"{platform.system()} {platform.release()} / {platform.machine()} / "
        f"python {platform.python_version()} / cpus={os.cpu_count()}"
    )


def emit(kind: str, **fields: object) -> None:
    """Print one machine-readable line. Never buffered, so CI sees it on a crash."""
    payload = {"kind": kind, **fields}
    sys.stdout.write("VAJRA-STAGE " + json.dumps(payload, default=str) + "\n")
    sys.stdout.flush()


@contextlib.contextmanager
def stage(name: str, detail: str = "") -> Iterator[dict[str, object]]:
    """Time a stage, record it, and re-raise on failure after logging.

    The context value is a mutable dict the body can put summary fields into; they are
    printed with the completion line so a `make` log is self-describing.
    """
    t0 = time.perf_counter()
    emit("stage_begin", stage=name, detail=detail, hardware=hardware_note())
    summary: dict[str, object] = {}
    try:
        yield summary
    except BaseException as exc:  # noqa: BLE001 - we re-raise after recording
        dt = time.perf_counter() - t0
        _RECORDS.append(StageRecord(name, dt, ok=False, detail=f"{type(exc).__name__}: {exc}"))
        emit("stage_end", stage=name, seconds=round(dt, 3), ok=False, error=str(exc))
        _flush()
        raise
    dt = time.perf_counter() - t0
    _RECORDS.append(StageRecord(name, dt, ok=True, detail=json.dumps(summary, default=str)))
    emit("stage_end", stage=name, seconds=round(dt, 3), ok=True, **summary)
    _flush()


def _flush() -> None:
    paths.ensure_writable()
    out = paths.reports / "runtime.json"
    existing: list[dict[str, object]] = []
    if out.exists():
        try:
            existing = json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    known = {(r["stage"], r["seconds"]) for r in existing if "stage" in r and "seconds" in r}
    for rec in _RECORDS:
        key = (rec.stage, round(rec.seconds, 3))
        if key in known:
            continue
        row = asdict(rec)
        row["seconds"] = round(rec.seconds, 3)
        row["hardware"] = hardware_note()
        existing.append(row)
        known.add(key)
    out.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")


def records() -> list[StageRecord]:
    return list(_RECORDS)
