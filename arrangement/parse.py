"""MusicXML -> canonical NoteEvents with declared part labels.

Reads original sources (raw_corpora/, or the ABC MuseScore->MusicXML
conversions), never the already-processed corpus/*.musicxml OpenScore files.

Pipeline (parse_score):
  raw parse -> [movement slice] -> [expand repeats] -> sounding pitch
  -> exclude percussion (logged) -> per-pitch instances -> tie merge -> NoteEvents

Decisions:
- Ties: merged per pitch by arrangement.ties (NOT music21 stripTies, which
  splits partial-chord and note->chord ties). One tied chain = one NoteEvent.
- Transposition: every pitch is sounding pitch (score.toSoundingPitch()).
- Repeats: expanded by default (expand_repeats=True). If music21 cannot expand
  a malformed repeat structure, the notated surface is used and this is
  recorded in ParsedPiece.warnings.
- Grace notes: kept, is_grace=True, duration 0.
- Voices: voice_id is the MusicXML voice number when music21 keeps a <voice>
  layer (measures with >1 voice). music21 drops the layer in single-voice
  measures, and those notes get voice_id "1".
- Staves: music21 splits a multi-staff <part> into PartStaff streams with ids
  "<partid>-Staff<n>"; these are regrouped into one declared part, and staff_id
  is n. Single-staff parts have staff_id 1.
- Percussion: parts whose instrument is a music21 Percussion, or whose notes
  are all unpitched, are excluded whole; stray unpitched notes in pitched parts
  are dropped. Both are logged in ParsedPiece.excluded.
- Chords / divisi: each pitch is its own NoteEvent, sharing part_id.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from music21 import chord, converter, instrument as m21instrument, note, percussion, stream

from parsing import _clean_musicxml_text, _read_mxl_text
from arrangement.ties import PitchInstance, TieAnomaly, TieGroup, merge_ties

log = logging.getLogger(__name__)

_PARTSTAFF_ID_RE = re.compile(r"^(?P<part>.+)-Staff(?P<staff>\d+)$")


@dataclass
class NoteEvent:
    id: int
    onset: float             # quarterLength from start of piece (after repeat expansion)
    duration: float          # quarterLength, tied chain summed; 0 for grace notes
    pitch: int               # sounding MIDI
    part_id: int             # index into ParsedPiece.parts
    voice_id: str
    staff_id: int
    measure: int             # notated measure number (repeats as notated after expansion)
    beat_strength: float     # music21 beatStrength, from the governing time signature
    is_grace: bool
    tie_group_id: int        # stable id of the tie group; every event has one
    is_tied: bool            # True when the event merged >1 notated notes; False = not a tie
    part_inferred: bool = False  # True when part_id comes from a track/channel guess, not a declared part

    @property
    def end(self) -> float:
        return self.onset + self.duration


@dataclass
class DeclaredPart:
    part_id: int
    xml_id: str
    name: str                 # partName as declared
    instrument_name: str      # music21 instrument name (unreliable in ABC exports)
    n_staves: int
    transposition: str | None  # written->sounding directed interval, e.g. "M-2"
    declared: bool = True     # False when the part was inferred (MIDI track/channel without instrument)


@dataclass
class ParsedPiece:
    source: str
    events: list[NoteEvent]
    parts: list[DeclaredPart]
    total_duration: float     # quarterLength of the (expanded) piece
    repeats_expanded: bool
    excluded: list[dict] = field(default_factory=list)
    tie_anomalies: list[TieAnomaly] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_format: str = "musicxml"
    movement: int | None = None


def load_raw_score(path: str | Path) -> stream.Score:
    """Parse MusicXML/.mxl with the same tag cleanup as the ladder, but no
    normalization (no stripTies, no voice splitting, written pitch)."""
    path = Path(path)
    text = _read_mxl_text(path) if path.suffix.lower() == ".mxl" else path.read_text(encoding="utf-8")
    return converter.parse(drop_cue_notes(_unhide_notations(_clean_musicxml_text(text))), format="musicxml")


def drop_cue_notes(text: str) -> str:
    """Remove <note>s carrying <cue/> (printed reminders of another part, not
    played). music21 ignores <cue/> and would import them as real notes.
    A cue note that advances time is replaced by a <forward> of the same
    duration in the same voice/staff so the rest of the measure keeps its
    timing; chord members and grace cues are simply removed."""
    if "<cue" not in text:
        return text
    root = ET.fromstring(text.encode("utf-8"))
    for measure in root.iter("measure"):
        for k, n in reversed(list(enumerate(measure))):
            if n.tag != "note" or n.find("cue") is None:
                continue
            measure.remove(n)
            dur = n.find("duration")
            if n.find("chord") is not None or n.find("grace") is not None or dur is None:
                continue
            fwd = ET.Element("forward")
            fwd.append(dur)
            for tag in ("voice", "staff"):
                x = n.find(tag)
                if x is not None:
                    fwd.append(x)
            measure.insert(k, fwd)
    return ET.tostring(root, encoding="unicode")


_HIDDEN_NOTATIONS_RE = re.compile(r'(<notations\b[^>]*?)\s+print-object="no"')


def _unhide_notations(text: str) -> str:
    """music21 10.5 crashes (AttributeError: 'NoneType' object has no
    attribute 'style') on <notations print-object="no"> holding an ornament it
    resolves to None, e.g. a lone accidental-mark. Visibility of notations has
    no effect on pitch or timing, so drop the attribute there. Hits 2 OpenScore
    files (Haydn Op.76/6, Mayer D minor)."""
    return _HIDDEN_NOTATIONS_RE.sub(r"\1", text)


def movement_index_ranges(score: stream.Score) -> list[tuple[int, int]]:
    """Measure-index ranges per movement, split where measure numbers reset.
    Same rule as build_corpus.movement_index_ranges (see its docstring)."""
    measures = list(score.parts[0].getElementsByClass(stream.Measure))
    bounds = [0] + [i for i in range(1, len(measures)) if measures[i].number < measures[i - 1].number]
    bounds.append(len(measures))
    return list(zip(bounds, bounds[1:]))


def slice_movement(score: stream.Score, movement: int) -> stream.Score:
    """1-based movement from a multi-movement OpenScore file."""
    ranges = movement_index_ranges(score)
    if not 1 <= movement <= len(ranges):
        raise ValueError(f"movement {movement} requested, {len(ranges)} detected")
    a, b = ranges[movement - 1]
    # indicesNotNumbers end index is EXCLUSIVE (build_corpus.py passes b - 1 and
    # so drops every movement's final measure).
    return score.measures(a, b, indicesNotNumbers=True)


def _voice_of(el) -> str:
    site = el.activeSite
    if isinstance(site, stream.Voice) and site.id is not None:
        return str(site.id)
    return "1"


def _is_percussion(part: stream.Part) -> bool:
    inst = part.getInstrument(returnDefault=False)
    if inst is not None and isinstance(inst, m21instrument.Percussion):
        return True
    notes = list(part.recurse().notes)
    return bool(notes) and all(isinstance(n, (note.Unpitched, percussion.PercussionChord)) for n in notes)


def _group_streams(score: stream.Score) -> list[tuple[str, list[tuple[int, int, stream.Part]]]]:
    """[(xml_part_id, [(stream_idx, staff_no, stream), ...]), ...] in score order."""
    groups: dict[str, list] = {}
    for idx, p in enumerate(score.parts):
        m = _PARTSTAFF_ID_RE.match(str(p.id)) if isinstance(p, stream.PartStaff) else None
        key, staff = (m.group("part"), int(m.group("staff"))) if m else (str(p.id), 1)
        groups.setdefault(key, []).append((idx, staff, p))
    return list(groups.items())


def collect_pitch_instances(score: stream.Score, stream_indices: set[int] | None = None) -> list[PitchInstance]:
    """One PitchInstance per pitch per notated note/chord. Expects a score
    already at sounding pitch. Unpitched notes are skipped."""
    out: list[PitchInstance] = []
    for stream_idx, part in enumerate(score.parts):
        if stream_indices is not None and stream_idx not in stream_indices:
            continue
        for el in part.recurse().notes:
            if isinstance(el, (note.Unpitched, percussion.PercussionChord)):
                continue
            onset = Fraction(el.getOffsetInHierarchy(part))
            dur = Fraction(el.duration.quarterLength)
            voice = _voice_of(el)
            is_grace = bool(el.duration.isGrace)
            members = el.notes if isinstance(el, chord.Chord) else (el,)
            # Artificial harmonic = a stopped note plus a diamond touch-point in
            # one chord. The diamond is a fingering mark, not a sounded note:
            # drop it and keep the stopped (fingered) pitch. A lone diamond
            # (natural harmonic) is kept as written.
            touch = {ci for ci, n in enumerate(members) if n.notehead == "diamond"}
            if len(touch) == len(members):
                touch = set()
            for ci, n in enumerate(members):
                if ci in touch:
                    continue
                out.append(PitchInstance(
                    stream_idx=stream_idx, voice=voice, midi=int(n.pitch.midi),
                    onset=onset, duration=Fraction(0) if is_grace else dur,
                    tie=n.tie.type if n.tie is not None and n.tie.type != "let-ring" else None,
                    is_grace=is_grace, measure=el.measureNumber or 0, src=(el, ci),
                ))
    return out


def merge_shared_unisons(events: list[NoteEvent]) -> tuple[list[NoteEvent], int]:
    """One part, same pitch, same onset, different voices -> one note (the
    longest; ties: lowest id). Typical case: a chord in one voice under its top
    note held in another voice; one string plays it once. Unisons within one
    voice's chord are deliberate unison double stops and are kept. Ids are
    renumbered densely in the original order."""
    keep: dict[tuple, NoteEvent] = {}
    drop: set[int] = set()
    for e in events:
        if e.is_grace:
            continue
        k = (e.part_id, e.pitch, e.onset)
        other = keep.get(k)
        if other is None:
            keep[k] = e
        elif other.voice_id != e.voice_id or other.staff_id != e.staff_id:
            loser = e if (e.duration, -e.id) <= (other.duration, -other.id) else other
            drop.add(loser.id)
            keep[k] = other if loser is e else e
    if not drop:
        return events, 0
    out = [e for e in events if e.id not in drop]
    for k, e in enumerate(out):
        e.id = k
    return out, len(drop)


def tie_merged_groups(score: stream.Score) -> tuple[list[TieGroup], list[TieAnomaly]]:
    return merge_ties(collect_pitch_instances(score))


def parse_score(path: str | Path, expand_repeats: bool = True, movement: int | None = None,
                score: stream.Score | None = None) -> ParsedPiece:
    """Full pipeline. Pass `score` to reuse an already-parsed raw score (it is
    not mutated); `movement` slices a multi-movement file first."""
    warnings: list[str] = []
    s = score if score is not None else load_raw_score(path)
    if movement is not None:
        s = slice_movement(s, movement)

    repeats_expanded = False
    if expand_repeats:
        try:
            s = s.expandRepeats()
            repeats_expanded = True
        except Exception as e:  # music21 raises ExpanderException on malformed repeats
            warnings.append(f"repeat expansion failed, using notated surface: {e}")
            log.warning("%s: repeat expansion failed: %s", path, e)

    written = s
    s = s.toSoundingPitch()

    excluded: list[dict] = []
    parts: list[DeclaredPart] = []
    stream_to_part: dict[int, tuple[int, int]] = {}  # stream_idx -> (part_id, staff_no)
    for xml_id, members in _group_streams(s):
        first = members[0][2]
        if any(_is_percussion(p) for _, _, p in members):
            excluded.append({"kind": "percussion_part", "xml_id": xml_id, "name": first.partName,
                             "notes": sum(len(p.recurse().notes) for _, _, p in members)})
            log.info("%s: excluded percussion part %r", path, first.partName)
            continue
        part_id = len(parts)
        inst = written.parts[members[0][0]].getInstrument(returnDefault=False)
        parts.append(DeclaredPart(
            part_id=part_id, xml_id=xml_id, name=first.partName or xml_id,
            instrument_name=(inst.instrumentName if inst is not None else "") or "",
            n_staves=len(members),
            transposition=inst.transposition.directedName if inst is not None and inst.transposition else None,
        ))
        for idx, staff, _ in members:
            stream_to_part[idx] = (part_id, staff)

    stray = sum(1 for idx in stream_to_part for el in s.parts[idx].recurse().notes
                if isinstance(el, (note.Unpitched, percussion.PercussionChord)))
    if stray:
        excluded.append({"kind": "unpitched_notes_in_pitched_part", "notes": stray})

    groups, anomalies = merge_ties(collect_pitch_instances(s, set(stream_to_part)))

    events: list[NoteEvent] = []
    for g in groups:
        first = g.first
        el, _ = first.src
        part_id, staff = stream_to_part[first.stream_idx]
        events.append(NoteEvent(
            id=len(events), onset=float(g.onset), duration=float(g.duration), pitch=first.midi,
            part_id=part_id, voice_id=first.voice, staff_id=staff, measure=first.measure,
            beat_strength=float(el.beatStrength or 0.0), is_grace=first.is_grace,
            tie_group_id=g.group_id, is_tied=g.is_tied,
        ))
    events, n_merged = merge_shared_unisons(events)
    if n_merged:
        excluded.append({"kind": "shared_unison_merged", "notes": n_merged})

    return ParsedPiece(
        source=str(path), events=events, parts=parts, total_duration=float(s.highestTime),
        repeats_expanded=repeats_expanded, excluded=excluded, tie_anomalies=anomalies,
        warnings=warnings, movement=movement,
    )
