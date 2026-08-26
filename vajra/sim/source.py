"""The MessageSource seam — the only component a real deployment replaces.

THE WHOLE FEASIBILITY STORY IN ONE INTERFACE: GATE consumes a `MessageSource`. The simulator is
one implementation (`TwinSource`); a tap on a real stream is another (`TapSource`). That makes the
simulator's OUTPUT CONTRACT the production INPUT CONTRACT, and it means an institution swaps the
source, not the scorer.

WHAT WE DO NOT CLAIM: TapSource has never been pointed at a real feed. It is an interface with a
stub implementation and no feed to test against. The claim is that THE SEAM EXISTS and is the only
thing that would have to change — not that we have swapped it. `TapSource.read()` raises rather
than returning synthetic data, because a stub that silently returns simulated events would let a
demo appear to be reading a real stream.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

from sim.schema import CanonicalEvent, canonical_field_order


class MessageSource(ABC):
    """A source of CanonicalEvent records, in non-decreasing timestamp order."""

    #: Human-readable provenance, rendered in the UI footer so a judge always knows what they
    #: are looking at. A screen that cannot say where its events came from is not auditable.
    name: str = "abstract"
    is_live: bool = False

    @abstractmethod
    def read(self) -> Iterator[CanonicalEvent]:
        ...

    @abstractmethod
    def describe(self) -> dict[str, object]:
        ...

    def read_batched(self, batch_size: int = 4096) -> Iterator[list[CanonicalEvent]]:
        batch: list[CanonicalEvent] = []
        for ev in self.read():
            batch.append(ev)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch


@dataclass
class TwinSource(MessageSource):
    """The digital twin: events produced by vajra-sim.

    Either from an in-memory list (the loop's inline path) or from Parquet on disk (the replay
    and training paths). Both are the same contract, which is the point.
    """

    events: Sequence[CanonicalEvent] | None = None
    parquet_path: Path | None = None
    name: str = "TwinSource (vajra-sim)"
    is_live: bool = False

    def read(self) -> Iterator[CanonicalEvent]:
        if self.events is not None:
            yield from self.events
            return
        if self.parquet_path is None:
            raise ValueError("TwinSource needs either `events` or `parquet_path`")
        yield from _read_events_parquet(self.parquet_path)

    def describe(self) -> dict[str, object]:
        return {
            "source": self.name,
            "is_live": False,
            "mode": "in-memory" if self.events is not None else "parquet",
            "path": str(self.parquet_path) if self.parquet_path else None,
            "n_events": len(self.events) if self.events is not None else None,
            "provenance": "SIMULATED. Every identifier is synthetic; no real PII, ever.",
        }


@dataclass
class TapSource(MessageSource):
    """A tap on a real message stream. STUB ONLY — never run against a real feed.

    `read()` raises. That is deliberate: the honest failure mode of this class is a loud error
    saying "there is no feed", not a quiet fallback to simulated data that would let a
    demonstration appear to be reading production traffic.
    """

    endpoint: str = ""
    name: str = "TapSource (STUB — no real feed)"
    is_live: bool = True

    def read(self) -> Iterator[CanonicalEvent]:
        raise NotImplementedError(
            "TapSource is a STUB. It declares the seam a real deployment would implement and has "
            "never been pointed at a real feed. It raises rather than falling back to simulated "
            "events, because a silent fallback would let a demo appear to read production "
            "traffic. To implement: map your message fields onto sim/schema.py's semantic names "
            "using sim/field_map.yaml, and yield CanonicalEvent records in timestamp order. "
            "The visibility ablation tells you up front which of our ~380 registry features you "
            "cannot construct from your view, and what recall that costs."
        )

    def describe(self) -> dict[str, object]:
        return {
            "source": self.name,
            "is_live": True,
            "implemented": False,
            "endpoint": self.endpoint,
            "provenance": (
                "NOT IMPLEMENTED. The seam exists; the feed does not. We have not swapped this "
                "against a real stream and do not claim to have."
            ),
            "what_a_deployment_changes": [
                "implement read() over your own message feed",
                "map your fields via sim/field_map.yaml (semantic names, never exact numbering)",
                "declare your institution's view in gate/views.yaml",
                "read the visibility ablation for the recall consequence of your view",
            ],
        }


def _read_events_parquet(path: Path) -> Iterator[CanonicalEvent]:
    """Read events back from Parquet into CanonicalEvent objects.

    Column order is asserted against the schema: a Parquet file written by an older schema would
    otherwise be silently mis-assigned field by field, which is a data-corruption bug that no
    test downstream could attribute.
    """
    import pyarrow.parquet as pq

    order = canonical_field_order()
    pf = pq.ParquetFile(path)
    got = tuple(pf.schema_arrow.names)
    if got != order:
        missing = [c for c in order if c not in got]
        extra = [c for c in got if c not in order]
        raise ValueError(
            f"{path} column set does not match sim/schema.py.\n"
            f"  missing from file: {missing}\n"
            f"  unexpected in file: {extra}\n"
            f"Regenerate with `make sim`; reading it anyway would mis-assign fields silently."
        )
    # Iterate in RECORD BATCHES rather than materialising all 156 columns as Python lists at once.
    # The old `to_pylist()` over the whole table held 156 x N Python scalars simultaneously, on top of
    # the CanonicalEvent objects the consumer builds — a ~2x memory spike that is harmless at smoke but
    # is tens of GB at the full preset. Batching bounds the pylist footprint to `batch_size` rows while
    # yielding exactly the same events in the same order.
    for batch in pf.iter_batches(batch_size=16_384, columns=list(order)):
        cols = {name: batch.column(name).to_pylist() for name in order}
        for i in range(batch.num_rows):
            yield CanonicalEvent(**{name: cols[name][i] for name in order})


def source_for(spec: str) -> MessageSource:
    """Resolve a source spec string. `twin:<path>` or `tap:<endpoint>`."""
    if spec.startswith("twin:"):
        return TwinSource(parquet_path=Path(spec[5:]))
    if spec.startswith("tap:"):
        return TapSource(endpoint=spec[4:])
    raise ValueError(f"unknown source spec {spec!r}; expected 'twin:<path>' or 'tap:<endpoint>'")


def read_columns(path: Path) -> dict[str, "object"]:
    """Read a Parquet event stream DIRECTLY into numpy columns.

    WHY THIS EXISTS ALONGSIDE `TwinSource.read()`: the streaming interface yields one CanonicalEvent
    at a time, which is the right shape for the inline scoring path and for the loop. It is the WRONG
    shape for batch training: at the `full` preset that is tens of millions of dataclass instances,
    several GB of object graph, and ~150 attribute reads per event to get them back into columns.

    The column set and its ORDER are asserted against sim/schema.py, exactly as in `read()`, so a
    Parquet file written by an older schema raises instead of being silently mis-assigned field by
    field.
    """
    import numpy as np
    import pyarrow.parquet as pq

    order = canonical_field_order()
    table = pq.read_table(path)
    got = tuple(table.schema.names)
    if got != order:
        missing = [c for c in order if c not in got]
        extra = [c for c in got if c not in order]
        raise ValueError(
            f"{path} column set does not match sim/schema.py.\n"
            f"  missing from file: {missing}\n"
            f"  unexpected in file: {extra}\n"
            f"Regenerate with `make sim`; reading it anyway would mis-assign fields silently."
        )
    out: dict[str, object] = {}
    for name in order:
        col = table.column(name)
        t = col.type
        if pa_types_is_string(t):
            out[name] = np.asarray(col.to_pylist(), dtype=object).astype(str)
        elif pa_types_is_bool(t):
            out[name] = np.asarray(col.to_pylist(), dtype=bool)
        elif pa_types_is_integer(t):
            out[name] = np.asarray(col.to_numpy(zero_copy_only=False), dtype=np.int64)
        else:
            out[name] = np.asarray(col.to_numpy(zero_copy_only=False), dtype=np.float64)
    return out


def pa_types_is_string(t) -> bool:  # noqa: ANN001
    import pyarrow as pa

    return bool(pa.types.is_string(t) or pa.types.is_large_string(t))


def pa_types_is_bool(t) -> bool:  # noqa: ANN001
    import pyarrow as pa

    return bool(pa.types.is_boolean(t))


def pa_types_is_integer(t) -> bool:  # noqa: ANN001
    import pyarrow as pa

    return bool(pa.types.is_integer(t))
