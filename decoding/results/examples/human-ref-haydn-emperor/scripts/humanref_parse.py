import sys, json
from fractions import Fraction as F
from music21 import converter
s = converter.parse(sys.argv[1])
out = []
for h, p in enumerate(s.parts):
    for n in p.recurse().notes:
        o = F(n.getOffsetInHierarchy(s)).limit_denominator(48); d = F(n.quarterLength).limit_denominator(48)
        for x in (n.pitches if n.isChord else [n.pitch]):
            out.append([h, str(o), str(d), x.midi])
json.dump(out, open(sys.argv[2], "w"))
top = {}
for h, o, d, x in out:
    top[F(o)] = max(top.get(F(o), 0), x)
print(sorted(top.items())[:24]); print("odd onsets", sorted({F(o) for _, o, _, _ in out if (F(o) * 4).denominator != 1})[:20])
