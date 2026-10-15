"""Tie-chain merging on per-pitch instances.

music21's stripTies() mis-handles ties that live on only some pitches of a
chord, ties from a single note into a chord, and (after voicesToParts) chains
that cross voices -- it splits them into several notes. We therefore merge
ties ourselves, one pitch at a time, reading the tie off each chord member
rather than off the chord.

A chain is keyed on (stream, voice, midi). A 'stop'/'continue' joins the open
chain for its key if that chain ends exactly at its onset; failing that it
may join an open chain on the same stream and pitch in a *different* voice
(notated cross-voice ties). Nothing is ever merged without a tie marking, and
nothing is merged across a gap. Every irregularity is recorded as an anomaly
rather than silently fixed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

EPS = Fraction(1, 10_000)


@dataclass
class PitchInstance:
    """One pitch of one notated note or chord, before tie merging."""
    stream_idx: int          # index into score.parts (a Part or PartStaff)
    voice: str
    midi: int
    onset: Fraction          # absolute quarterLength
    duration: Fraction
    tie: str | None          # 'start' | 'continue' | 'stop' | None
    is_grace: bool
    measure: int
    src: object = field(default=None, repr=False)  # (music21 element, chord index)


@dataclass
class TieGroup:
    members: list[PitchInstance]
    group_id: int = -1

    @property
    def first(self) -> PitchInstance:
        return self.members[0]

    @property
    def onset(self) -> Fraction:
        return self.members[0].onset

    @property
    def end(self) -> Fraction:
        last = self.members[-1]
        return last.onset + last.duration

    @property
    def duration(self) -> Fraction:
        return sum((m.duration for m in self.members), Fraction(0))

    @property
    def is_tied(self) -> bool:
        return len(self.members) > 1


@dataclass
class TieAnomaly:
    kind: str                # orphan_stop | orphan_continue | unterminated | cross_voice
    stream_idx: int
    voice: str
    midi: int
    measure: int
    onset: Fraction


def merge_ties(instances: list[PitchInstance]) -> tuple[list[TieGroup], list[TieAnomaly]]:
    """Merge tie chains. Returns groups in (onset, stream, voice, notated) order,
    with group_id assigned in that order, plus a list of anomalies."""
    anomalies: list[TieAnomaly] = []
    groups: list[TieGroup] = []
    open_chains: dict[tuple, TieGroup] = {}

    def note(kind: str, inst: PitchInstance) -> None:
        anomalies.append(TieAnomaly(kind, inst.stream_idx, inst.voice, inst.midi,
                                    inst.measure, inst.onset))

    def close(key: tuple) -> None:
        g = open_chains.pop(key)
        note("unterminated", g.members[-1])

    def find_open(inst: PitchInstance) -> tuple | None:
        key = (inst.stream_idx, inst.voice, inst.midi)
        g = open_chains.get(key)
        if g is not None and abs(g.end - inst.onset) <= EPS:
            return key
        for k, g in open_chains.items():
            if k[0] == inst.stream_idx and k[2] == inst.midi and abs(g.end - inst.onset) <= EPS:
                return k
        return None

    # Tiebreak on input order (= notated order within a stream), so grace-note
    # runs sharing one onset keep their sequence and chord members stay in order.
    order = {id(inst): k for k, inst in enumerate(instances)}
    ordered = sorted(instances, key=lambda i: (i.onset, i.stream_idx, i.voice, order[id(i)]))
    for inst in ordered:
        if inst.is_grace:
            groups.append(TieGroup([inst]))
            continue

        key = (inst.stream_idx, inst.voice, inst.midi)
        # A chain on this key that ended before now can never be continued.
        stale = open_chains.get(key)
        if stale is not None and stale.end < inst.onset - EPS:
            close(key)

        if inst.tie in ("stop", "continue"):
            found = find_open(inst)
            if found is not None:
                g = open_chains.pop(found)
                if found[1] != inst.voice:
                    note("cross_voice", inst)
                g.members.append(inst)
                if inst.tie == "continue":
                    open_chains[key] = g
                continue
            note(f"orphan_{inst.tie}", inst)
            g = TieGroup([inst])
            groups.append(g)
            if inst.tie == "continue":
                open_chains[key] = g
            continue

        if key in open_chains:
            # Same pitch re-struck at/after the chain end without a stop mark.
            close(key)
        g = TieGroup([inst])
        groups.append(g)
        if inst.tie == "start":
            open_chains[key] = g

    for key in list(open_chains):
        close(key)

    groups.sort(key=lambda g: (g.onset, g.first.stream_idx, g.first.voice, order[id(g.first)]))
    for i, g in enumerate(groups):
        g.group_id = i
    return groups, anomalies
