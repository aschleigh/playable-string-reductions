"""MIDI (.mid/.midi): the degraded path.

MIDI has tracks and channels, not declared parts. A part here is one
(track, channel) pair that carries notes. It counts as declared only if that
channel has a program change in its track, or the track has an
instrument-name meta event. Otherwise every event in it is part_inferred=True
and the DeclaredPart has declared=False. Even "declared" MIDI parts carry no
notation (voices, ties, staves), so ParsedPiece.source_format == "midi" lets
downstream code exclude MIDI from ground truth entirely; the floor validation
uses MusicXML only.

Read at the raw event level (music21.midi), not via converter.parse, which
quantizes onsets. Onsets/durations are exact Fractions of the file's ticks per
quarter. Channel 10 (index 9) is General MIDI percussion and is excluded.
MIDI is sounding pitch and has no ties, so neither needs resolving.
"""
from __future__ import annotations

from collections import defaultdict, deque
from fractions import Fraction
from pathlib import Path

from music21 import meter, midi as m21midi

from arrangement.parse import DeclaredPart, NoteEvent, ParsedPiece

PERCUSSION_CHANNEL = 10   # 1-based, as music21 reports it
CVM = m21midi.ChannelVoiceMessages
META = m21midi.MetaEvents


def _text(data) -> str:
    return data.decode("latin-1", "replace") if isinstance(data, (bytes, bytearray)) else str(data or "")


class _Meter:
    """Measure number and beat strength from the file's time-signature events."""

    def __init__(self, changes: list[tuple[Fraction, str]]):
        changes = sorted(changes) or [(Fraction(0), "4/4")]
        if changes[0][0] != 0:
            changes.insert(0, (Fraction(0), "4/4"))
        self.segments = []   # (start, first_measure, bar_length, TimeSignature)
        measure = 1
        for k, (start, sig) in enumerate(changes):
            ts = meter.TimeSignature(sig)
            bar = Fraction(ts.barDuration.quarterLength)
            self.segments.append((start, measure, bar, ts))
            if k + 1 < len(changes):
                measure += -(-(changes[k + 1][0] - start) // bar)   # ceil

    def locate(self, t: Fraction) -> tuple[int, float]:
        start, first, bar, ts = next(s for s in reversed(self.segments) if s[0] <= t)
        n, pos = divmod(t - start, bar)
        return first + int(n), float(ts.getAccentWeight(float(pos), forcePositionMatch=False))


class MidiBackend:
    name = "midi"
    suffixes = (".mid", ".midi")

    def n_movements(self, path: str | Path) -> int:
        return 1

    def read(self, path: str | Path, movement: int | None = None) -> ParsedPiece:
        if movement not in (None, 1):
            raise ValueError("MIDI files are read as a single movement")
        mf = m21midi.MidiFile()
        mf.open(str(path))
        mf.read()
        mf.close()
        tpq = mf.ticksPerQuarterNote

        open_notes: dict[tuple, deque] = defaultdict(deque)       # (track, ch, pitch) -> onsets
        notes: dict[tuple[int, int], list[tuple[Fraction, Fraction, int]]] = defaultdict(list)
        programs: set[tuple[int, int]] = set()
        track_name: dict[int, str] = {}
        inst_name: dict[int, str] = {}
        ts_changes: list[tuple[Fraction, str]] = []
        perc_notes = 0
        unclosed = 0
        end_time = Fraction(0)

        for ti, track in enumerate(mf.tracks):
            tick = 0
            for ev in track.events:
                if isinstance(ev, m21midi.DeltaTime):
                    tick += ev.time
                    continue
                t = Fraction(tick, tpq)
                end_time = max(end_time, t)
                if ev.type == META.SEQUENCE_TRACK_NAME:
                    track_name.setdefault(ti, _text(ev.data).strip())
                elif ev.type == META.INSTRUMENT_NAME:
                    inst_name.setdefault(ti, _text(ev.data).strip())
                elif ev.type == META.TIME_SIGNATURE:
                    d = ev.data
                    ts_changes.append((t, f"{d[0]}/{2 ** d[1]}"))
                elif ev.type == CVM.PROGRAM_CHANGE:
                    programs.add((ti, ev.channel))
                elif ev.isNoteOn() or ev.isNoteOff():
                    if ev.channel == PERCUSSION_CHANNEL:
                        perc_notes += ev.isNoteOn()
                        continue
                    key = (ti, ev.channel, ev.pitch)
                    if ev.isNoteOn():
                        open_notes[key].append(t)
                    elif open_notes[key]:
                        on = open_notes[key].popleft()           # FIFO pairing of re-struck notes
                        if t > on:
                            notes[(ti, ev.channel)].append((on, t - on, ev.pitch))
        unclosed = sum(len(q) for q in open_notes.values())

        warnings: list[str] = []
        if unclosed:
            warnings.append(f"{unclosed} note-on events without a matching note-off were dropped")
        excluded = [{"kind": "percussion_channel", "channel": PERCUSSION_CHANNEL, "notes": perc_notes}] if perc_notes else []

        mtr = _Meter(ts_changes)
        parts: list[DeclaredPart] = []
        events: list[NoteEvent] = []
        for (ti, ch) in sorted(notes):
            declared = (ti, ch) in programs or ti in inst_name
            pid = len(parts)
            name = inst_name.get(ti) or track_name.get(ti) or f"track {ti} channel {ch}"
            parts.append(DeclaredPart(part_id=pid, xml_id=f"t{ti}c{ch}", name=name,
                                      instrument_name=inst_name.get(ti, ""), n_staves=1,
                                      transposition=None, declared=declared))
            for on, dur, p in sorted(notes[(ti, ch)]):
                measure, strength = mtr.locate(on)
                events.append(NoteEvent(
                    id=-1, onset=float(on), duration=float(dur), pitch=p, part_id=pid,
                    voice_id="1", staff_id=1, measure=measure, beat_strength=strength,
                    is_grace=False, tie_group_id=-1, is_tied=False, part_inferred=not declared))
            if not declared:
                warnings.append(f"part {name!r} has no declared instrument: events marked part_inferred")
        events.sort(key=lambda e: (e.onset, e.part_id, e.pitch, e.duration))
        for k, e in enumerate(events):
            e.id = k
            e.tie_group_id = k
        return ParsedPiece(source=str(path), events=events, parts=parts,
                           total_duration=float(end_time), repeats_expanded=False,
                           excluded=excluded, warnings=warnings, source_format="midi")
