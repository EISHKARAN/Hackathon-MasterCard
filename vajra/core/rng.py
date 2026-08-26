"""Named, independently derived RNG streams.

Determinism is not a nicety here. Two properties depend on it:

1.  **The sealed-family holdout is only enforceable if a held-out family's random
    draws are not a function of how much data was drawn before it.** If every
    subsystem pulled from one global generator, adding a training campaign would
    shift a held-out family's numbers, and "held out" would silently become
    "generated from a state the training data determined".

2.  **Byte-identical Parquet given a fixed seed and config**, asserted by a hash test.

So a stream's seed is derived by a keyed hash of its NAME, never by advancing a
shared counter:

    seed(stream) = int(BLAKE2b(b"VAJRA/v1|" + name + b"|" + str(master_seed))[:8])

Adding a stream or reordering execution cannot perturb another stream. The stream
registry in config/seed.yaml is authoritative and `stream()` raises on an
unregistered name, so a typo produces a hard failure rather than a silently
different-but-deterministic world.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Iterable

import numpy as np
import yaml

from core.paths import paths

_KDF_DOMAIN = b"VAJRA/v1|"

#: Prefixes under which dynamically named streams are permitted. Per-attack-family
#: streams are derived from grammar ids that are not known at config-authoring time.
_DYNAMIC_PREFIXES: tuple[str, ...] = (
    "attack.family.",
    "eval.bootstrap.",
    "loop.tick.",
    "bench.load.",
)


class StreamRegistry:
    """The declared stream names, loaded once from config/seed.yaml."""

    def __init__(self, master_seed: int, names: Iterable[str]) -> None:
        self.master_seed = int(master_seed)
        self.names = frozenset(names)

    def validate(self, name: str) -> None:
        if name in self.names:
            return
        if any(name.startswith(p) for p in _DYNAMIC_PREFIXES):
            return
        raise KeyError(
            f"RNG stream {name!r} is not declared in config/seed.yaml and does not "
            f"use a permitted dynamic prefix {_DYNAMIC_PREFIXES}. Declare it rather "
            f"than deriving an undeclared stream: an undeclared stream is a "
            f"reproducibility hole that no test can see."
        )


@lru_cache(maxsize=1)
def _registry() -> StreamRegistry:
    with (paths.config / "seed.yaml").open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return StreamRegistry(cfg["master_seed"], cfg.get("streams") or [])


def master_seed() -> int:
    return _registry().master_seed


def derive_seed(name: str, master: int | None = None) -> int:
    """Derive the 64-bit seed for a named stream.

    Pure function of (name, master_seed). No global state, no ordering dependence.
    """
    m = _registry().master_seed if master is None else int(master)
    payload = _KDF_DOMAIN + name.encode("utf-8") + b"|" + str(m).encode("ascii")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=False)


def stream(name: str, master: int | None = None) -> np.random.Generator:
    """Return the numpy Generator for a named stream.

    Callers get a FRESH generator each call, positioned at the start of the stream.
    That is deliberate: a function that needs a reproducible draw asks for its stream
    by name and gets the same numbers every time, regardless of what else ran. Callers
    that need to consume a long sequence hold onto the returned generator.
    """
    _registry().validate(name)
    return np.random.Generator(np.random.PCG64(derive_seed(name, master)))


def substream(parent: str, key: str | int, master: int | None = None) -> np.random.Generator:
    """A deterministic child stream of `parent`, keyed by `key`.

    Used for per-entity draws (per cardholder habit vector, per campaign schedule)
    where we want reproducibility per entity rather than per call order. The parent
    name is validated; the composed `parent#key` name is not, because keys are entity
    ids that cannot be declared in advance.
    """
    _registry().validate(parent)
    composed = f"{parent}#{key}"
    return np.random.Generator(np.random.PCG64(derive_seed(composed, master)))


def family_stream(family_id: str, master: int | None = None) -> np.random.Generator:
    """The dedicated stream for one attack family.

    Control #2 of the sealed-family protocol (docs/CONTRACTS.md): separate RNG streams
    per family, so a held-out family's draws cannot correlate with training data
    through shared generator state.
    """
    return stream(f"attack.family.{family_id}", master)


def spawn_int(gen: np.random.Generator, low: int, high: int) -> int:
    """`gen.integers` returning a plain int, for use in ids and dict keys."""
    return int(gen.integers(low, high))
