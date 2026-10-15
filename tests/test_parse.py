"""Parser tests (arrangement.parse). Reference counts come from
tests/xml_counts.py, which reads the MusicXML directly (no music21), so every
number here can be checked by hand against the XML."""
import glob
import io
import xml.etree.ElementTree as ET
from collections import Counter

import pytest
from music21 import pitch

from arrangement.parse import NoteEvent, load_raw_score, parse_score
from conftest import ROOT
from xml_counts import (expected_event_counts, expected_event_counts_text, grace_count,
                        movement_measure_range, read_xml_text)

ENSEMBLE = ROOT / "tests" / "fixtures" / "ensemble.musicxml"
ABC = ["beethoven_op18-2_ii", "beethoven_op18-4_i", "beethoven_op59-3_iv",
       "beethoven_op131_i", "beethoven_op132_iii"]


def _name(midi):
    return pitch.Pitch(midi=midi).nameWithOctave


def _openscore(glob_pat):
    return glob.glob(str(ROOT / "raw_corpora/StringQuartets/scores" / glob_pat))[0]


# --- hand-written ensemble fixture: transposition, staves, voices, percussion ---

@pytest.fixture(scope="module")
def ensemble():
    return parse_score(ENSEMBLE)


def test_transposition_written_vs_sounding(ensemble):
    written = load_raw_score(ENSEMBLE)
    before = {p.partName: [n.pitch.nameWithOctave for n in p.recurse().notes] for p in written.parts[:2]}
    after = {ensemble.parts[pid].name: [_name(e.pitch) for e in ensemble.events if e.part_id == pid]
             for pid in (0, 1)}
    assert before == {"Clarinet in B♭": ["D5", "E5", "F#5", "G5"], "Horn in F": ["G4", "A4", "B4", "C5"]}
    assert after == {"Clarinet in B♭": ["C5", "D5", "E5", "F5"], "Horn in F": ["C4", "D4", "E4", "F4"]}
    assert [p.transposition for p in ensemble.parts] == ["M-2", "P-5", None]


def test_piano_is_one_part_two_staves(ensemble):
    assert [(p.name, p.n_staves) for p in ensemble.parts] == \
           [("Clarinet in B♭", 1), ("Horn in F", 1), ("Piano", 2)]
    pno = sorted((e.staff_id, e.voice_id, _name(e.pitch), e.onset, e.duration)
                 for e in ensemble.events if e.part_id == 2)
    assert pno == [(1, "1", "C5", 0.0, 2.0), (1, "1", "D5", 2.0, 2.0), (1, "2", "E4", 0.0, 4.0),
                   (2, "1", "C3", 0.0, 4.0), (2, "1", "G3", 0.0, 4.0)]  # chord -> 2 events, same part


def test_percussion_excluded_and_logged(ensemble):
    assert ensemble.excluded == [{"kind": "percussion_part", "xml_id": "Snare Drum",
                                  "name": "Snare Drum", "notes": 4}]
    assert all(p.name != "Snare Drum" for p in ensemble.parts)


def test_beat_strength_from_time_signature(ensemble):
    cl = [e.beat_strength for e in ensemble.events if e.part_id == 0]
    assert cl == [1.0, 0.25, 0.5, 0.25]  # 4/4


def test_event_schema(ensemble):
    e = ensemble.events[0]
    assert isinstance(e, NoteEvent)
    assert set(vars(e)) == {"id", "onset", "duration", "pitch", "part_id", "voice_id", "staff_id",
                            "measure", "beat_strength", "is_grace", "tie_group_id", "is_tied",
                            "part_inferred"}


# --- real corpus: counts against the raw XML ---

@pytest.mark.parametrize("name", ABC)
def test_abc_event_counts_match_xml(name):
    path = ROOT / "corpus" / f"{name}.musicxml"
    pp = parse_score(path, expand_repeats=False)
    got = Counter(pp.parts[e.part_id].name for e in pp.events)
    assert dict(got) == expected_event_counts(path)
    assert len(pp.parts) == 4


def test_op18_2_ii_opening_by_hand():
    """3/4 with a one-beat pickup. From the XML: pickup G4 quarter, then m.1
    C5 dotted-quarter, G4 E4 C4 eighths."""
    pp = parse_score(ROOT / "corpus" / "beethoven_op18-2_ii.musicxml", expand_repeats=False)
    v1 = [(e.measure, _name(e.pitch), e.onset, e.duration, e.beat_strength)
          for e in pp.events if e.part_id == 0][:5]
    assert v1 == [(0, "G4", 0.0, 1.0, 0.5), (1, "C5", 1.0, 1.5, 1.0), (1, "G4", 2.5, 0.5, 0.25),
                  (1, "E4", 3.0, 0.5, 0.5), (1, "C4", 3.5, 0.5, 0.25)]


def test_grace_notes_kept_zero_duration_in_order():
    path = ROOT / "corpus" / "beethoven_op18-2_ii.musicxml"
    text = read_xml_text(path)
    pp = parse_score(path, expand_repeats=False)
    graces = [e for e in pp.events if e.is_grace]
    assert len(graces) == grace_count(text) == 36
    assert all(e.duration == 0.0 for e in graces)
    # notated order of the grace run in Violin 1, m.2
    root = ET.parse(io.StringIO(text)).getroot()
    m2 = root.find("part").findall("measure")[2]
    xml_run = [n.findtext("pitch/step") + n.findtext("pitch/octave")
               for n in m2.iter("note") if n.find("grace") is not None]
    got_run = [_name(e.pitch).replace("#", "").replace("-", "")
               for e in graces if e.part_id == 0 and e.measure == 2]
    assert got_run == xml_run


def test_tie_group_ids_on_every_event_is_tied_flag():
    pp = parse_score(ROOT / "tests" / "fixtures" / "ties.musicxml")
    assert all(isinstance(e.tie_group_id, int) for e in pp.events)
    assert len({e.tie_group_id for e in pp.events}) == len(pp.events)
    tied = [(_name(e.pitch), e.onset, e.duration) for e in pp.events if e.is_tied]
    assert tied == [("C4", 0.0, 3.0), ("E4", 0.0, 3.0), ("G4", 0.0, 3.0), ("C4", 4.0, 3.0),
                    ("D4", 8.0, 3.0), ("F4", 12.0, 5.0)]
    assert sum(not e.is_tied for e in pp.events) == 17 - 6


# --- OpenScore raw source: declared parts, movement slicing, repeats ---

@pytest.fixture(scope="module")
def haydn_raw():
    path = _openscore("Haydn*/*Op.20_No.6/*.mxl")
    return path, load_raw_score(path)


def test_openscore_movement_counts_and_declared_parts(haydn_raw):
    path, raw = haydn_raw
    pp = parse_score(path, expand_repeats=False, movement=4, score=raw)
    text = read_xml_text(path)
    assert [p.name for p in pp.parts] == ["Violin 1", "Violin 2", "Viola", "Violoncello"]
    assert dict(Counter(pp.parts[e.part_id].name for e in pp.events)) == \
           expected_event_counts_text(text, movement_measure_range(text, 4))
    assert max(e.measure for e in pp.events) == 95  # final measure kept (build_corpus drops it)


@pytest.mark.slow
def test_repeats_expanded_by_default_mozart_k387_iv():
    path = _openscore("Mozart*/*K.387*/*.mxl")
    raw = load_raw_score(path)
    notated = parse_score(path, expand_repeats=False, movement=4, score=raw)
    expanded = parse_score(path, movement=4, score=raw)
    assert expanded.repeats_expanded and not notated.repeats_expanded
    # 298 measures of 4/4 notated (incl. the final one); both halves repeated except the final bar
    assert notated.total_duration == 298 * 4 and expanded.total_duration == 2260.0
    # every expanded measure is a notated one, some appear more than once
    n_occ = Counter((e.measure, e.part_id, e.pitch) for e in expanded.events)
    assert set(n_occ) == {(e.measure, e.part_id, e.pitch) for e in notated.events}
    assert [e.onset for e in expanded.events] == sorted(e.onset for e in expanded.events)
