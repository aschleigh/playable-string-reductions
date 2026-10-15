"""Generates tests/fixtures/ensemble.musicxml: transposing instruments, a
two-staff piano with two voices on the upper staff, and unpitched percussion.

4/4, divisions=1 (quarter = 1). Written pitches are chosen so sounding pitch
is easy to check by hand:
  Clarinet in Bb (transpose -2): written D5 E5 F#5 G5  -> sounding C5 D5 E5 F5 (72 74 76 77)
  Horn in F      (transpose -7): written G4 A4 B4 C5   -> sounding C4 D4 E4 F4 (60 62 64 65)
  Piano staff 1 voice 1: C5 half, D5 half; voice 2: E4 whole
  Piano staff 2: [C3 G3] whole (a chord -> two events, same part)
  Snare (unpitched): 4 quarter strokes -> excluded and logged
"""
from pathlib import Path

def pitched(step, octv, dur, typ, alter=0, voice=1, staff=None, chord=False):
    return ("<note>" + ("<chord/>" if chord else "") + f"<pitch><step>{step}</step>"
            + (f"<alter>{alter}</alter>" if alter else "") + f"<octave>{octv}</octave></pitch>"
            + f"<duration>{dur}</duration><voice>{voice}</voice><type>{typ}</type>"
            + (f"<staff>{staff}</staff>" if staff else "") + "</note>")

def attrs(clef="<clef><sign>G</sign><line>2</line></clef>", transpose="", staves=""):
    return ("<attributes><divisions>1</divisions><key><fifths>0</fifths></key>"
            "<time><beats>4</beats><beat-type>4</beat-type></time>" + staves + clef + transpose + "</attributes>")

cl = attrs(transpose="<transpose><diatonic>-1</diatonic><chromatic>-2</chromatic></transpose>") + \
     pitched("D", 5, 1, "quarter") + pitched("E", 5, 1, "quarter") + pitched("F", 5, 1, "quarter", alter=1) + pitched("G", 5, 1, "quarter")
hn = attrs(transpose="<transpose><diatonic>-4</diatonic><chromatic>-7</chromatic></transpose>") + \
     pitched("G", 4, 1, "quarter") + pitched("A", 4, 1, "quarter") + pitched("B", 4, 1, "quarter") + pitched("C", 5, 1, "quarter")
pno = attrs(staves="<staves>2</staves>",
            clef='<clef number="1"><sign>G</sign><line>2</line></clef><clef number="2"><sign>F</sign><line>4</line></clef>') + \
      pitched("C", 5, 2, "half", staff=1) + pitched("D", 5, 2, "half", staff=1) + \
      "<backup><duration>4</duration></backup>" + pitched("E", 4, 4, "whole", voice=2, staff=1) + \
      "<backup><duration>4</duration></backup>" + pitched("C", 3, 4, "whole", voice=5, staff=2) + \
      pitched("G", 3, 4, "whole", voice=5, staff=2, chord=True)
sn = attrs(clef="<clef><sign>percussion</sign></clef>") + "".join(
     "<note><unpitched><display-step>C</display-step><display-octave>5</display-octave></unpitched>"
     "<duration>1</duration><instrument id=\"P4-I1\"/><voice>1</voice><type>quarter</type></note>" for _ in range(4))

xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1"><part-list>
<score-part id="P1"><part-name>Clarinet in B♭</part-name><score-instrument id="P1-I1"><instrument-name>Clarinet in B♭</instrument-name></score-instrument></score-part>
<score-part id="P2"><part-name>Horn in F</part-name><score-instrument id="P2-I1"><instrument-name>Horn in F</instrument-name></score-instrument></score-part>
<score-part id="P3"><part-name>Piano</part-name><score-instrument id="P3-I1"><instrument-name>Piano</instrument-name></score-instrument></score-part>
<score-part id="P4"><part-name>Snare Drum</part-name><score-instrument id="P4-I1"><instrument-name>Snare Drum</instrument-name></score-instrument></score-part>
</part-list>
<part id="P1"><measure number="1">{cl}</measure></part>
<part id="P2"><measure number="1">{hn}</measure></part>
<part id="P3"><measure number="1">{pno}</measure></part>
<part id="P4"><measure number="1">{sn}</measure></part>
</score-partwise>
"""
Path(__file__).with_name("ensemble.musicxml").write_text(xml)
