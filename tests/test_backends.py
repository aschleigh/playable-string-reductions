"""Step 1: format backends, spec extractor, label stripper, corpus cache."""
import struct
from collections import Counter
from dataclasses import replace
from fractions import Fraction

import numpy as np
import pytest
from music21 import converter

from arrangement.backends import MidiBackend, backend_for, load
from arrangement.corpus import piece_from_json, piece_to_json, select_parts
from arrangement.instruments import load_instruments
from arrangement.parse import DeclaredPart, NoteEvent, ParsedPiece, parse_score
from arrangement.spec import extract_spec, identify_instrument, to_ensemble
from arrangement.strip import UnlabeledNote, strip_labels
from conftest import ROOT

ENSEMBLE = ROOT / "tests" / "fixtures" / "ensemble.musicxml"


# --------------------------------------------------------------- raw MIDI writer

def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append(0x80 | (n & 0x7F))
        n >>= 7
    return bytes(reversed(out))


def write_midi(path, tracks, tpq=480):
    """tracks: list of [(abs_tick, bytes_event)]. Writes a format-1 file."""
    chunks = []
    for evs in tracks:
        data, last = b"", 0
        for tick, ev in sorted(evs, key=lambda x: x[0]):
            data += _vlq(tick - last) + ev
            last = tick
        data += _vlq(0) + b"\xff\x2f\x00"
        chunks.append(b"MTrk" + struct.pack(">I", len(data)) + data)
    path.write_bytes(b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), tpq) + b"".join(chunks))


def note(ch, pitch, on, off, vel=80):
    return [(on, bytes([0x90 | ch, pitch, vel])), (off, bytes([0x80 | ch, pitch, 0]))]


# ------------------------------------------------------------------ dispatch

def test_dispatch_by_suffix(tmp_path):
    assert backend_for("a.mxl").name == "musicxml"
    assert backend_for("a.MID").name == "midi"
    with pytest.raises(NotImplementedError):
        load(tmp_path / "x.krn")
    with pytest.raises(ValueError):
        backend_for("a.pdf")


def test_musicxml_backend_is_declared_ground_truth():
    p = load(ENSEMBLE)
    assert p.source_format == "musicxml"
    assert all(part.declared for part in p.parts)
    assert not any(e.part_inferred for e in p.events)


# ---------------------------------------------------------------------- MIDI

def test_midi_tracks_without_instruments_are_part_inferred(tmp_path):
    f = tmp_path / "bare.mid"
    t1 = note(0, 60, 0, 480) + note(0, 62, 480, 960) + note(1, 48, 0, 960)
    drums = note(9, 38, 0, 120) + note(9, 38, 480, 600)
    write_midi(f, [t1, drums])
    p = MidiBackend().read(f)
    assert p.source_format == "midi"
    assert [part.declared for part in p.parts] == [False, False]
    assert all(e.part_inferred for e in p.events)
    assert sorted((e.onset, e.duration, e.pitch) for e in p.events) == [(0, 1, 60), (0, 2, 48), (1, 1, 62)]
    assert p.excluded == [{"kind": "percussion_channel", "channel": 10, "notes": 2}]


def test_midi_program_change_declares_that_channel_only(tmp_path):
    f = tmp_path / "prog.mid"
    t1 = [(0, bytes([0xC0, 40]))] + note(0, 67, 0, 480) + note(1, 48, 0, 480)
    write_midi(f, [t1])
    p = MidiBackend().read(f)
    by_part = {part.part_id: part.declared for part in p.parts}
    assert {e.pitch: e.part_inferred for e in p.events} == {67: not by_part[0], 48: not by_part[1]}
    assert sorted(by_part.values()) == [False, True]


def test_midi_exact_triplet_timing_and_retrigger(tmp_path):
    f = tmp_path / "trip.mid"
    t1 = note(0, 60, 0, 160) + note(0, 62, 160, 320) + note(0, 64, 320, 480)
    t1 += [(480, bytes([0x90, 70, 80])), (600, bytes([0x90, 70, 80])), (720, bytes([0x80, 70, 0])),
           (960, bytes([0x80, 70, 0]))]   # re-struck before release: FIFO pairing
    write_midi(f, [t1])
    p = MidiBackend().read(f)
    got = [(Fraction(e.onset).limit_denominator(100), Fraction(e.duration).limit_denominator(100), e.pitch)
           for e in p.events]
    assert got == [(0, Fraction(1, 3), 60), (Fraction(1, 3), Fraction(1, 3), 62), (Fraction(2, 3), Fraction(1, 3), 64),
                   (1, Fraction(1, 2), 70), (Fraction(5, 4), Fraction(3, 4), 70)]


def test_midi_export_of_fixture_matches_musicxml(tmp_path):
    """Round trip: music21's MIDI export of the ensemble fixture parses back to
    the same sounding (onset, duration, pitch) multiset as the MusicXML."""
    xml = parse_score(ENSEMBLE, expand_repeats=False)
    f = tmp_path / "ens.mid"
    # music21's MIDI export writes transposing parts at WRITTEN pitch, so
    # convert first; MIDI itself is always sounding pitch.
    converter.parse(str(ENSEMBLE)).toSoundingPitch().write("midi", fp=str(f))
    mid = MidiBackend().read(f)
    key = lambda es: Counter((round(e.onset, 6), round(e.duration, 6), e.pitch) for e in es)
    assert key(mid.events) == key(xml.events)
    assert mid.excluded and mid.excluded[0]["kind"] == "percussion_channel"


# ---------------------------------------------------------------------- spec

@pytest.mark.parametrize("name,expected", [
    ("Violin 1", "violin"), ("Violino II", "violin"), ("Viola", "viola"), ("Violoncello", "cello"),
    ("Vc.", "cello"), ("Cello", "cello"), ("Klang", None), ("Piano", "piano"), ("Organ", None)])
def test_identify_instrument(name, expected):
    part = DeclaredPart(part_id=0, xml_id="P1", name=name, instrument_name="", n_staves=1, transposition=None)
    assert identify_instrument(part, load_instruments()) == expected


def _piece(events, names):
    parts = [DeclaredPart(i, f"P{i}", n, "", 1, None) for i, n in enumerate(names)]
    evs = [NoteEvent(id=k, onset=o, duration=d, pitch=p, part_id=pid, voice_id="1", staff_id=1, measure=1,
                     beat_strength=1.0, is_grace=g, tie_group_id=k, is_tied=False)
           for k, (o, d, p, pid, g) in enumerate(events)]
    return ParsedPiece(source="synthetic", events=evs, parts=parts, total_duration=4.0, repeats_expanded=False)


def test_extract_spec_ranges_and_simultaneity():
    piece = _piece([(0, 2, 62, 0, False), (0, 1, 69, 0, False), (1, 1, 71, 0, False), (1, 0, 80, 0, True),
                    (0, 4, 36, 1, False), (2, 1, 43, 1, False)], ["Violin 1", "Violoncello"])
    spec = extract_spec(piece, load_instruments())
    v, c = spec.parts
    assert (v.instrument, v.n_notes, v.low, v.high, v.max_simultaneity) == ("violin", 4, 62, 80, 2)
    assert (c.instrument, c.low, c.high, c.max_simultaneity) == ("cello", 36, 43, 2)
    assert spec.max_simultaneity == 3
    ens = to_ensemble(spec, load_instruments())
    assert [i.key for i in ens.instruments] == ["violin", "cello"]


def test_to_ensemble_refuses_unknown_instrument():
    spec = extract_spec(_piece([(0, 1, 60, 0, False)], ["Klang"]), load_instruments())
    with pytest.raises(ValueError):
        to_ensemble(spec, load_instruments())


# ---------------------------------------------------------------------- strip

def test_strip_removes_part_identity_and_keeps_target():
    piece = load(ENSEMBLE)
    up, target = strip_labels(piece)
    assert set(UnlabeledNote.__dataclass_fields__) & {"part_id", "voice_id", "staff_id", "tie_group_id"} == set()
    assert len(up) == len(piece.events) == len(target.part_id)
    by_id = {e.id: e for e in piece.events}
    for n, pid, oid in zip(up.notes, target.part_id, target.original_id):
        e = by_id[oid]
        assert (n.onset, n.pitch, n.duration, pid) == (e.onset, e.pitch, e.duration, e.part_id)
    keys = [(n.onset, n.pitch, n.duration) for n in up.notes]
    assert keys == sorted(keys)                       # order carries no part information
    assert [n.id for n in up.notes] == list(range(len(up)))


def test_strip_order_independent_of_part_order():
    events = [(0, 1, 60, 0, False), (0, 1, 60, 1, False), (1, 1, 64, 0, False), (0.5, 1, 55, 1, False)]
    a = _piece(events, ["Violin 1", "Violin 2"])
    swapped = [(o, d, p, 1 - pid, g) for o, d, p, pid, g in reversed(events)]
    b = _piece(swapped, ["Violin 2", "Violin 1"])
    ua, ta = strip_labels(a)
    ub, tb = strip_labels(b)
    strip_key = lambda up: [(n.onset, n.pitch, n.duration) for n in up.notes]
    assert strip_key(ua) == strip_key(ub)
    assert ua.arrays().tpq == ub.arrays().tpq


# ---------------------------------------------------------------------- cache

def test_select_parts_and_json_roundtrip():
    piece = _piece([(0, 1, 60, 0, False), (0, 1, 72, 1, False), (1, 1, 48, 2, False)], ["Violin 1", "Klang", "Viola"])
    kept = select_parts(piece, [0, 2])
    assert [p.name for p in kept.parts] == ["Violin 1", "Viola"]
    assert [(e.id, e.part_id, e.pitch) for e in kept.events] == [(0, 0, 60), (1, 1, 48)]
    back = piece_from_json(piece_to_json(kept))
    assert back.events == kept.events and back.parts == kept.parts


def test_cached_corpus_movement_spec():
    """Needs the corpus cache (python -m arrangement.corpus); skipped otherwise."""
    from arrangement.corpus import CACHE, load_cached, manifest
    rows = [r for r in manifest(CACHE) if r["status"] == "ok"]
    if not rows:
        pytest.skip("corpus cache not built")
    piece = load_cached(sorted(r["key"] for r in rows)[0])
    spec = extract_spec(piece, load_instruments())
    assert [p.instrument for p in spec.parts] == ["violin", "violin", "viola", "cello"]
    assert all(p.n_notes > 0 and p.max_simultaneity >= 1 for p in spec.parts)
    up, target = strip_labels(piece)
    assert len(up) == len(piece.events) and not target.part_inferred.any()
