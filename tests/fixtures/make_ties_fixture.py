"""Generates tests/fixtures/ties.musicxml from the hand-specified measures
below. Re-run only if the spec changes; the .musicxml is the test input.

2/4, divisions=2 (quarter = 2). Each note: (step, octave, divs, tie, chord, grace, voice)
tie in {None, 'start', 'stop', 'both'} ('both' = stop+start, i.e. continue).
"""
from pathlib import Path

def n(p, d, tie=None, chord=False, grace=False, voice=1):
    return dict(p=p, d=d, tie=tie, chord=chord, grace=grace, voice=voice)
def r(d, voice=1):
    return dict(p=None, d=d, voice=voice)

P1 = [
    # m1-2 whole chord tied
    [n("C4", 4, "start"), n("E4", 4, "start", chord=True)],
    [n("C4", 2, "stop"), n("E4", 2, "stop", chord=True), r(2)],
    # m3-4 partial chord tie: only C4 tied; E4 re-struck; G4 new
    [n("C4", 4, "start"), n("E4", 4, chord=True)],
    [n("C4", 2, "stop"), n("E4", 2, chord=True), n("G4", 2, chord=True), r(2)],
    # m5-6 single note tied into a chord
    [n("D4", 4, "start")],
    [n("D4", 2, "stop"), n("A4", 2, chord=True), r(2)],
    # m7-9 three-link chain starting inside a chord, continuing as single notes
    [n("F4", 4, "start"), n("A4", 4, chord=True)],
    [n("F4", 4, "both")],
    [n("F4", 2, "stop"), r(2)],
    # m10 grace note, then a plain note
    [n("B4", 0, grace=True), n("C5", 4)],
    # m11 same pitch re-struck, no tie -> two events
    [n("E4", 2), n("E4", 2)],
]
# Part 2: two voices, with a tie from voice 1 into voice 2.
P2 = [
    [n("G4", 4, "start", voice=1), "backup4", n("C4", 4, voice=2)],
    [n("E5", 4, voice=1), "backup4", n("G4", 2, "stop", voice=2), r(2, voice=2)],
]

def note_xml(e):
    if isinstance(e, str):
        return f"<backup><duration>{e[6:]}</duration></backup>"
    v = f"<voice>{e['voice']}</voice>"
    if e["p"] is None:
        return f"<note><rest/><duration>{e['d']}</duration>{v}<type>quarter</type></note>"
    step, octv = e["p"][0], e["p"][-1]
    ties = {"start": ["start"], "stop": ["stop"], "both": ["stop", "start"]}.get(e.get("tie"), [])
    typ = {0: "eighth", 2: "quarter", 4: "half"}[e["d"]]
    return ("<note>" + ("<grace/>" if e["grace"] else "") + ("<chord/>" if e["chord"] else "")
            + f"<pitch><step>{step}</step><octave>{octv}</octave></pitch>"
            + ("" if e["grace"] else f"<duration>{e['d']}</duration>")
            + "".join(f'<tie type="{t}"/>' for t in ties) + v + f"<type>{typ}</type>"
            + ("<notations>" + "".join(f'<tied type="{t}"/>' for t in ties) + "</notations>" if ties else "")
            + "</note>")

def part_xml(pid, measures):
    out = [f'<part id="{pid}">']
    for i, m in enumerate(measures, 1):
        attrs = ("<attributes><divisions>2</divisions><key><fifths>0</fifths></key>"
                 "<time><beats>2</beats><beat-type>4</beat-type></time>"
                 "<clef><sign>G</sign><line>2</line></clef></attributes>") if i == 1 else ""
        out.append(f'<measure number="{i}">{attrs}' + "".join(note_xml(e) for e in m) + "</measure>")
    return "".join(out) + "</part>"

xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<score-partwise version="3.1"><part-list>'
       '<score-part id="P1"><part-name>Violin</part-name></score-part>'
       '<score-part id="P2"><part-name>Viola</part-name></score-part></part-list>'
       + part_xml("P1", P1) + part_xml("P2", P2) + "</score-partwise>\n")
Path(__file__).with_name("ties.musicxml").write_text(xml)
