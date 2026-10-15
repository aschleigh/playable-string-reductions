# NOTES: deferred ideas (not built; out of scope for the hard tier)

- **Adjacent strings for double stops.** A double/triple stop needs its notes on
  adjacent strings, with at most one note per string. Pitch-to-string feasibility
  is a hard constraint we do not check. `max_chord: 4` only bounds the count.
  Tested 2026-10-06 (dev split): the tuning-only form (sorted notes >= open
  strings) flags 0.003 per 100 notes on the true parts, 0.04 for naive and 0.13
  for continuity. That is a weak signal. The strong form needs per-string upper
  limits and left-hand stretch across strings, both unsourced.
- **The hard tier does not discriminate for strings.** With envelopes wide enough
  for real quartet writing, naive trips only chord size (results/validation/).
  The constraints that separate playable from unplayable string writing (stretch,
  shifting, string choice) are fingering-level, close to difficulty modelling.
- **Sustained vs. rolled chords.** On strings, 3- and 4-note chords are playable only
  short or broken. Telling them apart needs duration/articulation-dependent rules,
  which edges into difficulty scoring. Not checked.
- **Tempo-aware transitions.** Transition time is in quarter notes (approved
  default), so the same leap is equally legal at Grave and Presto. A tempo-aware
  version needs reliable tempo extraction (many scores have text-only tempi).
- **Transition is non-monotone** (a later commit can clear an earlier transition
  violation). For constrained decoding: a per-commit mask can block a commit
  whose violation a later note would have resolved. Whether masking should use
  only the monotone checks is a decoding-design question for later.
- **Chord-size counting** gives one violation per distinct over-full sounding set
  (one per onset). A long over-full stretch with many entries therefore counts
  several times. `notes_implicated_per_100` is reported alongside the raw
  violation rate for this reason.
- **Continuity assigner has no memory decay.** A part's "previous pitch" persists
  across rests of any length. A time-decayed or phrase-aware version is a possible
  stronger baseline, but it edges toward voice-separation modelling.
- **Continuity crossing mode.** "forbid" (no part crossing within an onset slice)
  is the configured default because the crossing-allowed matching makes the
  continuity weight useless on the dev split (results/assigner/README.md).
  Real quartets do cross parts, so forbid caps achievable accuracy.
- **music21 MIDI export writes transposing parts at written pitch.** Any MIDI
  produced through music21 from transposing scores must be converted with
  toSoundingPitch() first (found while testing the MIDI backend).
