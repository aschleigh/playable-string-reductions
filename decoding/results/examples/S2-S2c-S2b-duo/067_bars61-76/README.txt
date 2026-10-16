Haydn,_Joseph__String_Quartet_in_D_minor,_Hob.III76,_Op.76_No.2__sq12772795__m02

Bars are numbered along the repeat-expanded timeline (the numbering used in review so far). Original score bar numbers: 61=41, 62=42, 63=43, 64=44, 65=45, 66=46, 67=47, 68=48, 69=49, 70=50, 71=51, 72=52, 73=53, 74=54, 75=55, 76=56
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

Source string quartet: 416 notes; 0 red (hard violation); 3 orange only
Ou et al. duo, unconstrained: 396 notes; 258 red (hard violation); 6 orange only; 7 held notes shortened for display (3rd voice); 17 unison duplicates drawn as one note
Ou et al. duo, masked (ou_band_masked): 183 notes; 0 red (hard violation); 40 orange only; 8 unison duplicates drawn as one note
Arranger (confirm5/control-S2b) duo, unmasked: 300 notes; 5 red (hard violation); 0 orange only
Arranger (confirm5/control-S2b) duo, masked: 297 notes; 0 red (hard violation); 0 orange only
S2 : Arranger (confirm/control-S2) duo, unmasked: 304 notes; 9 red (hard violation); 0 orange only
S2 : Arranger (confirm/control-S2) duo, masked: 295 notes; 0 red (hard violation); 0 orange only
S2c: Arranger (rl/control-S2c-review) duo, unmasked: 298 notes; 5 red (hard violation); 0 orange only
S2c: Arranger (rl/control-S2c-review) duo, masked: 295 notes; 0 red (hard violation); 0 orange only
