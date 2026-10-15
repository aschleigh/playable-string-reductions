"""Parser fixes found by the floor validation (Step 4)."""
from arrangement.parse import parse_score

HEAD = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1"><part-list><score-part id="P1"><part-name>Violin 1</part-name></score-part></part-list>
<part id="P1"><measure number="1"><attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time>
<clef><sign>G</sign><line>2</line></clef></attributes>"""
N = lambda step, octv, dur, voice, extra="": (f"<note>{extra}<pitch><step>{step}</step><octave>{octv}</octave></pitch>"
                                              f"<duration>{dur}</duration><voice>{voice}</voice><type>quarter</type></note>")


def test_cue_notes_dropped_and_timing_kept(tmp_path):
    body = (N("G", 4, 2, 1) + N("A", 4, 2, 1) + "<backup><duration>4</duration></backup>"
            + N("C", 3, 1, 2, "<cue/>") + N("E", 3, 1, 2, "<chord/><cue/>")   # a cue chord (cello cue)
            + N("D", 5, 1, 2) + N("E", 5, 2, 2))
    f = tmp_path / "cue.musicxml"
    f.write_text(HEAD + body + "</measure></part></score-partwise>")
    p = parse_score(f, expand_repeats=False)
    assert sorted((e.onset, e.pitch) for e in p.events) == [(0, 67), (1, 74), (2, 69), (2, 76)]


def test_hidden_notations_with_lone_accidental_mark_parse(tmp_path):
    body = N("G", 4, 4, 1).replace(
        "</note>", '<notations print-object="no"><ornaments><accidental-mark>sharp</accidental-mark></ornaments></notations></note>')
    f = tmp_path / "hidden.musicxml"
    f.write_text(HEAD + body + "</measure></part></score-partwise>")
    assert [e.pitch for e in parse_score(f, expand_repeats=False).events] == [67]


def test_octave_shift_keeps_true_pitch(tmp_path):
    """MusicXML pitch data under <octave-shift> is the true pitch; nothing to shift."""
    body = (N("C", 5, 1, 1) + '<direction><direction-type><octave-shift type="down" size="8" number="1"/></direction-type></direction>'
            + N("C", 7, 1, 1) + N("D", 7, 1, 1)
            + '<direction><direction-type><octave-shift type="stop" size="8" number="1"/></direction-type></direction>' + N("C", 5, 1, 1))
    f = tmp_path / "ottava.musicxml"
    f.write_text(HEAD + body + "</measure></part></score-partwise>")
    assert [e.pitch for e in parse_score(f, expand_repeats=False).events] == [72, 96, 98, 72]


def test_artificial_harmonic_touch_note_dropped_lone_diamond_kept(tmp_path):
    dia = "<notehead>diamond</notehead>"
    harm = (N("E", 4, 2, 1).replace("</type>", "</type>")
            + N("A", 4, 2, 1, "<chord/>").replace("<type>quarter</type>", "<type>quarter</type>" + dia))
    lone = N("E", 5, 2, 1).replace("<type>quarter</type>", "<type>quarter</type>" + dia)
    f = tmp_path / "harm.musicxml"
    f.write_text(HEAD + harm + lone + "</measure></part></score-partwise>")
    assert [(e.onset, e.pitch) for e in parse_score(f, expand_repeats=False).events] == [(0, 64), (2, 76)]


def test_shared_unison_across_voices_merged_same_voice_unison_kept(tmp_path):
    body = (N("G", 5, 4, 1) + "<backup><duration>4</duration></backup>"
            + N("G", 4, 1, 2) + N("G", 5, 1, 2, "<chord/>") + N("A", 4, 3, 2))   # G5 shared with voice 1
    f = tmp_path / "uni.musicxml"
    f.write_text(HEAD + body + "</measure></part></score-partwise>")
    p = parse_score(f, expand_repeats=False)
    assert sorted((e.onset, e.pitch, e.duration) for e in p.events) == [(0, 67, 1), (0, 79, 4), (1, 69, 3)]
    assert [e.id for e in p.events] == list(range(3))
    assert {"kind": "shared_unison_merged", "notes": 1} in p.excluded
    body2 = N("A", 4, 4, 1) + N("A", 4, 4, 1, "<chord/>")      # same-voice unison double stop
    f2 = tmp_path / "uni2.musicxml"
    f2.write_text(HEAD + body2 + "</measure></part></score-partwise>")
    assert len(parse_score(f2, expand_repeats=False).events) == 2
