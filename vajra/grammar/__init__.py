"""VAJRA ARENA — the attack grammar (Pillar 1: Identify).

An attack is not an entry in a list. It is a typed composition of six morpheme slots, and
that single design choice is what converts breadth from an assertion into an arithmetic
fact: a judge runs `make grammar` and gets an integer.
"""

from grammar.composition import Composition, SLOT_ORDER, load_slots, SlotVocabulary
from grammar.typecheck import TypeChecker, TypeVerdict, load_typechecker
from grammar.cell_of import Cell, cell_of, admissible_depths, rail_class_of, locus_of

__all__ = [
    "Composition",
    "SLOT_ORDER",
    "load_slots",
    "SlotVocabulary",
    "TypeChecker",
    "TypeVerdict",
    "load_typechecker",
    "Cell",
    "cell_of",
    "admissible_depths",
    "rail_class_of",
    "locus_of",
]
