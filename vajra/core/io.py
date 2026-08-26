"""Deterministic Parquet and JSON I/O.

The byte-identical-Parquet guarantee in the design is a property of THIS module, so it
is worth being explicit about how it is obtained:

*   **Fixed column order.** Columns are written in the order the schema declares, never
    in dict-insertion or set-iteration order.
*   **No compression metadata drift.** We write with a fixed compression codec and
    `write_statistics=False`; Parquet column statistics embed min/max per row group,
    which is stable, but writer-version strings and creation metadata are not, so we
    hash the *logical table* rather than the file bytes for the CI assertion.
*   **A logical hash, not a file hash.** `table_hash()` hashes the column names, dtypes
    and values. That is the guarantee that actually matters (the same data), and it is
    robust to a pyarrow upgrade changing a footer string, which a raw file hash is not.
    We say so rather than shipping a file-hash test that goes red on a dependency bump
    and gets deleted.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

_COMPRESSION = "zstd"
_COMPRESSION_LEVEL = 3


def to_table(columns: Mapping[str, Sequence[Any]], order: Sequence[str]) -> pa.Table:
    """Build an Arrow table with an explicit column order.

    Raises rather than silently dropping or reordering: a column present in the data
    but absent from `order` is a schema drift bug, and a silent drop is how a feature
    disappears from training without any test noticing.
    """
    missing = [c for c in order if c not in columns]
    if missing:
        raise KeyError(f"columns declared in order but absent from data: {missing}")
    extra = [c for c in columns if c not in order]
    if extra:
        raise KeyError(
            f"columns present in data but not declared in order: {extra}. "
            "Add them to the schema; an undeclared column is a silent schema drift."
        )
    n = None
    arrays = []
    for name in order:
        col = columns[name]
        if n is None:
            n = len(col)
        elif len(col) != n:
            raise ValueError(
                f"column {name!r} has length {len(col)} but the table has {n} rows"
            )
        arrays.append(pa.array(col))
    return pa.Table.from_arrays(arrays, names=list(order))


def write_parquet(table: pa.Table, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        table,
        path,
        compression=_COMPRESSION,
        compression_level=_COMPRESSION_LEVEL,
        write_statistics=False,
        use_dictionary=False,
        version="2.6",
    )
    return path


def read_parquet(path: Path, columns: Sequence[str] | None = None) -> pa.Table:
    return pq.read_table(path, columns=list(columns) if columns else None)


def table_hash(table: pa.Table) -> str:
    """A stable logical hash of an Arrow table: schema + values, no file metadata."""
    h = hashlib.blake2b(digest_size=16)
    for field in table.schema:
        h.update(field.name.encode("utf-8"))
        h.update(b"\x00")
        h.update(str(field.type).encode("utf-8"))
        h.update(b"\x01")
    for col in table.columns:
        for chunk in col.chunks:
            _update_with_chunk(h, chunk)
            h.update(b"\x02")
    return h.hexdigest()


def _update_with_chunk(h: "hashlib._Hash", chunk: pa.Array) -> None:
    """Fold one Arrow array into a hash, numerically where possible.

    Numeric and boolean chunks hash as contiguous bytes plus an explicit null mask
    (to_numpy() fills nulls, so without the mask a null and a zero would collide).
    Anything else -- strings, nested types -- hashes via its Python repr, which is
    slower but total.
    """
    numeric = (
        pa.types.is_integer(chunk.type)
        or pa.types.is_floating(chunk.type)
        or pa.types.is_boolean(chunk.type)
        or pa.types.is_temporal(chunk.type)
    )
    if numeric:
        buf = np.asarray(chunk.to_numpy(zero_copy_only=False))
        if buf.dtype != object:
            h.update(np.ascontiguousarray(buf).tobytes())
            if chunk.null_count:
                mask = np.asarray(chunk.is_null().to_numpy(zero_copy_only=False), dtype=np.uint8)
                h.update(mask.tobytes())
            return
    values = chunk.to_pylist()
    h.update("\x1f".join("\x00NULL" if v is None else repr(v) for v in values).encode("utf-8"))


def parquet_hash(path: Path) -> str:
    return table_hash(read_parquet(path))


def write_json(obj: Any, path: Path, *, sort_keys: bool = True) -> Path:
    """JSON with sorted keys and a trailing newline, so a diff is a real diff."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=sort_keys, default=_json_default) + "\n",
        encoding="utf-8",
    )
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_default(o: Any) -> Any:
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"not JSON-serialisable: {type(o)!r}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()
