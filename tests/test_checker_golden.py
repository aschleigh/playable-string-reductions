"""Golden passages: every FAIL passage breaks exactly one check, with exactly
the expected attribution; every CLEAN passage passes. Run through both the
batch checker and the incremental checker (in id order and reversed)."""
import pytest

from arrangement.checker import IncrementalChecker, UNASSIGNED, check
from golden.passages import CLEAN, FAIL
from checker_helpers import build, ensemble


def _incremental(notes, ens, assign, order):
    ck = IncrementalChecker(notes, ens)
    for i in order:
        if assign[i] != UNASSIGNED:
            ck.commit(i, int(assign[i]))
    return ck.violations()


def _all_ways(p):
    notes, assign = build(p.notes)
    ens = ensemble(p.ensemble)
    n = len(assign)
    return [check(notes, ens, assign),
            _incremental(notes, ens, assign, range(n)),
            _incremental(notes, ens, assign, reversed(range(n)))]


@pytest.mark.parametrize("p", CLEAN, ids=lambda p: p.name)
def test_clean_passes(p):
    for vs in _all_ways(p):
        assert vs == []


@pytest.mark.parametrize("p", FAIL, ids=lambda p: p.name)
def test_fail_exactly_one_check(p):
    for vs in _all_ways(p):
        got = sorted((v.check, v.part_id, v.note_ids) for v in vs)
        assert got == sorted(p.expected)
        assert len({v.check for v in vs}) == 1


def test_fail_set_covers_every_check():
    assert {e[0] for p in FAIL for e in p.expected} == {
        "simultaneity", "range", "chord_size", "hand_span", "transition"}


def test_measured_and_limit_are_reported():
    by_name = {p.name: p for p in FAIL}
    notes, assign = build(by_name["transition_violin_legato_leap"].notes)
    (v,) = check(notes, ensemble("test"), assign)
    assert (v.measured, v.limit) == (45.0, 24.0)
    notes, assign = build(by_name["hand_span_piano_wide_chord"].notes)
    (v,) = check(notes, ensemble("test"), assign)
    assert (v.measured, v.limit) == (14.0, 12.0)
    notes, assign = build(by_name["simultaneity_flute_overlap"].notes)
    (v,) = check(notes, ensemble("test"), assign)
    assert (v.measured, v.limit) == (1.0, 0.0)
