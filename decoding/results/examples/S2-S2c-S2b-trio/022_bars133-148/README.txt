Bridge,_Frank__String_Quartet_No.1,_H.70__sq8938822__m02

Bars are numbered along the repeat-expanded timeline (the numbering used in review so far). Original score bar numbers: 133=133, 134=134, 135=135, 136=136, 137=137, 138=138, 139=139, 140=140, 141=141, 142=142, 143=143, 144=144, 145=145, 146=146, 147=147, 148=148
Readable MusicXML excerpts: the source quartet, Ou et al. unconstrained, and Ou et al.
masked, on the same bars, for performer review. Display only; nothing here feeds a result.

    python -m decoding.render_excerpts --idx 67 --start 1 --bars 16 [--masked-dir ou_band_masked]

Faithful to the source score:
  - time signature and key signature come from the original MusicXML
    (repeat-expanded exactly as headroom/sources.py does it); split bars at repeats are
    drawn as short bars under the running time signature, not as new meters;
  - onsets are exact: each beat is drawn on the coarsest grid (quarter, 8th, 16th, triplet,
    sextuplet, 32nd, 1/12) that keeps every onset in it exact, so no two notes that start
    at different times are drawn as a chord;
  - note ends are the only display change: an end within a 16th of the next onset in the
    part is drawn at that onset, otherwise at the nearest 16th or 8th-triplet point. Generated
    output often writes ends sloppily, and drawing them exactly would bury the rhythm in tuplets.
Readability: at most two voices per staff; voice-2 rests are hidden; a third overlapping
layer is drawn by shortening the held note to the new onset (counted in README.txt).

Colours (lyrics give the reason):
  red     hard violation under the current checker (letters, see LEGEND);
  orange  "3": three or more notes sounding at once in one string part, not a violation.

LEGEND
  R  out of range
  C  too many notes at once
  T  leap too fast
  M  chord does not fit the strings/hand
  B  three strings held
  X  shift too far too fast
  O  3+ notes not struck together
  W  3+-note chord too wide
  F  3+-note chords too fast
  V  held note under/over a new note
  K  re-strikes a sounding pitch
  Q  double stops too fast
  Y  3+-note chord too short before the next note
  S  overlap (monophonic)
  H  hand span
  D  same key twice
  L  hand leap

Source string quartet: 197 notes; 0 red (hard violation); 0 orange only
Ou et al. trio, unconstrained: 229 notes; 155 red (hard violation); 15 orange only; 1 held notes shortened for display (3rd voice); 144 unison duplicates drawn as one note
Ou et al. trio, masked (ou_band_masked): 180 notes; 0 red (hard violation); 26 orange only; 1 held notes shortened for display (3rd voice); 12 unison duplicates drawn as one note
Arranger (confirm5/control-S2b) trio, unmasked: 127 notes; 0 red (hard violation); 0 orange only
Arranger (confirm5/control-S2b) trio, masked: 127 notes; 0 red (hard violation); 0 orange only
S2 : Arranger (confirm/control-S2) trio, unmasked: 139 notes; 9 red (hard violation); 0 orange only
S2 : Arranger (confirm/control-S2) trio, masked: 137 notes; 0 red (hard violation); 3 orange only
S2c: Arranger (rl/control-S2c-review) trio, unmasked: 139 notes; 8 red (hard violation); 0 orange only
S2c: Arranger (rl/control-S2c-review) trio, masked: 136 notes; 0 red (hard violation); 0 orange only
