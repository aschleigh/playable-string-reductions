# Floor triage: every violation on the real part assignments

Every floor violation, classified. Records: `floor_violations_annotated.jsonl` (`category`,
`xml_features`, source file, movement, measure). Reproduce: `python -m arrangement.validate &&
python -m arrangement.triage`; show one case: `python -m arrangement.triage --show N`.

## Parser bugs found and fixed (not in the counts below)

| Fix | What it was | Where | Test |
|---|---|---|---|
| Cue notes dropped | music21 ignores `<cue/>`; cues counted as played notes (31 range violations, e.g. a cello cue in Bridge No.2 Vn1) | `parse.drop_cue_notes` | `test_cue_notes_dropped_and_timing_kept` |
| music21 crash on hidden notations | `<notations print-object="no">` with a lone accidental-mark; 2 files / 8 movements missing | `parse._unhide_notations` | `test_hidden_notations_with_lone_accidental_mark_parse` |
| Harmonic touch points dropped | diamond touch-point notes in a chord with a stopped note were counted as sounding notes | `parse.collect_pitch_instances` | `test_artificial_harmonic_touch_note_dropped_lone_diamond_kept` |
| Shared unisons merged | same pitch, same onset, different voices of one part counted twice (743 notes corpus-wide) | `parse.merge_shared_unisons` | `test_shared_unison_across_voices_merged_same_voice_unison_kept` |

Verified correct, no fix needed: pitches under `<octave-shift>` (`test_octave_shift_keeps_true_pitch`).

## Remaining violations

| Category | Verdict | Total | range | chord_size | transition |
|---|---|---|---|---|---|
| `harmonic_notation` | KNOWN LIMITATION | 25 | 7 | 0 | 18 |
| `shared_unison` | FIXED IN PARSER | 0 | 0 | 0 | 0 |
| `range_above_placeholder` | THRESHOLD TOO STRICT | 0 | 0 | 0 | 0 |
| `transition_placeholder` | THRESHOLD TOO STRICT | 118 | 0 | 0 | 118 |
| `below_open_string` | UNRESOLVED | 10 | 10 | 0 | 0 |
| **total** | | **153** | | | |

- **`harmonic_notation`** (KNOWN LIMITATION): Harmonic passages the parser rule does not cover. The rule (PLAN.md decision 10) drops diamond touch points that share a chord with a stopped note. Left as written: lone diamonds (natural harmonics), natural harmonics notated at sounding pitch ("Flag."), and voices that print the resulting pitches.
- **`shared_unison`** (FIXED IN PARSER): The same pitch at the same onset in two voices of one part (PLAN.md decision 11). Any left would be overlaps that start at different onsets.
- **`range_above_placeholder`** (THRESHOLD TOO STRICT): Real top-register notes above the configured upper bound (UNSOURCED.md U1-U3).
- **`transition_placeholder`** (THRESHOLD TOO STRICT): Real leaps above the configured transition limit (UNSOURCED.md U0, U4, U5): string crossings, open strings, register jumps.
- **`below_open_string`** (UNRESOLVED): Below the lowest open string with no octave line, cue or harmonic in the XML. Possible scordatura or an engraving error; needs a look at the printed score.

Rules (`classify`): harmonic markup in the violation's measures (or "Flag."/"harm." text in
the 8 measures before) -> `harmonic_notation`; chord-size sets with a repeated pitch ->
`shared_unison`; remaining range above/below -> `range_above_placeholder` /
`below_open_string`; remaining transitions -> `transition_placeholder`.

Hand-inspected in the XML (2026-10-06, earlier config with the 24-semitone release-based cap):
- transition: Reger Op.121 i (Vc E♭4→D2 in a 16th), Grosse Fuge (Vn1 E♭6→A3), Delius iii (Vn1 A3→B5),
  Haydn Op.76/4 ii (E♭6→D♭4), Vieuxtemps Op.44 i (G3→E6), Mozart K.590 iv (D6→D♭4), Op.18/4 i
  (C7→open G3, 41 semitones). All are real writing, none a parse artifact.
- harmonic: Borodin No.1 i Vc "Flag. sul A" C♯6–E6; Koechlin No.1 ii Va (diamond F7 over C7); Janáček
  No.2 i Vn1 m252 and Schulhoff No.1 iv Vn1 m21 (diamond touch points plus a voice printing the resulting
  pitches).
- shared unison: Bridge No.2 i Vn1 m1 (4-note chord in voice 2 under a G5 held in voice 1); fixed in the parser.
- below open string: Zemlinsky No.2 i Vc B1 tremolo, no octave line or cue in the XML.

## Below the lowest open string (unresolved; needs the printed score)

- Zemlinsky,_Alexander_von__String_Quartet_No.2,_Op.15__sq10439083__m01 Violoncello m673: pitch 35 < 36
- Zemlinsky,_Alexander_von__String_Quartet_No.2,_Op.15__sq10439083__m01 Violoncello m674: pitch 35 < 36
- Zemlinsky,_Alexander_von__String_Quartet_No.2,_Op.15__sq10439083__m01 Violoncello m675: pitch 35 < 36
- Zemlinsky,_Alexander_von__String_Quartet_No.2,_Op.15__sq10439083__m01 Violoncello m676: pitch 35 < 36
- Zemlinsky,_Alexander_von__String_Quartet_No.2,_Op.15__sq10439083__m01 Violoncello m677: pitch 35 < 36
- Zemlinsky,_Alexander_von__String_Quartet_No.2,_Op.15__sq10439083__m01 Violoncello m678: pitch 35 < 36
- Zemlinsky,_Alexander_von__String_Quartet_No.2,_Op.15__sq10439083__m01 Violoncello m679: pitch 35 < 36
- Zemlinsky,_Alexander_von__String_Quartet_No.2,_Op.15__sq10439083__m01 Violoncello m680: pitch 35 < 36
- Zemlinsky,_Alexander_von__String_Quartet_No.2,_Op.15__sq10439083__m01 Violoncello m681: pitch 35 < 36
- Zemlinsky,_Alexander_von__String_Quartet_No.2,_Op.15__sq10439083__m01 Violoncello m682: pitch 35 < 36

Possible scordatura (C string down to B), which would keep the bound correct, or an engraving
error in the OpenScore edition.

## Known, not counted as bugs

- Janáček No.1: two declared "Violoncello" parts share one part id; the second (3 notes) merges into the cello.
- 18 movements: music21 could not expand the repeats; the notated surface is used (logged in the manifest).
