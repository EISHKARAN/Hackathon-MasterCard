"""The multipartite entity graph — built FIRST, before any event exists.

`graph -> actors -> events -> messages -> rows` is the single most consequential ordering
decision in the simulator, and it is the inverse of what a row-first (CTGAN/SMOTE) submission
does. A row-first generator can match a marginal distribution and still have no notion of an
entity that has a device, a habit and a beneficiary — which means it cannot produce a multi-hop
laundering pattern, a mandate violation, or a chargeback that arrives eleven weeks after an
authorisation.
"""

from sim.graph.entities import (
    Beneficiary,
    Cardholder,
    Device,
    Merchant,
    Terminal,
    Token,
    World,
)
from sim.graph.builder import build_world

__all__ = [
    "Beneficiary",
    "Cardholder",
    "Device",
    "Merchant",
    "Terminal",
    "Token",
    "World",
    "build_world",
]
