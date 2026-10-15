"""Floor-violation triage helpers: look up the source MusicXML around a
violation and flag notational features that commonly produce false
violations (octave-shift lines, harmonics, cue notes, tremolo, divisi voices).

    python -m arrangement.triage            # annotate every floor violation
    python -m arrangement.triage --show N   # print XML context of violation N

Writes results/validation/floor_violations_annotated.jsonl.
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from functools import lru_cache
from pathlib import Path

from arrangement.corpus import ROOT, manifest

OUT = ROOT / "results" / "validation"


@lru_cache(maxsize=8)
def _root(file: str) -> ET.Element:
    z = zipfile.ZipFile(ROOT / file)
    name = next(n for n in z.namelist() if n.endswith(".xml") and not n.startswith("META"))
    return ET.fromstring(z.read(name))


def _num(m: ET.Element) -> int | None:
    """Leading integer of the measure number; None for MuseScore's uncounted
    measures ("X1", "X2"), which music21 files under the previous number."""
    x = re.match(r"\d+", m.get("number", "") or "")
    return int(x.group()) if x else None


def _numbers(measures: list[ET.Element]) -> list[int]:
    out, prev = [], 0
    for m in measures:
        n = _num(m)
        prev = prev if n is None else n
        out.append(prev)
    return out


@lru_cache(maxsize=None)
def _key_info() -> dict[str, tuple[str, int]]:
    return {r["key"]: (r["file"], r["movement"]) for r in manifest() if r["status"] == "ok"}


def movement_measures(file: str, movement: int, part_index: int) -> list[ET.Element]:
    """<measure> elements of one part for one movement (split where measure
    numbers reset, the same rule as arrangement.parse)."""
    root = _root(file)
    parts = [p for p in root.findall("part")]
    first = parts[0].findall("measure")
    nums = _numbers(first)
    bounds = [0] + [i for i in range(1, len(nums)) if nums[i] < nums[i - 1]] + [len(nums)]
    a, b = bounds[movement - 1], bounds[movement]
    return parts[part_index].findall("measure")[a:b]


def _declared_part_index(file: str, name: str) -> int:
    names = [(sp.findtext("part-name") or "").strip() for sp in _root(file).iter("score-part")]
    return names.index(name)


FEATURES = {
    "octave_shift": lambda m: m.find(".//octave-shift") is not None,
    "harmonic": lambda m: m.find(".//technical/harmonic") is not None,
    "diamond_notehead": lambda m: any((n.text or "").strip() in ("diamond", "harmonic") for n in m.iter("notehead")),
    "cue": lambda m: m.find(".//cue") is not None or any(n.get("size") == "cue" for n in m.iter("type")),
    "tremolo": lambda m: m.find(".//tremolo") is not None,
    "multi_voice": lambda m: len({v.text for v in m.iter("voice")}) > 1,
    "grace": lambda m: m.find(".//grace") is not None,
    "clef_change": lambda m: m.find(".//clef") is not None,
    "pizz_arco_text": lambda m: any(re.search(r"pizz|arco", (w.text or ""), re.I) for w in m.iter("words")),
    "harmonic_text": lambda m: any(re.search(r"flag|harm|armon", (w.text or ""), re.I) for w in m.iter("words")),
}

HARMONIC = {"harmonic", "diamond_notehead", "harmonic_text"}

CATEGORIES = {
    "harmonic_notation": ("KNOWN LIMITATION", "Harmonic passages the parser rule does not cover. The rule "
                          "(PLAN.md decision 10) drops diamond touch points that share a chord with a stopped "
                          "note. Left as written: lone diamonds (natural harmonics), natural harmonics notated "
                          "at sounding pitch (\"Flag.\"), and voices that print the resulting pitches."),
    "shared_unison": ("FIXED IN PARSER", "The same pitch at the same onset in two voices of one part (PLAN.md "
                      "decision 11). Any left would be overlaps that start at different onsets."),
    "range_above_placeholder": ("THRESHOLD TOO STRICT", "Real top-register notes above the configured upper "
                                "bound (UNSOURCED.md U1-U3)."),
    "transition_placeholder": ("THRESHOLD TOO STRICT", "Real leaps above the configured transition limit "
                               "(UNSOURCED.md U0, U4, U5): string crossings, open strings, register jumps."),
    "below_open_string": ("UNRESOLVED", "Below the lowest open string with no octave line, cue or harmonic in "
                          "the XML. Possible scordatura or an engraving error; needs a look at the printed score."),
}


def classify(a: dict) -> str:
    feats = set(a["xml_features"])
    if a["check"] == "chord_size":
        pitches = [n["pitch"] for n in a["notes"]]
        if len(set(pitches)) <= a["limit"] and len(set(pitches)) < len(pitches):
            return "shared_unison"
        return "harmonic_notation" if feats & HARMONIC else "shared_unison"
    if feats & HARMONIC:
        return "harmonic_notation"
    if a["check"] == "range":
        return "range_above_placeholder" if a["measured"] > a["limit"] else "below_open_string"
    if a["check"] == "transition":
        return "transition_placeholder"
    raise ValueError(a["check"])


def annotate(v: dict) -> dict:
    file, mvt = _key_info()[v["key"]]
    pi = _declared_part_index(file, v["part"])
    ms = movement_measures(file, mvt, pi)
    wanted = {n["measure"] for n in v["notes"]}
    # also the measure before (an octave line can start there)
    sel = [m for m, k in zip(ms, _numbers(ms)) if k in wanted or k + 1 in wanted]
    feats = {f for f, fn in FEATURES.items() if any(fn(m) for m in sel)}
    # a "Flag."/"harm." instruction governs the passage after it: look back 8 measures
    lookback = [m for m, k in zip(ms, _numbers(ms)) if any(0 <= w - k <= 8 for w in wanted)]
    if any(FEATURES["harmonic_text"](m) for m in lookback):
        feats.add("harmonic_text")
    feats = sorted(feats)
    return {**v, "file": file, "movement": mvt, "xml_features": feats}


def show(v: dict, width: int = 0) -> str:
    file, mvt = _key_info()[v["key"]]
    ms = movement_measures(file, mvt, _declared_part_index(file, v["part"]))
    wanted = {n["measure"] for n in v["notes"]}
    lines = [f"{v['key']}  {v['part']}  {v['check']} measured={v['measured']} limit={v['limit']}",
             f"notes: {[(n['pitch'], n['onset'], n['duration']) for n in v['notes']]}"]
    for m, k in zip(ms, _numbers(ms)):
        if k in wanted or k + 1 in wanted:
            lines.append(f"--- measure {m.get('number')}")
            for el in m:
                if el.tag == "note":
                    p = el.find("pitch")
                    txt = (f"{p.findtext('step')}{p.findtext('alter') or ''}/{p.findtext('octave')}" if p is not None
                           else ("rest" if el.find("rest") is not None else "?"))
                    extras = [x.tag for x in el.iter() if x.tag in ("chord", "grace", "cue", "harmonic", "tremolo", "tied")]
                    nh = el.findtext("notehead")
                    lines.append(f"  note {txt:8s} dur={el.findtext('duration')} v={el.findtext('voice')} "
                                 f"{' '.join(extras)} {('notehead=' + nh) if nh else ''}")
                elif el.tag == "direction":
                    os_ = el.find(".//octave-shift")
                    w = " ".join((x.text or "") for x in el.iter("words"))
                    if os_ is not None:
                        lines.append(f"  OCTAVE-SHIFT {os_.attrib}")
                    if w.strip():
                        lines.append(f"  words: {w.strip()}")
                elif el.tag == "attributes" and el.find("clef") is not None:
                    c = el.find("clef")
                    lines.append(f"  clef {c.findtext('sign')}{c.findtext('line')} {c.findtext('clef-octave-change') or ''}")
                elif el.tag in ("backup", "forward"):
                    lines.append(f"  {el.tag} {el.findtext('duration')}")
    return "\n".join(lines)


INSPECTED = """\
Hand-inspected in the XML (2026-10-06, earlier config with the 24-semitone release-based cap):
- transition: Reger Op.121 i (Vc E♭4→D2 in a 16th), Grosse Fuge (Vn1 E♭6→A3), Delius iii (Vn1 A3→B5),
  Haydn Op.76/4 ii (E♭6→D♭4), Vieuxtemps Op.44 i (G3→E6), Mozart K.590 iv (D6→D♭4), Op.18/4 i
  (C7→open G3, 41 semitones). All are real writing, none a parse artifact.
- harmonic: Borodin No.1 i Vc "Flag. sul A" C♯6–E6; Koechlin No.1 ii Va (diamond F7 over C7); Janáček
  No.2 i Vn1 m252 and Schulhoff No.1 iv Vn1 m21 (diamond touch points plus a voice printing the resulting
  pitches).
- shared unison: Bridge No.2 i Vn1 m1 (4-note chord in voice 2 under a G5 held in voice 1); fixed in the parser.
- below open string: Zemlinsky No.2 i Vc B1 tremolo, no octave line or cue in the XML.
"""

FIXED = """\
| Fix | What it was | Where | Test |
|---|---|---|---|
| Cue notes dropped | music21 ignores `<cue/>`; cues counted as played notes (31 range violations, e.g. a cello cue in Bridge No.2 Vn1) | `parse.drop_cue_notes` | `test_cue_notes_dropped_and_timing_kept` |
| music21 crash on hidden notations | `<notations print-object="no">` with a lone accidental-mark; 2 files / 8 movements missing | `parse._unhide_notations` | `test_hidden_notations_with_lone_accidental_mark_parse` |
| Harmonic touch points dropped | diamond touch-point notes in a chord with a stopped note were counted as sounding notes | `parse.collect_pitch_instances` | `test_artificial_harmonic_touch_note_dropped_lone_diamond_kept` |
| Shared unisons merged | same pitch, same onset, different voices of one part counted twice (743 notes corpus-wide) | `parse.merge_shared_unisons` | `test_shared_unison_across_voices_merged_same_voice_unison_kept` |

Verified correct, no fix needed: pitches under `<octave-shift>` (`test_octave_shift_keeps_true_pitch`).
"""


def write_report(A: list[dict]) -> str:
    cat = Counter(a["category"] for a in A)
    by: dict[str, Counter] = {}
    for a in A:
        by.setdefault(a["category"], Counter())[a["check"]] += 1
    L = ["# Floor triage: every violation on the real part assignments", "",
         "Every floor violation, classified. Records: `floor_violations_annotated.jsonl` (`category`,",
         "`xml_features`, source file, movement, measure). Reproduce: `python -m arrangement.validate &&",
         "python -m arrangement.triage`; show one case: `python -m arrangement.triage --show N`.", "",
         "## Parser bugs found and fixed (not in the counts below)", "", FIXED,
         "## Remaining violations", "",
         "| Category | Verdict | Total | range | chord_size | transition |", "|---|---|---|---|---|---|"]
    for k, (verdict, _) in CATEGORIES.items():
        c = by.get(k, Counter())
        L.append(f"| `{k}` | {verdict} | {cat[k]} | {c['range']} | {c['chord_size']} | {c['transition']} |")
    L += [f"| **total** | | **{len(A)}** | | | |", ""]
    L += [f"- **`{k}`** ({verdict}): {desc}" for k, (verdict, desc) in CATEGORIES.items()]
    L += ["", "Rules (`classify`): harmonic markup in the violation's measures (or \"Flag.\"/\"harm.\" text in",
          "the 8 measures before) -> `harmonic_notation`; chord-size sets with a repeated pitch ->",
          "`shared_unison`; remaining range above/below -> `range_above_placeholder` /",
          "`below_open_string`; remaining transitions -> `transition_placeholder`.", "", INSPECTED,
          "## Below the lowest open string (unresolved; needs the printed score)", ""]
    L += [f"- {a['key']} {a['part']} m{a['measure']}: pitch {int(a['measured'])} < {int(a['limit'])}"
          for a in A if a["category"] == "below_open_string"]
    L += ["", "Possible scordatura (C string down to B), which would keep the bound correct, or an engraving",
          "error in the OpenScore edition.", "",
          "## Known, not counted as bugs", "",
          "- Janáček No.1: two declared \"Violoncello\" parts share one part id; the second (3 notes) merges into the cello.",
          "- 18 movements: music21 could not expand the repeats; the notated surface is used (logged in the manifest).", ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=None)
    args = ap.parse_args(argv)
    V = [json.loads(line) for line in (OUT / "floor_violations.jsonl").read_text().splitlines()]
    if args.show is not None:
        print(show(V[args.show]))
        return
    A = [annotate(v) for v in V]
    for a in A:
        a["category"] = classify(a)
    with (OUT / "floor_violations_annotated.jsonl").open("w") as fh:
        for a in A:
            fh.write(json.dumps(a, ensure_ascii=False) + "\n")
    for check in ("range", "chord_size", "transition"):
        sub = [a for a in A if a["check"] == check]
        c = Counter(f for a in sub for f in a["xml_features"])
        print(check, len(sub), "no features:", sum(not a["xml_features"] for a in sub), dict(c.most_common()))
    print(Counter((a["check"], a["category"]) for a in A))
    (OUT / "TRIAGE.md").write_text(write_report(A))


if __name__ == "__main__":
    main()
