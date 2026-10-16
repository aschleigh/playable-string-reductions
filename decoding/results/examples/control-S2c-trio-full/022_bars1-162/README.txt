Bridge,_Frank__String_Quartet_No.1,_H.70__sq8938822__m02

Bars are numbered along the repeat-expanded timeline (the numbering used in review so far). Original score bar numbers: 1=1, 2=2, 3=3, 4=4, 5=5, 6=6, 7=7, 8=8, 9=9, 10=10, 11=11, 12=12, 13=13, 14=14, 15=15, 16=16, 17=17, 18=18, 19=19, 20=20, 21=21, 22=22, 23=23, 24=24, 25=25, 26=26, 27=27, 28=28, 29=29, 30=30, 31=31, 32=32, 33=33, 34=34, 35=35, 36=36, 37=37, 38=38, 39=39, 40=40, 41=41, 42=42, 43=43, 44=44, 45=45, 46=46, 47=47, 48=48, 49=49, 50=50, 51=51, 52=52, 53=53, 54=54, 55=55, 56=56, 57=57, 58=58, 59=59, 60=60, 61=61, 62=62, 63=63, 64=64, 65=65, 66=66, 67=67, 68=68, 69=69, 70=70, 71=71, 72=72, 73=73, 74=74, 75=75, 76=76, 77=77, 78=78, 79=79, 80=80, 81=81, 82=82, 83=83, 84=84, 85=85, 86=86, 87=87, 88=88, 89=89, 90=90, 91=91, 92=92, 93=93, 94=94, 95=95, 96=96, 97=97, 98=98, 99=99, 100=100, 101=101, 102=102, 103=103, 104=104, 105=105, 106=106, 107=107, 108=108, 109=109, 110=110, 111=111, 112=112, 113=113, 114=114, 115=115, 116=116, 117=117, 118=118, 119=119, 120=120, 121=121, 122=122, 123=123, 124=124, 125=125, 126=126, 127=127, 128=128, 129=129, 130=130, 131=131, 132=132, 133=133, 134=134, 135=135, 136=136, 137=137, 138=138, 139=139, 140=140, 141=141, 142=142, 143=143, 144=144, 145=145, 146=146, 147=147, 148=148, 149=149, 150=150, 151=151, 152=152, 153=153, 154=154, 155=155, 156=156, 157=157, 158=158, 159=159, 160=160, 161=161, 162=162
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

Source string quartet: 2234 notes; 19 red (hard violation); 6 orange only
Ou et al. trio, unconstrained: 3304 notes; 2192 red (hard violation); 89 orange only; 169 held notes shortened for display (3rd voice); 144 unison duplicates drawn as one note
Ou et al. trio, masked (ou_band_masked): 1684 notes; 0 red (hard violation); 136 orange only; 8 held notes shortened for display (3rd voice); 12 unison duplicates drawn as one note
Arranger (rl/control-S2c-review) trio, unmasked: 1676 notes; 59 red (hard violation); 1 orange only
Arranger (rl/control-S2c-review) trio, masked: 1648 notes; 0 red (hard violation); 0 orange only
