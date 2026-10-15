"""Hard-tier playability checker. `check` = full assignment, vectorized;
`IncrementalChecker` = per-commit, for partial arrangements and masking.
Both implement the rules documented in incremental.py and agree exactly."""
from arrangement.checker.batch import check
from arrangement.checker.incremental import IncrementalChecker
from arrangement.checker.report import rates_per_100
from arrangement.checker.types import CHECKS, UNASSIGNED, Delta, NoteArrays, Violation

__all__ = ["check", "IncrementalChecker", "rates_per_100", "CHECKS", "UNASSIGNED",
           "Delta", "NoteArrays", "Violation"]
