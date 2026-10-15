"""decode v2 (REVIEW R37): unison duplicates in one part are merged at commit time, as in the training
targets; the RL probe undoes a merge exactly."""
from fractions import Fraction as F

import pytest

pytest.importorskip("torch")

import model.augment as A  # noqa: E402
from arrangement.instruments import load_ensemble  # noqa: E402
from model.decode import Committer  # noqa: E402

TPQ = 720720


def _notes():
    # Vn1 and Vn2 in unison (G4) on beat 1, a different note on beat 2
    return [A.INote(F(0), F(1), 67, src=0), A.INote(F(0), F(1), 67, src=1), A.INote(F(1), F(1), 72, src=0)]


@pytest.mark.parametrize("masked", [True, False])
def test_unison_merged_into_one_note(masked):
    ens = load_ensemble("trio")
    inotes = _notes()
    com = Committer(ens, TPQ, masked, F(1))
    for i in range(3):
        assert com.try_commit(i, inotes, 0, 0, A.PLAIN)
    assert inotes[1].merged and not inotes[0].merged and com.n_merged == 1
    out = A.expand(inotes)
    assert sorted(out) == [(0, F(0), F(1), 67), (0, F(1), F(1), 72)]


def test_unison_in_different_parts_is_kept():
    ens = load_ensemble("trio")
    inotes = _notes()
    com = Committer(ens, TPQ, True, F(1))
    assert com.try_commit(0, inotes, 0, 0, A.PLAIN) and com.try_commit(1, inotes, 1, 0, A.PLAIN)
    assert not inotes[1].merged and len(A.expand(inotes[:2])) == 2


def test_merge_off_reproduces_decode_v1():
    ens = load_ensemble("trio")
    inotes = _notes()
    com = Committer(ens, TPQ, True, F(1), merge_unisons=False)
    for i in range(2):
        com.try_commit(i, inotes, 0, 0, A.PLAIN)
    assert len(A.expand(inotes[:2])) == 2


def test_probe_undoes_a_merge():
    import model.grpo as G
    ens = load_ensemble("trio")
    inotes = _notes()
    com = G._committer_cls()(ens, TPQ, True, F(1))
    assert com.try_commit(0, inotes, 0, 0, A.PLAIN)
    before = (dict(com.plain_at), com.n_merged, dict(com.slots))
    assert com.probe(1, inotes, 0, 0, A.PLAIN)            # would merge
    assert com.probe(2, inotes, 0, 0, A.PLAIN)            # would register a new plain note
    assert (dict(com.plain_at), com.n_merged, dict(com.slots)) == before
    assert not inotes[1].merged
