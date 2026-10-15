# Bridge, String Quartet No. 1, mvt 2, bars 60–75: original quartet against the control-S2 trio

**Files compared:**
- `0_source_quartet.musicxml`: Bridge's quartet, 236 notes.
- `4_arranger_masked_trio.musicxml`: control-S2, masked, melody-first decoding, checker-v5; 166 notes,
  0 violations.

The counts below follow every source note in these bars. A note is:
- **kept:** in its natural trio part (Vn1/Vn2 → violin, Va → viola, Vc → cello);
- **moved:** to another instrument at the same pitch;
- **re-voiced:** moved by an octave;
- **dropped.**

## The big picture: one voice per instrument, the original viola mostly lost

| Source part | Kept | Moved | Re-voiced (octave) | Dropped | What happens |
|---|---|---|---|---|---|
| **Violin 1** (melody) | 58 / 58 | — | — | **0** | Becomes the trio violin part, complete and as written, held notes included. |
| **Violin 2** | — | 70 (→ viola) | 1 (→ cello, bar 74) | 2 (bars 67, 70) | Becomes the trio **viola** part: the second-violin line at the same pitch, played by the viola. |
| **Viola** | 3 | 1 (→ cello, bar 73) | 6 (to cello or violin) | **55** | Almost all of Bridge's viola part is gone. A few notes survive by octave displacement. |
| **Cello** | 36 | — | — | 4 (bars 63, 65, 67, 68) | The bass line, essentially intact. |

**Main change:** four voices become three by **dropping the inner viola voice** and moving Violin 2
down into the viola. That is the trade the S2 rule makes: no double stops, at the cost of the
quartet's fourth line.

## Bar by bar

| Bar | Violin (from Vn1) | Viola (from Vn2) | Cello | What is lost or changed |
|---|---|---|---|---|
| 60 | held C5 (3½ beats) kept | Vn2's eighths F4 G4 G♯4 G4 F4 E♭4 | F2 kept | Bridge's viola eighths (G♯3 B♭3 C4 B♭3 G♯3 G3) dropped |
| 61 | C5–C5–B4–C5 kept | D4 C♯4 C4 B♭3 | kept | Viola's F♯3 F3 E3 dropped |
| 62 | kept | G♯3 C4 D4 | kept | Viola's descending line dropped |
| 63 | kept | B♭3 D4 B♭3 | low B♭2 dropped | Viola's G3 G♯3 G3 dropped; one cello note gone |
| 64 | kept | E♭4 D4 | kept | Viola's G♯3 dropped |
| 65 | kept | C4 D4 E♭4 F♯4 G4 | low E♭2 dropped | Viola's B♭3 re-voiced up into the **violin** (B♭4); others dropped |
| 66 | kept | B♭4 A4 A4 G4 | kept | Viola's D4 re-voiced **down two octaves into the cello** (D2); 5 viola notes dropped |
| 67 | kept | D4 F♯4 | D3 dropped | One Vn2 note dropped; most of the viola dropped |
| 68 | kept | G4 F♯4 | D3 dropped | Viola's C4 dropped |
| 69 | kept | E4 F♯4 G4 B♭4 B4 | kept | Viola's D4 re-voiced **up into the violin** (D5) |
| 70 | **held F♯5 kept for the whole bar** | D5 C♯5 C5 B4 | kept | Vn2's held F♯4 dropped; viola's F♯4 moved **to the cello** (F♯2); 4 viola notes dropped |
| 71 | kept | B4 B♭4 G♯4 F4 E♭4 | kept | Viola's chromatic descent (D4 C♯4 C4 B3 C4) dropped |
| 72 | kept | same pattern | kept | Same viola descent dropped |
| 73 | kept | C♯4 F4 D4 C4 | kept | One viola note moved to the cello (G♯3); 2 dropped |
| 74 | kept | D4 E♭4 F4 | kept | Vn2's B♭3 moved down into the cello |
| 75 | kept | Vn2's sixteenths G4 B♭4 F4 G♯4 … (12 notes) | kept | The viola's own sixteenths dropped, apart from two octave moves |

## What this means musically

- **The melody and the bass are fully intact.** That includes the held notes the earlier models
  lost: the C5 in bar 60 and the F♯5 in bar 70.
- **The viola part of the trio is Bridge's second violin,** moved down. It sits comfortably in the
  viola's middle range (B♭3–D5).
- **Bridge's own viola line is the casualty.** Its chromatic inner motion (bars 71–72) and its eighths
  under the melody (bars 60–62) are gone. These are the passages where the texture thins the most
  relative to the original.
- **A few viola notes are re-homed by octave:** up into the violin (bars 65 and 69) or down into
  the cello (bars 66, 70 and 73). This is the "cello assists" behaviour, used sparingly.
- **There are no double stops,** apart from the two short cello dyads, and every note is playable
  under checker-v5.

*Generated from the decoded records; the counts are source notes (236 notes in these bars: 58 + 73 + 65 + 40), so they sum to more than the 166 output notes where unisons were merged. This passage is one of the 5
review movements, so it is excluded from the confirmatory test.*
