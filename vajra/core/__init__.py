"""VAJRA core: determinism, paths and configuration.

Nothing in this package imports a subsystem. Everything else in the repo imports
from here, so a cycle through `core` is a design error and tests/test_core.py
asserts the import graph stays acyclic at this boundary.
"""

from core.paths import Paths, paths
from core.rng import derive_seed, stream, StreamRegistry
from core.config import Config, load_config

__all__ = [
    "Paths",
    "paths",
    "derive_seed",
    "stream",
    "StreamRegistry",
    "Config",
    "load_config",
]
