"""Known-answer tests for the evaluation harness (METRICS.md). Every expected
value below is derived by hand from the construction, not from running the code."""
from __future__ import annotations

import csv
import json
from fractions import Fraction as F

import numpy as np
import pytest

from arrangement.checker import CHECKS
from arrangement.eval import fidelity
from arrangement.eval.harness import METRICS_VERSION, evaluate, run, seed_groups
from arrangement.eval.playability import ensemble_of, near_limit, slacks, violations
from arrangement.eval.record import ArrangementRecord, Score, from_json, load, make_score, save, to_json

QUARTET = [("Vn1", "violin"), ("Vn2", "violin"), ("Va", "viola"), ("Vc", "cello")]
TRIO = [("Vn", "violin"), ("Va", "viola"), ("Vc", "cello")]
BARS4 = tuple((F(4 * k), F(4)) for k in range(4))   # four 4/4 bars


def chorale(n_bars=4):
    """Four-part block chords, one per beat, all in range, every part on every beat."""
    notes = []
    for b in range(n_bars * 4):
        for p, x in enumerate([76, 72, 64, 48]):
            notes.append((p, b, 1, x + (b % 3)))
    return make_score(QUARTET, notes)


def rec(output, source=None, reference=None, system="t", seed=0, bars=BARS4, **kw):
    return ArrangementRecord(system=system, seed=seed, input_id="in", ensemble="e",
                             source=source if source is not None else output, output=output,
                             bars=bars, reference=reference, **kw)


def ev(r):
    return evaluate(r, soft=False)


# ------------------------------------------------------------ the five constructed cases

def test_perfect_copy_of_reference_is_at_ceiling():
    src = chorale()
    m = ev(rec(src, source=src, reference=src))
    for side in ("vs_source", "vs_reference"):
        f = m["fidelity"][side]
        for k in ("note_f1", "note_i_f1", "mel_f1", "mel_top_f1", "i_iou"):
            assert f[k] == pytest.approx(1.0), (side, k)
            assert f[f"{k}__n_segments"] == 4
    assert m["fidelity"]["vs_source"]["harmony"] == pytest.approx(1.0)
    assert all(m["playability"][f"{c}__violations"] == 0 for c in CHECKS)
    t = m["texture"]
    assert t["note_ratio__total"] == 1.0 and t["duration_ratio__total"] == 1.0
    assert t["doubling_rate"] == t["doubling_rate__source"]
    assert t["rhythmic_independence"] == 0.0          # a block chorale is rhythmically locked


def test_empty_arrangement():
    src = chorale()
    out = make_score(TRIO, [])
    m = ev(rec(out, source=src))
    f = m["fidelity"]["vs_source"]
    for k in ("note_f1", "note_i_f1", "mel_f1", "mel_top_f1", "i_iou"):
        assert f[k] == 0.0 and f[f"{k}__n_segments"] == 4   # target non-empty in every bar -> 0, not excluded
    assert f["harmony"] == 0.0 and f["harmony__n_beats"] == 16
    p = m["playability"]
    assert p["n_notes"] == 0 and all(p[f"{c}__per_100"] is None for c in CHECKS)
    t = m["texture"]
    assert t["note_density"] == 0.0 and t["note_ratio__total"] == 0.0
    assert t["rhythmic_independence"] is None and t["polyphony_rate"] is None
    assert t["n_notes__per_part"] == [0, 0, 0]


def test_every_note_in_one_part():
    src = chorale()
    out = make_score(TRIO, [(1, o, d, x) for _, o, d, x in src.notes])   # all to the viola
    m = ev(rec(out, source=src, reference_source_parts=((0,), (2,), (3,))))
    f = m["fidelity"]["vs_source"]
    assert f["note_f1"] == pytest.approx(1.0)              # pitches and onsets all present
    # Note_i: only the source viola's notes match (1 of 4 per beat): P = 1/4, R = 1/4 -> F1 = 1/4
    assert f["note_i_f1"] == pytest.approx(0.25)
    assert f["i_iou"] == pytest.approx(1 / 3)                # {viola} vs {violin, viola, cello}
    t = m["texture"]
    assert t["n_notes__per_part"] == [0, 64, 0]
    assert t["rhythmic_independence"] is None              # fewer than two non-empty parts
    assert t["note_ratio__per_part"] == [0.0, 4.0, 0.0]    # 64 notes vs 16 source Va notes
    assert t["polyphony_rate"] == 1.0
    # Four notes per onset on a 4-string viola is legal, and every pitch (48..78) is inside viola C3..G#6.
    pl = m["playability"]
    assert pl["chord_size__violations"] == 0 and pl["range__violations"] == 0


def test_every_note_in_one_part_range_count():
    # Same construction with pitches chosen so the expected range count is unambiguous:
    # two notes per beat, one of them below viola low (48).
    src = make_score(QUARTET, [(p, b, 1, x) for b in range(16) for p, x in [(0, 76), (3, 40)]])
    out = make_score(TRIO, [(1, o, d, x) for _, o, d, x in src.notes])
    pl = ev(rec(out, source=src))["playability"]
    assert pl["range__violations"] == 16
    assert pl["range__per_100"] == pytest.approx(50.0)


def test_deliberate_range_violations():
    # A clean trio, then k notes pushed out of range: violin 54 (< G3 55) and cello 90 (> D6 86).
    base = [(0, b, 1, 76) for b in range(16)] + [(1, b, 1, 60) for b in range(16)] + [(2, b, 1, 43) for b in range(16)]
    bad = list(base)
    bad[0] = (0, 0, 1, 54)
    bad[5] = (0, 5, 1, 54)
    bad[40] = (2, 8, 1, 90)
    out = make_score(TRIO, bad)
    m = ev(rec(out, source=make_score(TRIO, base)))
    pl = m["playability"]
    assert pl["range__violations"] == 3
    assert pl["range__per_100"] == pytest.approx(100 * 3 / 48)
    assert pl["by_check_part"]["range:0"] == 2 and pl["by_check_part"]["range:2"] == 1
    nl = m["near_limit"]
    assert nl["range__n_opportunities"] == 48
    assert nl["range__hist"]["-1"] == 2 and nl["range__hist"]["-4"] == 1   # 54-55 = -1; 86-90 = -4
    assert nl["range__share_violating"] == pytest.approx(3 / 48)


def test_rhythmically_locked_parts():
    locked = make_score(TRIO, [(p, b, 1, x) for b in range(16) for p, x in [(0, 76), (1, 60), (2, 43)]])
    assert ev(rec(locked))["texture"]["rhythmic_independence"] == 0.0
    # Violin on every beat, viola on even beats, cello on off-beat eighths only:
    # Vn/Va: J = 8/16 -> 0.5; Vn/Vc: J = 0 -> 1; Va/Vc: J = 0 -> 1; mean = 2.5/3
    free = make_score(TRIO, [(0, b, 1, 76) for b in range(16)] + [(1, b, 2, 60) for b in range(0, 16, 2)]
                      + [(2, F(b) + F(1, 2), F(1, 2), 43) for b in range(16)])
    assert ev(rec(free))["texture"]["rhythmic_independence"] == pytest.approx(2.5 / 3)


# ------------------------------------------------------------ published metric definitions

def test_onset_tolerance_is_strictly_less_than_a_sixteenth():
    tgt = make_score(TRIO, [(0, 0, 1, 76)])
    near = make_score(TRIO, [(0, F(1, 8), 1, 76)])
    edge = make_score(TRIO, [(0, F(1, 4), 1, 76)])
    bars = ((F(0), F(4)),)
    assert fidelity.reference_metrics(near, tgt, bars)["note_f1"] == 1.0
    assert fidelity.reference_metrics(edge, tgt, bars)["note_f1"] == 0.0


def test_matching_is_one_to_one():
    # Output duplicates the single target note: |M| = 1, P = 1/2, R = 1 -> F1 = 2/3
    tgt = make_score(TRIO, [(0, 0, 1, 76)])
    dup = make_score(TRIO, [(0, 0, 1, 76), (1, 0, 1, 76)])
    assert fidelity.reference_metrics(dup, tgt, ((F(0), F(4)),))["note_f1"] == pytest.approx(2 / 3)


def test_segment_where_both_sides_are_empty_is_excluded():
    tgt = make_score(TRIO, [(0, 0, 1, 76)])
    m = fidelity.reference_metrics(tgt, tgt, ((F(0), F(4)), (F(4), F(4))))   # bar 2 empty on both sides
    assert m["note_f1"] == 1.0 and m["note_f1__n_segments"] == 1


def test_melody_track_is_highest_mean_pitch_track_not_top_voice():
    # Viola holds the highest mean pitch; the violin dips below it. Paper melody = whole viola track.
    out = make_score(TRIO, [(0, 0, 1, 90), (0, 1, 1, 50), (1, 0, 1, 80), (1, 1, 1, 80)])
    assert fidelity.melody_track(list(out.notes)) == [n for n in out.notes if n[0] == 1]
    # Top voice (our addition) = 90 at beat 0, 80 at beat 1
    sky = sorted((n[1], n[3]) for n in fidelity.skyline(list(out.notes)))
    assert sky == [(0, 90), (1, 80)]


def test_skyline_drops_note_under_a_sustained_higher_note():
    s = make_score(TRIO, [(0, 0, 4, 80), (1, 1, 1, 70), (1, 2, 1, 85)])
    assert sorted((n[1], n[3]) for n in fidelity.skyline(list(s.notes))) == [(0, 80), (2, 85)]


def test_i_iou_per_segment():
    tgt = make_score(TRIO, [(0, 0, 1, 76), (1, 0, 1, 60), (2, 0, 1, 43)])
    out = make_score(TRIO, [(0, 0, 1, 76), (2, 0, 1, 43)])
    assert fidelity.reference_metrics(out, tgt, ((F(0), F(4)),))["i_iou"] == pytest.approx(2 / 3)


def test_harmony_is_pitch_class_based_and_octave_invariant():
    src = make_score(TRIO, [(0, 0, 4, 72), (1, 0, 4, 64), (2, 0, 4, 55)])   # C E G
    up = make_score(TRIO, [(0, 0, 4, 84), (1, 0, 4, 76), (2, 0, 4, 67)])    # same, octave up
    assert fidelity.harmony_agreement(up, src, F(0), F(4))["harmony"] == pytest.approx(1.0)
    other = make_score(TRIO, [(0, 0, 4, 73), (1, 0, 4, 66), (2, 0, 4, 58)])  # disjoint pitch classes
    assert fidelity.harmony_agreement(other, src, F(0), F(4))["harmony"] == pytest.approx(0.0)


def test_reference_with_different_instrument_count():
    # Quartet reference, trio output: Note F1 ignores instruments; Note_i matches by instrument type,
    # so both violins of the reference are "violin".
    ref = make_score(QUARTET, [(0, 0, 1, 76), (1, 0, 1, 72), (2, 0, 1, 64), (3, 0, 1, 48)])
    out = make_score(TRIO, [(0, 0, 1, 76), (0, 0, 1, 72), (1, 0, 1, 64), (2, 0, 1, 48)])
    m = fidelity.reference_metrics(out, ref, ((F(0), F(4)),))
    assert m["note_f1"] == 1.0 and m["note_i_f1"] == 1.0 and m["i_iou"] == 1.0


# ------------------------------------------------------------ near-limit agrees with the checker

def _corpus_record():
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "headroom" / "data" / "sources" / "000.json"
    if not p.exists():
        pytest.skip("headroom sources not exported")
    d = json.loads(p.read_text())
    src = make_score(QUARTET, [(int(a), F(b), F(c), int(x)) for a, b, c, x in d["notes"]])
    return src, tuple((F(a), F(b)) for a, b in d["bars"])


@pytest.mark.parametrize("ens", ["trio", "duo", "solo_flute", "piano"])
def test_near_limit_negative_slack_equals_checker_violations(ens):
    from arrangement.assign import naive
    from arrangement.instruments import load_ensemble
    from arrangement.eval.playability import arrays
    src, _ = _corpus_record()
    e = load_ensemble(ens)
    parts = [(n, i.key) for n, i in zip(e.part_names, e.instruments)]
    na, _ = arrays(src)
    a = naive(na, e)
    out = make_score(parts, [(int(p), n[1], n[2], n[3]) for p, n in zip(a, src.notes)])
    ens_ = ensemble_of(out)
    vs = violations(out, ens_)
    sl = slacks(out, ens_)
    for c in ("range", "chord_size", "hand_span", "transition"):
        assert sum(s < 0 for s in sl[c]) == sum(v.check == c for v in vs), c
    if ens == "solo_flute":   # consecutive-pair overlaps <= all overlapping pairs
        assert 0 < sum(s < 0 for s in sl["simultaneity"]) <= sum(v.check == "simultaneity" for v in vs)


def test_floor_quartet_has_no_range_or_chord_slack_below_zero():
    src, bars = _corpus_record()
    nl = near_limit(src, ensemble_of(src))
    assert nl["chord_size__share_violating"] == 0.0 and nl["range__share_violating"] == 0.0


# ------------------------------------------------------------ seeds, records, run files

def test_identical_seeds_have_zero_spread_and_full_pairwise_agreement():
    src = chorale()
    rs = [rec(src, seed=s) for s in range(3)]
    rows = seed_groups(rs, [ev(r) for r in rs])
    assert len(rows) == 1 and rows[0]["n_seeds"] == 3
    assert rows[0]["pairwise_note_f1"] == 1.0 and rows[0]["pairwise_note_i_f1"] == 1.0
    assert rows[0]["spread"]["fidelity.vs_source.note_f1"]["std"] == 0.0


def test_different_seeds_spread():
    src = chorale(1)
    a = make_score(QUARTET, list(src.notes))
    b = make_score(QUARTET, list(src.notes[:8]))          # second seed keeps half the notes
    bars = BARS4[:1]
    rs = [rec(a, source=src, seed=0, bars=bars), rec(b, source=src, seed=1, bars=bars)]
    row = seed_groups(rs, [ev(r) for r in rs])[0]
    assert row["pairwise_note_f1"] == pytest.approx(2 * 0.5 / 1.5)   # P = 1, R = 1/2
    assert row["spread"]["texture.note_ratio__total"]["std"] == pytest.approx(np.std([1.0, 0.5], ddof=1))


def test_record_roundtrip_and_assignment_check(tmp_path):
    src = chorale(1)
    m = {0: 0, 1: -1, 2: 1, 3: 2}   # Vn1 -> violin, Vn2 dropped, Va -> viola, Vc -> cello
    assign = tuple(m[p] for p, *_ in src.notes)
    out = make_score(TRIO, [(m[p], o, d, x) for p, o, d, x in src.notes if m[p] >= 0])
    r = rec(out, source=src, bars=BARS4[:1], assignment=assign)
    r.validate()
    assert from_json(json.loads(json.dumps(to_json(r)))) == r
    bad = rec(out, source=src, bars=BARS4[:1], assignment=tuple(0 for _ in src.notes))
    with pytest.raises(ValueError):
        bad.validate()
    save([r], tmp_path / "r.jsonl")
    assert load(tmp_path / "r.jsonl") == [r]


def test_window_restricts_source_and_bars():
    src = chorale(4)
    out = make_score(QUARTET, [n for n in src.notes if n[1] < 8])
    m = ev(rec(out, source=src, window=(F(0), F(8))))
    assert m["n_segments"] == 2 and m["fidelity"]["vs_source"]["note_f1"] == 1.0
    assert m["texture"]["note_ratio__total"] == 1.0


def test_run_writes_versioned_data_files(tmp_path):
    src = chorale(1)
    save([rec(src, seed=0, bars=BARS4[:1]), rec(src, seed=1, bars=BARS4[:1])], tmp_path / "r.jsonl")
    info = run([str(tmp_path / "r.jsonl")], tmp_path / "out", soft=False)
    assert info["n_records"] == 2 and info["n_seed_groups"] == 1
    rows = [json.loads(l) for l in open(tmp_path / "out" / "metrics.jsonl")]
    assert all(r["metrics_version"] == METRICS_VERSION for r in rows)
    with open(tmp_path / "out" / "metrics.csv") as f:
        c = list(csv.DictReader(f))
    assert len(c) == 2 and c[0]["metrics_version"] == METRICS_VERSION
    assert "playability.range__per_100" in c[0] and "fidelity.vs_source.note_i_f1" in c[0]
    assert not any(k.startswith("score") or k == "aggregate" for k in c[0])
