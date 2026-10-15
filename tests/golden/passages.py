"""Hand-constructed golden passages for the hard-tier checker.

Each FAIL passage breaks exactly one check, and `expected` lists every
violation it must produce (check, part, note_ids). Each CLEAN passage must
produce none. Notes are (onset, duration, pitch, part[, grace]) in quarter
notes / sounding MIDI; part -1 = unassigned. Note id = list position.

Test ensemble (tests/golden/test_ensemble.yaml): 0 flute, 1 violin, 2 piano.
Quartet passages use the real config: 0 Vn1, 1 Vn2, 2 Va, 3 Vc.
"""
from __future__ import annotations

from dataclasses import dataclass, field

FL, VN, PF = 0, 1, 2
V1, V2, VA, VC = 0, 1, 2, 3


@dataclass
class Passage:
    name: str
    ensemble: str                  # "test" or "quartet"
    notes: list[tuple]
    expected: list[tuple] = field(default_factory=list)   # (check, part, note_ids)


CLEAN = [
    Passage("flute_stepwise_scale", "test",
            [(0, 1, 72, FL), (1, 1, 74, FL), (2, 1, 76, FL), (3, 1, 77, FL), (4, 2, 79, FL)]),
    Passage("violin_double_stops_and_short_triple", "test",
            # held D4 under a moving upper line, then a 3-note chord
            [(0, 2, 62, VN), (0, 1, 69, VN), (1, 1, 71, VN), (2, 0.5, 55, VN), (2, 0.5, 62, VN), (2, 0.5, 69, VN)]),
    Passage("violin_four_note_chord_is_allowed", "test",
            [(0, 1, 55, VN), (0, 1, 62, VN), (0, 1, 69, VN), (0, 1, 76, VN)]),
    Passage("piano_two_hand_chord_within_reach", "test",
            [(0, 1, x, PF) for x in (48, 52, 55, 72, 76, 79)]),
    Passage("violin_big_leap_after_rest", "test",
            # leap 45 after a 2-quarter rest: allowed 24 + 12*2 = 48
            [(0, 1, 55, VN), (3, 1, 100, VN)]),
    Passage("flute_grace_into_note", "test",
            [(0, 1, 72, FL), (1, 0, 74, FL, True), (1, 1, 72, FL)]),
    Passage("unassigned_notes_are_invisible", "test",
            # would be range, simultaneity, chord-size, transition violations if assigned
            [(0, 1, 72, FL), (0, 4, 30, -1), (0.5, 1, 74, -1), (1, 1, 100, -1), (1, 1, 74, FL)]),
    Passage("transition_measured_from_release_not_onset", "test",
            # a long-held low note then a high note right at its release: the
            # nearest predecessor is the upper line note released at the same time
            [(0, 2, 55, VN), (0, 1, 76, VN), (1, 1, 79, VN), (2, 1, 81, VN)]),
    Passage("quartet_chorale", "quartet",
            [(0, 1, 72, V1), (0, 1, 67, V2), (0, 1, 60, VA), (0, 1, 48, VC),
             (1, 1, 74, V1), (1, 1, 67, V2), (1, 1, 62, VA), (1, 1, 43, VC)]),
    Passage("quartet_open_strings_are_in_range", "quartet",
            [(0, 1, 55, V1), (0, 1, 55, V2), (0, 1, 48, VA), (0, 1, 36, VC)]),
]

FAIL = [
    Passage("simultaneity_flute_overlap", "test",
            [(0, 2, 72, FL), (1, 1, 74, FL)],
            [("simultaneity", FL, (0, 1))]),
    Passage("simultaneity_flute_unison_doubling", "test",
            [(0, 1, 72, FL), (0, 1, 72, FL)],
            [("simultaneity", FL, (0, 1))]),
    Passage("range_violin_below_open_g", "test",
            [(0, 1, 62, VN), (1, 1, 54, VN)],
            [("range", VN, (1,))]),
    Passage("range_flute_above_top", "test",
            [(0, 1, 96, FL), (1, 1, 97, FL)],
            [("range", FL, (1,))]),
    Passage("range_quartet_cello_below_c2", "quartet",
            [(0, 1, 72, V1), (0, 1, 67, V2), (0, 1, 60, VA), (0, 1, 35, VC)],
            [("range", VC, (3,))]),
    Passage("chord_size_violin_five_notes", "test",
            [(0, 1, x, VN) for x in (55, 62, 69, 76, 83)],
            [("chord_size", VN, (0, 1, 2, 3, 4))]),
    Passage("chord_size_from_held_notes", "test",
            # four held notes, a fifth enters at beat 2: one violation, at beat 2
            [(0, 4, 55, VN), (0, 4, 62, VN), (0, 4, 69, VN), (0, 4, 76, VN), (2, 1, 79, VN)],
            [("chord_size", VN, (0, 1, 2, 3, 4))]),
    Passage("hand_span_piano_wide_chord", "test",
            # best split {36,50}|{64,78}: both hands span 14 > 12
            [(0, 1, x, PF) for x in (36, 50, 64, 78)],
            [("hand_span", PF, (0, 1, 2, 3))]),
    Passage("transition_violin_legato_leap", "test",
            # leap 45 with no gap: allowed 24
            [(0, 1, 55, VN), (1, 1, 100, VN)],
            [("transition", VN, (0, 1))]),
    Passage("transition_flute_grace_leap", "test",
            # grace note 30 semitones above the previous note, no gap
            [(0, 1, 62, FL), (1, 0, 92, FL, True), (1, 1, 90, FL)],
            [("transition", FL, (0, 1))]),
]
