import json, sys
from collections import defaultdict, Counter
from fractions import Fraction as F
from pathlib import Path
import numpy as np
sys.path.insert(0, "/scratch/ashleyz/reduction_ladder")
from decoding.render_excerpts import build, hard_marks, merge_unisons, _hand_split, QUARTET, LEGEND
from arrangement.instruments import load_ensemble
from arrangement.eval.reduction import voice_tiers
from arrangement.eval.fidelity import chroma_per_beat
from arrangement.checker.incremental import best_two_hand_span
S = "/scratch/shared/ashleyz/tmp/claude-28774/-scratch-ashleyz-reduction-ladder/12f0879f-f358-4ec2-87f0-8ae62a6655a1/scratchpad"
dec = json.load(open(f"{S}/humanref_decoded.json"))
L = lambda rows: [(int(p), F(o), F(d), int(x)) for p, o, d, x in rows]
src = L(dec["source"])
cl = [(h, F(o), F(d), x) for h, o, d, x in json.load(open(f"{S}/clementi_l27.json"))]
ref = [(h, o, d, x) for h, o, d, x in cl if o < 64] + [(h, o - 16, d, x) for h, o, d, x in cl if 80 <= o < 96]
systems = {"Clementi (1803, human)": [(0, o, d, x) for h, o, d, x in ref],
           "control-FK2 (ours)": L(dec["control-FK2"]), "control-FK3 (ours, thinner)": L(dec["control-FK3"])}
ss = sorted(src, key=lambda n: (n[1], n[3], n[2])); tiers = voice_tiers(ss)
def keyset(ns, pc=False): return {(o, x % 12 if pc else x) for _, o, d, x in ns if d > 0}
def near(o, x, S_):  # same pitch, onset within a 16th
    return any(abs(o - y) < F(1, 4) for y in S_.get(x, ()))
def index(ns, pc=False):
    by = defaultdict(list)
    for _, o, d, x in ns: by[x % 12 if pc else x].append(o)
    return by
def chroma_cos(a, b):
    Ca, Cb = chroma_per_beat(tuple(a), F(0), F(80)), chroma_per_beat(tuple(b), F(0), F(80))
    na, nb = np.linalg.norm(Ca, axis=1), np.linalg.norm(Cb, axis=1); sel = nb > 0
    return float(np.where(na[sel] > 0, (Ca[sel] * Cb[sel]).sum(1) / np.maximum(na[sel] * nb[sel], 1e-300), 0).mean())
ens = load_ensemble("piano")
rows = {}
refn = systems["Clementi (1803, human)"]
for name, ns in systems.items():
    by = index(ns)
    ret = {t: np.mean([near(o, x, by) for (p, o, d, x), tt in zip(ss, tiers) if tt == t]) for t in ("top", "bass", "inner")}
    struck = defaultdict(list)
    for _, o, d, x in ns: struck[o].append(x)
    spans = [best_two_hand_span(sorted(set(v)), 5) or 0 for v in struck.values()]
    pcs = [len({x for x in v}) for v in struck.values()]
    marks = hard_marks([(o, d, x, 0) for _, o, d, x in ns], ens)
    r = {"notes": len(ns), "notes_per_onset": float(np.mean([len(v) for v in struck.values()])),
         "max_notes_at_once": max(len(v) for v in struck.values()),
         "hand_span_max": max(spans), "chords_needing_hand_over_octave": sum(s > 12 for s in spans),
         "kept_melody": float(ret["top"]), "kept_bass": float(ret["bass"]), "kept_inner": float(ret["inner"]),
         "harmony_vs_quartet": chroma_cos(ns, src), "checker_v7_violations": sum(1 for v in marks.values() if v)}
    if name != "Clementi (1803, human)":
        for pc in (False, True):
            a, b = index(ns, pc), index(refn, pc)
            rec = np.mean([near(o, x % 12 if pc else x, a) for _, o, d, x in refn])
            pre = np.mean([near(o, x % 12 if pc else x, b) for _, o, d, x in ns])
            k = "pitch_class" if pc else "exact_pitch"
            r[f"agree_{k}_recall"] = float(rec); r[f"agree_{k}_precision"] = float(pre)
        r["harmony_vs_clementi"] = chroma_cos(ns, refn)
    rows[name] = r
rows["source quartet (bars 1-20)"] = {"notes": len(src)}
od = Path("decoding/results/examples/human-ref-haydn-emperor/076-3_m02_bars1-20"); od.mkdir(parents=True, exist_ok=True)
json.dump(rows, open(od.parent / "compare.json", "w"), indent=1)
for k, v in rows.items(): print(k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in v.items()})
# render (MusicXML only)
bars = [(F(4 * k), F(4)) for k in range(20)]
meta = [{"fifths": 1, "ts": "2/2", "number": k + 1} for k in range(20)]
sub = "Haydn, String Quartet Op. 76 No. 3, II (Emperor hymn), bars 1-20"
files = [("0_source_quartet", "Source string quartet", [(o, d, x, p) for p, o, d, x in src], None),
         ("1_clementi_human_piano", "Clementi, piano (1803), Op. 42 Lesson XXVII (Mutopia, CC BY-SA 4.0)", [(o, d, x, h) for h, o, d, x in ref], "own"),
         ("2_control-FK2_piano", "Arranger control-FK2, piano, masked", [(o, d, x, 0) for _, o, d, x in systems["control-FK2 (ours)"]], "split"),
         ("3_control-FK3_piano", "Arranger control-FK3 (thinner), piano, masked", [(o, d, x, 0) for _, o, d, x in systems["control-FK3 (ours, thinner)"]], "split")]
for fname, label, notes, hands in files:
    if hands is None:
        names, keys, marks = QUARTET, ["violin", "violin", "viola", "cello"], {}
    else:
        marks = hard_marks([(o, d, x, 0) for o, d, x, _ in notes], ens)
        if hands == "split":
            notes = [(o, d, x, h) for (o, d, x, _), h in zip(notes, _hand_split(notes))]
        names, keys = ["Piano (right hand)", "Piano (left hand)"], ["piano", "piano_lh"]
    notes, marks, _ = merge_unisons(notes, marks)
    sc, _ = build(label, sub, names, keys, notes, marks, bars, meta, 0, 19)
    sc.write("musicxml", fp=str(od / f"{fname}.musicxml"))
print(od)
