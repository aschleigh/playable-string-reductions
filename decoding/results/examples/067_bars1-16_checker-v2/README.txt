Haydn,_Joseph__String_Quartet_in_D_minor,_Hob.III76,_Op.76_No.2__sq12772795__m02

MuseScore files: Ou et al. trio, unconstrained vs gate-masked, on one excerpt.

    python -m decoding.render_masked --idx 67 --bars 1-16

Red = hard-tier violation (checker-v2, also for the checker-v1-masked file; computed on the whole movement); lyric R/C/T (v1), M multistop, B bow, X shift (v2).
Orange, lyric "3" = three or more distinct pitches sounding at once in one string part.
That is NOT a hard-tier rule (the checker allows up to 4); it marks sustained multi-stops
a player would have to break or cannot sustain. Display only; nothing here feeds a result.

Ou et al. trio, unconstrained: 398 notes in excerpt; 270 red (hard violation); 64 orange only (>= 3-note sounding chord, not a hard rule); 2 held notes shortened for display (>4 voices)
Ou et al. trio, masked by checker-v1: 302 notes in excerpt; 134 red (hard violation); 56 orange only (>= 3-note sounding chord, not a hard rule)
Ou et al. trio, masked by checker-v2: 253 notes in excerpt; 0 red (hard violation); 57 orange only (>= 3-note sounding chord, not a hard rule)
