Haydn,_Joseph__String_Quartet_in_D_minor,_Hob.III76,_Op.76_No.2__sq12772795__m02

Bars are numbered along the repeat-expanded timeline (the numbering used in review so far). Original score bar numbers: 1=0, 2=1, 3=2, 4=3, 5=4, 6=0, 7=1, 8=2, 9=3, 10=4, 11=4, 12=5, 13=6, 14=7, 15=8, 16=9
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

Source string quartet: 260 notes; 0 red (hard violation); 0 orange only
Ou et al. duo, unconstrained: 259 notes; 181 red (hard violation); 6 orange only; 7 held notes shortened for display (3rd voice); 17 unison duplicates drawn as one note
Ou et al. duo, masked (ou_band_masked): 159 notes; 0 red (hard violation); 30 orange only; 1 held notes shortened for display (3rd voice); 52 unison duplicates drawn as one note
Arranger (rl/rl-A) duo, unmasked: 238 notes; 81 red (hard violation); 0 orange only
Arranger (rl/rl-A) duo, masked: 216 notes; 0 red (hard violation); 9 orange only
Oracle (true reduction) under the checker-v4 mask, duo: 226 notes; 0 red (hard violation); 12 orange only; 1 unison duplicates drawn as one note
