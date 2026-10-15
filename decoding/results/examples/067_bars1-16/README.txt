Haydn,_Joseph__String_Quartet_in_D_minor,_Hob.III76,_Op.76_No.2__sq12772795__m02

MuseScore files: Ou et al. trio, unconstrained vs gate-masked, on one excerpt.

    python -m decoding.render_masked --idx 67 --bars 1-16

Red = hard-tier violation (frozen checker, computed on the whole movement); lyric R/C/T.
Orange, lyric "3" = three or more distinct pitches sounding at once in one string part.
That is NOT a hard-tier rule (the checker allows up to 4); it marks sustained multi-stops
a player would have to break or cannot sustain. Display only; nothing here feeds a result.

Ou et al. trio, unconstrained: 398 notes in excerpt; 150 red (hard violation); 165 orange only (>= 3-note sounding chord, not a hard rule); 2 held notes shortened for display (>4 voices)
Ou et al. trio, gate-masked: 302 notes in excerpt; 0 red (hard violation); 179 orange only (>= 3-note sounding chord, not a hard rule)
