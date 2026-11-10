# One score, stacked for comparison: Clementi (RH, LH), control-FK2 (RH, LH), control-FK3 (RH, LH). Display only.
import json, sys
from fractions import Fraction as F
sys.path.insert(0, "/scratch/ashleyz/reduction_ladder")
from decoding.render_excerpts import build, merge_unisons
from arrangement.piano_hands import assign_hands
O = "/scratch/ashleyz/reduction_ladder/decoding/results/examples/human-ref-haydn-emperor"
dec = json.load(open("/scratch/shared/ashleyz/tmp/claude-28774/-scratch-ashleyz-reduction-ladder/12f0879f-f358-4ec2-87f0-8ae62a6655a1/scratchpad/humanref_decoded.json"))
cl = [(h, F(o), F(d), x) for h, o, d, x in json.load(open(f"{O}/clementi_l27.json"))]
ref = [(o, d, x, h) for h, o, d, x in cl if o < 64] + [(o - 16, d, x, h) for h, o, d, x in cl if 80 <= o < 96]
notes = list(ref)
for k, run in enumerate(("control-FK2", "control-FK3"), start=1):
    ns = [(F(o), F(d), int(x), 0) for p, o, d, x in dec[run]]
    notes += [(o, d, x, 2 * k + h) for (o, d, x, _), h in zip(ns, assign_hands([(o, d, x) for o, d, x, _ in ns]))]
notes, marks, _ = merge_unisons(notes, {})
bars = [(F(4 * k), F(4)) for k in range(20)]; meta = [{"fifths": 1, "ts": "2/2", "number": k + 1} for k in range(20)]
names = ["Clementi RH", "Clementi LH", "FK2 RH", "FK2 LH", "FK3 RH", "FK3 LH"]
sc, _ = build("Clementi vs our arranger, piano", "Haydn Op. 76 No. 3, II, bars 1-20", names,
              ["piano", "piano_lh"] * 3, notes, marks, bars, meta, 0, 19)
sc.write("musicxml", fp=f"{O}/076-3_m02_bars1-20/4_side_by_side_clementi_FK2_FK3.musicxml")
print("ok")
