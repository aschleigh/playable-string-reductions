Franck,_César__String_Quartet__sq26652775__m04

Bars are numbered along the repeat-expanded timeline (the numbering used in review so far). Original score bar numbers: 480=480, 481=481, 482=482, 483=483, 484=484, 485=485, 486=486, 487=487, 488=488, 489=489, 490=490, 491=491, 492=492, 493=493, 494=494, 495=495
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

Source string quartet: 100 notes; 0 red (hard violation); 0 orange only
Ou et al. trio, unconstrained: 150 notes; 96 red (hard violation); 0 orange only; 2 held notes shortened for display (3rd voice)
Ou et al. trio, masked (ou_band_masked): 125 notes; 0 red (hard violation); 45 orange only
Arranger (arranger-v2b) trio, unmasked: 100 notes; 49 red (hard violation); 0 orange only; 1 held notes shortened for display (3rd voice)
Arranger (arranger-v2b) trio, masked: 91 notes; 0 red (hard violation); 0 orange only
