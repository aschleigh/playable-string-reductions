Haydn,_Joseph__String_Quartet_in_D_minor,_Hob.III76,_Op.76_No.2__sq12772795__m02

MuseScore files: Ou et al. trio, unconstrained vs gate-masked, on one excerpt.

    python -m decoding.render_masked --idx 67 --bars 1-16

Red = hard-tier violation (current checker, checker-v3, for every file; computed on the whole movement); lyric R/C/T (v1), M multistop, B bow, X shift (v2), O not struck together, W 3+-note stretch, F chords too fast (v3).
Orange, lyric "3" = three or more distinct pitches sounding at once in one string part.
That is NOT by itself a hard-tier rule; it marks where three strings sound at once.
Blue, lyric "~" = display rounding: onsets are drawn on a 16th grid, so notes that start at
different times in the data (e.g. 32nds) can be drawn as one chord. They are not a chord.
Display only; nothing here feeds a result.

Ou et al. trio, unconstrained: 398 notes in excerpt; 333 red (hard violation); 6 orange only (>= 3-note sounding chord, not a hard rule); 73 blue (drawn merged by 16th rounding, not simultaneous); 2 held notes shortened for display (>4 voices)
Ou et al. trio, masked by checker-v2: 253 notes in excerpt; 58 red (hard violation); 12 orange only (>= 3-note sounding chord, not a hard rule); 30 blue (drawn merged by 16th rounding, not simultaneous)
Ou et al. trio, masked by checker-v3: 219 notes in excerpt; 0 red (hard violation); 6 orange only (>= 3-note sounding chord, not a hard rule); 34 blue (drawn merged by 16th rounding, not simultaneous)
