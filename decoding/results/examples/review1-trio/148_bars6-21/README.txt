Zemlinsky,_Alexander_von__String_Quartet_No.1,_Op.4__sq8944152__m02

Bars are numbered along the repeat-expanded timeline (the numbering used in review so far). Original score bar numbers: 6=6, 7=7, 8=8, 9=9, 10=10, 11=11, 12=12, 13=13, 14=14, 15=15, 16=15, 17=1, 18=2, 19=3, 20=4, 21=5
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
  S  overlap (monophonic)
  H  hand span
  D  same key twice
  L  hand leap

Source string quartet: 117 notes; 0 red (hard violation); 0 orange only
Ou et al. trio, unconstrained: 157 notes; 106 red (hard violation); 3 orange only; 4 held notes shortened for display (3rd voice); 220 unison duplicates drawn as one note
Ou et al. trio, masked (ou_band_masked): 126 notes; 0 red (hard violation); 28 orange only; 52 unison duplicates drawn as one note
Arranger (arranger-v2b) trio, unmasked: 115 notes; 15 red (hard violation); 1 orange only; 3 unison duplicates drawn as one note
Arranger (arranger-v2b) trio, masked: 112 notes; 0 red (hard violation); 0 orange only; 5 unison duplicates drawn as one note
Oracle (true reduction) under the checker-v4 mask, trio: 113 notes; 0 red (hard violation); 0 orange only; 12 unison duplicates drawn as one note
