# Progress log

Append-only, newest at the bottom. One dated entry per action, result or incident. Each entry says
what was done or found, plus what went wrong or was changed. The related records are:
- results: BLOCK4.md (Block 4), MODEL.md (Block 3), DECODING.md (the gate);
- decisions: REVIEW.md (R-numbers);
- code changes: git log;
- raw job events: `model/logs/rl_chain.log`.

Backfilled on 2026-10-13 from the git history, the job logs and the session record; maintained live
from then on.

## 2026-10-12 (Block 3, model block)

- **11:05–11:24 checker-v4.** Three new string checks (double_onset, restrike, double_rate) from the
  user's MuseScore review; readable excerpt renderer; PDF/PNG previews. Frozen as tag `checker-v4`.
  DECODING.md A3 pre-registered.
- **11:34 Ou et al. + repair baseline** (DECODING.md A3).
- **11:44–12:04 Step 5 evaluation script, training-curve figure.** REVIEW R23–R27 (decisions under
  "proceed with all steps").
- **12:46–12:57 decode bugs fixed:**
  - windows over 384 notes are now shrunk;
  - exact tick resolution for expanded subdivisions;
  - a shard-merge bug;
  - GPU 0 out of memory, so decoding moved to GPU 1;
  - repeat/tremolo expansion made exact.

  All model records were regenerated.
- **13:00–16:40 arranger-v1** trained (30k steps, 47 min), then decoded and evaluated for trio and duo.
- **16:42 MODEL.md written** (Step 6). Masked arranger: D = 0, Note_i F1 0.741 trio / 0.608 duo; beats
  every playable Ou variant.
- **16:55 arranger excerpts** rendered for 5 review movements.
- **20:28–21:40 checker-v4 gates** for solo violin, solo flute and piano. Piano: outcome 1, unchanged.
- **21:15 Block 3 → 4 handoff** (BLOCK3_HANDOFF.md).

## 2026-10-12/13 (Block 4)

- **21:20–23:19 Steps 0–1, read-only diagnostics** (`model/diagnose.py`).
  - **Incidents:** the report loop was quadratic and stalled; I killed it and rewrote it as a sweep.
    A DROP-index bug in the intervention breakdown was found and fixed.
  - **Findings:**
    - the true intervention rate is 11.9% / 22.2%. MODEL.md's 24% / 51% came from a counter of failed
      options; corrected;
    - the oracle-under-mask ceiling for Note_i F1 is 0.87–0.90 trio and 0.60–0.66 duo;
    - 92–97% of double stops come from merging source parts;
    - the checker is not the compute bottleneck.
- **23:19 BLOCK4.md proposal** (Step 2). Approved 23:33; decision 1 delegated (R28).
- **23:41 arranger-v2 started** (source-part feature + class weights). Early training showed the
  feature makes the part head a lookup, so **arranger-v2b** (class weights only) was launched in
  parallel.
- **02:01 Step 3 done.** v2 copies the merged reduction and loses the melody (Vn1 retention 0.94 →
  0.80). v2b ≈ v1 with better repeat/tremolo recall. The user delegated ("always choose the
  recommended route"): **v2b is the starting point** (R29, R30).
- **02:00–02:42 Step 4: METRICS 1.4.0-draft** (`arrangement/eval/reduction.py`), all baselines re-run
  (6 regimes), detector ranges fixed before any RL run.
  - **Incident:** large record copies under `metrics-1.4.0/` were committed in `9ffb283` because a
    gitignore rule was too shallow. They are untracked now but remain in that commit's history; the
    user decides whether to rewrite it.
- **02:00–02:55 Step 5: GRPO implemented** (`model/grpo.py`). Five masking-ratio tests pass; a 3-step
  smoke run passes.
  - **Incidents:**
    - context precompute on 8 GPU processes was too slow (≈ 8 h projected). Killed and rerun on 34
      single-thread CPU processes (≈ 30 min).
    - `pgrep -f` matched my own shell and killed it; since then only explicit PIDs are used.
  - **Changes after the smoke run (R31):** the retention floor applies only to tiers with ≥ 8 notes;
    learning rate 1e-5.
- **03:22 RL launch 1 failed:** both learners ran out of GPU memory at the first update, and the chain
  wrongly went on to decode the untrained checkpoints. Fixed with micro-batched gradient accumulation
  (tested equal to a full batch) and a guard in the chain.
- **03:33 RL launch 2:** rl-C ran out of GPU memory again at step 2 (GPU 1 shared, ≈ 33 GB used by
  others) and was restarted on GPU 0. rl-A continued on GPU 1.
  - **Speed:** about 19 s per step, so step-400 snapshot evaluations were added (R32).
  - **Process fix:** I stopped the chain's main process to keep 6-shard decodes off a full GPU 1.
    Standalone waiter scripts with 2 decode shards replaced it.
- **03:44 control S trained** (supervised on feasible targets). **04:34 evaluated:** interventions
  −62% trio / −77% duo; fidelity near the masked ceiling; detectors narrowly out.
- **06:29–06:45 step-400 snapshots of rl-A and rl-C:** fidelity up, intervention rate flat. That is
  the pre-registered failure mode "better arranging without internalising the constraint". R33 queues
  rl-SA (RL from S).
- **08:38 rl-A (800 steps) evaluated:** plateaued. Best melody retention (≈ 0.99 trio / 0.97 duo);
  interventions not reduced. Not a success.
- **09:02 rl-C (800 steps) evaluated:** reward hack. It splits held notes into repeats (note ratio 1.07,
  duration ratio 0.82–0.89); the fixed detectors caught it. Not a success.
- **08:40 diagnosis (R34):** the masked ratio and KL put no gradient on infeasible probability, so the
  approved objective cannot reduce the intervention rate. rl-SA (from S) visibly un-learnt S's
  feasibility.
  - **rl-AZ** (feasible-mass term, DROP counted as feasible) learnt to drop 32–60% of notes; stopped at
    step 108 as a hack.
  - **rl-AZ2** (R34b: feasibility given the note is played; DROP excluded) launched 09:22.
- **10:51 rl-SA (RL from S, 400 steps) evaluated:** the best system on fidelity, with fewer
  interventions than v2b in both regimes. One criterion short in each regime.
- **10:53 rl-SAZ launched** (RL from S + the conditional feasibility term; R35).
- **11:49 rl-SA review excerpts** rendered and committed.
- **≈ 11:45 session restart.** All detached jobs survived. A shared-GPU user (Jon) asked about usage;
  answer drafted. Since then all new runs go on GPU 1.
- **12:11 rl-AZ2 trained** (400 steps); decode and evaluation running.
- **≈ 12:20 lockstep rollout engine implemented** (user approved). Each pass is one batched GPU forward
  over all rollouts; CPU workers keep only the checker and sampling.
  - New test: the engine reproduces sequential rollouts exactly (same seeds); all 7 GRPO tests pass.
  - **Bug found by the test:** the engine forced the network back to training mode; it now restores
    the previous mode.
  - Not used by any run yet.
- **12:35 lockstep engine benchmark** (3 steps, 16 windows × G = 8, 24 workers, GPU 1, while rl-SAZ is
  running):
  - rollout 3.9–5.2 s per step, against 11–28 s with the CPU-forward pool, so 3–6× faster;
  - update 1.7–1.9 s, so ≈ 6 s per step overall (≈ 600 steps per hour);
  - GPU forwards 0.5–1.3 s per step (8 batched forwards);
  - worker CPU ≈ 23 core-s per step (checker 16 s), so the workers are mostly idle.

  New runs use `--engine lockstep` (the default) on GPU 1.
- **13:06 rl-AZ2 evaluated: a reward hack.**
  - Interventions came down (0.048 trio / 0.160 duo), but 17% of notes were realised as repeats
    (v2b: 1.7%).
  - Note ratio 1.35 / 1.23, duration ratio 0.74 / 0.71, Note_i F1 −0.118 / −0.066, more double stops.
  - The detectors caught it. rl-C had a mild version (3–4% repeats).
- **13:15 R36 fix:** reward setting A2 (a note is kept only if held ≥ 75% of its written duration),
  plus detector proxies (note ratio, duration ratio, repeat share) logged at validation. Tested on a
  rollout. **rl-SA2Z launched** (A2 + feasibility from S, lockstep engine, GPU 1, 400 steps).
- **13:30 rl-AZ2 excerpts rendered for the user** (`decoding/results/examples/rl-AZ2-trio/`, Bridge
  bars 60–75 and Haydn 1–16). Bridge: 389 notes against the source's 236. Held bass and viola notes
  have become running repeated-eighth double stops, which confirms the R36 hack musically.
- **13:50 user review of Bridge 60–75 (two comments).**
  - **(1) "Everything is eighth notes":** confirmed to be the rl-AZ2 hack (349 of 389 notes are
    eighths). v2b, rl-A and rl-SA keep Bridge's duration mix, and the renderer does not quantise.
  - **(2) Chords with the same note twice:** a real defect. 283 of 3,326 rendered chords had a
    unison duplicate, from merging parts that double each other (Vn1/Vn2 unisons; Ou et al.'s output
    has them too). Training targets merge unisons, but the decoder never did.
    - Fixed for display now: the renderer draws same-part, same-onset, same-pitch notes as one note,
      the longest, and counts them in the README. All review excerpts are being re-rendered.
    - A decoder-level fix needs a versioned change and re-evaluation; the decision is with the user.
- **13:41–13:47 decode v2 (R37) implemented and tested** (unisons merged at commit; the probe undoes
  merges exactly; all GRPO, model and decode tests pass). Then:
  - rl-SAZ's in-flight decode, which had become mixed v1/v2, was stopped and set aside;
  - rl-SA2Z's waiter was stopped (its training continues);
  - `model/run_dv2.sh` was launched: keep the v1 outputs, re-decode v2b, re-score METRICS 1.4.0
    trio/duo, recompute detector ranges, then re-decode and re-evaluate S, rl-A, rl-SA, rl-C, rl-SAZ
    and rl-SA2Z (6 shards, GPU 1).
- **13:59 v2b re-decoded under decode v2** (masked trio). 14,688 unisons merged (2.8% of notes);
  interventions 0.1135 → 0.1053; drops 6.4% → 5.5%. A unison pair counted as a double stop for the
  checker, so merging also removes some forced fallbacks. Each decode set takes 5–7 min with 6 shards
  on GPU 1.
- **14:25 detector ranges under decode v2.**
  - Trio note ratio [0.989, 1.012] → [0.970, 1.000]; the rest changes by ≤ 0.01.
  - The old range was set partly by unison duplicates in v2b's output. Runs that failed only on trio
    note ratio (0.978–0.981) need re-checking.
  - Both sets of ranges will be reported.
- **14:48 control S re-evaluated under decode v2** (C); the A evaluation and rl-A, rl-SA, rl-C,
  rl-SAZ and rl-SA2Z follow.
- **16:58 decode-v2 re-run complete** (`model/run_dv2.sh`): control S, rl-A, rl-C, rl-SA, rl-SAZ and
  rl-SA2Z all re-decoded and re-evaluated. Results in the BLOCK4.md section "Results under decode v2".
  - **No system meets all 5 criteria.** Closest:
    - rl-SA2Z trio: fails only the double-stop reduction (+0.002);
    - rl-SA trio: detectors narrowly;
    - rl-SA duo: double stops flat.
  - RL from S beats S on fidelity. rl-SA2Z keeps S's trio feasibility (0.034 interventions) but not
    S's Note_i F1.
  - Duo: RL gives back feasibility, with residual repeat-splitting (3.4–5.0%).
- **17:35** rendering rl-SA2Z excerpts (Bridge, Haydn) for review.
- **17:45 rl-SA2Z excerpts rendered** (`decoding/results/examples/rl-SA2Z-trio/`).
  - Bridge 60–75: 241 notes (source 236); the held cello and viola notes are back; 0 violations.
  - Unison-duplicate chords: 1 left on display, against 51 for rl-AZ2 and many for v1-decoded systems.
    The remainder are figurated, not plain, notes, which decode v2 does not merge.
- **17:49 launched rl-SA3Z (A3: λ_DS = 3) and rl-SA3D9Z (A3D9: λ_DS = 3, 90% duration rule)**, both
  from S with the feasibility term, concurrently on GPU 1 (lockstep), each followed by a decode-v2
  decode and evaluation (R38).
- **19:45 rl-SA3Z and rl-SA3D9Z evaluated.**
  - λ_DS = 3 cuts double stops (trio −0.030, duo −0.038, CIs clear) and interventions (0.021 / 0.038),
    but drops notes: the note-ratio and harmony detectors fail; duo harmony is non-inferiority-failed.
  - The 90% duration rule had no effect.
- **20:15 tuning-on-the-evaluation-set issue flagged (R39).** R33–R38 relabelled as development
  results; remedy proposed (select on the dev split, freeze, one confirmatory run). Waiting for the
  user's decision; no new runs started.
- **20:35 rl-SA3Z excerpts rendered and shown to the user** (`decoding/results/examples/rl-SA3Z-trio/`),
  with the Bridge source and the rl-SA2Z Haydn.
  - **Finding:** in Bridge bars 60 and 70, Vn1's held melody note (D5, F♯5) is dropped in both
    rl-SA2Z and rl-SA3Z, and the violin keeps Vn2's moving line.
  - **Cause:** in a merged part, held melody plus moving inner line breaks double_onset; the reward
    counts notes, not duration (1 top note < 5 inner eighths × 0.25).
  - **Proposed:** weight kept notes by duration as well as tier. Pending the user's decision on R39.
- **20:55 user review of Bridge 60–75** (six points). Actions:
  - (1) **Strings played as piano in MuseScore:** the MusicXML had part names but no instrument
    definitions. The renderer now writes Violin, Viola and Violoncello (MIDI programs 41–43); all
    excerpts are being re-rendered.
  - (2) **Keep the held melody note**, possibly an octave lower or in the cello: points to a reward
    change.
  - (3) The "held note under a new note" rule needed explaining.
  - (4)/(6) Still too many double stops; the melody in bars 70–72 is lost; the arrangement should be
    more inventive.
  - (5) **The orange triple stop in bar 75 is unplayable:** G3 + E♭4 + E♭5, which the checker
    passes. That is a checker gap.
- **21:10 reward M implemented and tested** (R40). The selection rule was pre-registered in BLOCK4.md.
  Launched rl-SM2Z (λ = 2) and rl-SM3Z (λ = 3), from S with the feasibility term: dev-only, no
  evaluation-set decode. Asked the user what makes the bar 75 chord unplayable, since it already
  meets "adjacent strings, ≤ extended position".
- **23:42 rl-SM2Z and rl-SM3Z stepping.** Step-0 dev values (= control S), the reference for the R40
  selection rule:

  | | Trio | Duo |
  |---|---|---|
  | fidelity_M | 0.910 | 0.789 |
  | top retention M | 0.896 | 0.857 |
  | note ratio | 0.962 | 0.832 |
  | mean-duration ratio | 0.919 | 0.848 |
  | repeat share | 0.013 | 0.014 |
  | interventions | 0.037 | 0.039 |

  **Eligibility thresholds** (0.95 × S):
  - trio: note ratio ≥ 0.914, duration ratio ≥ 0.873, repeat share ≤ 0.026;
  - duo: note ratio ≥ 0.790, duration ratio ≥ 0.806, repeat share ≤ 0.028.
- **00:46–01:00 rl-SM2Z and rl-SM3Z finished.** The final dev validation had not been logged (a
  bug, now fixed); it was recomputed from the checkpoints.
  - **R40 rule:** neither is eligible (duo repeat share 0.031 > 0.028), so no confirmatory run.
  - **Finding:** long melody notes are still lost (top retention 0.98 by count, 0.91 by duration),
    caused by confidence-ordered committing.
  - **Proposed:** melody-first commit order (decode v3), awaiting the user (R41).
- **00:55 decode v3 (melody-first) implemented** (R42; `--melody-first`): within each pass, notes are
  committed by source voice tier (top, bass, inner), then by confidence. With the flag off, decode
  is unchanged.
  - On one dev movement: 1,335 notes against 1,365, and 172 interventions against 146. Melody now
    wins conflicts.
  - Dev comparison running (`model/dev_decode_compare.py`: 61 dev movements × trio/duo × v2b, S,
    rl-SM2Z × decode v2/v3).
- **The user answered on bar 75:** the triple stop was unplayable for both reasons, (a) the hand
  stretch beyond normal position and (b) too short before fast notes. Checker v5 to implement.
- **01:15 checker-v5 implemented** (R43).
  - Violin/viola triple-stop stretch ≤ 4; new triple_recover ≥ 1 quarter.
  - Batch, incremental and growing agree: 145 new tests; the full suite passes, with two expected
    expectation updates (a v3 test now also sees triple_recover; U19 added to UNSOURCED.md).
  - METRICS 1.5.0-draft. Tagged `checker-v5`.
- **01:23 DECODING.md A4 written, then `decoding/run_v5.sh` launched** (GPU 1 only): masked Ou et al.
  regenerated under checker-v5 for trio, duo and solo violin, plus gates, the repair baseline and the
  headroom re-measurement. The v4 outputs are kept as `*_checker-v4`. Expected to take several hours
  (overnight).
- **01:20 decode-v3 dev comparison rerunning under checker-v5.** The first attempt crashed: I changed
  the checker while it ran, so its workers had mismatched code.
- **01:55 decode-v3 dev comparison done** (BLOCK4.md R42 section): melody-first lifts
  duration-weighted melody retention for v2b and rl-SM2Z (rl-SM2Z: trio 0.928 → 0.950, duo 0.862 →
  0.920) at a small cost in drops and double stops; control S does not benefit.
- **02:05 Bridge and Haydn rendered with rl-SM2Z + melody-first**
  (`decoding/results/examples/rl-SM2Z-melodyfirst-trio/`): the bar 70 F♯5 is held; the bar 60 C5 is
  still re-struck as eighths. My earlier description of bar 60's note as D5 was wrong; it is C5.
- **2026-10-15 user: double stops still everywhere; fix it in training (supervised target or
  reward), not at inference.**
  - Measured double stops per 100 notes. Real parts: Vn1 2.3, Vn2 6.1, Va 5.1, Vc 2.5. v2b trio
    output: violin 23.9, viola 15.6, cello 5.3.
  - Built the S2 target rule (R44), tested on 12 movements, building for the full train split.
  - Rendered the S2 target for Bridge and Haydn (`decoding/results/examples/s2-target-trio/`):
    violin a single melody line with the held notes kept, viola takes Vn2, cello helps; about 70% of
    notes kept.
  - Discussed with the user: double stops are a symptom of preservation-only objectives; proposed an
    idiomaticity term (learned part model or corpus-statistic matching).
- **00:43 user approved the S2 style** (R45). Added the cello rule (moved notes ≤ G4, else an octave
  down; U20). Launched `model/run_s2.sh`: S2 targets for the full train split, fine-tune control-S2,
  then dev evaluation of double stops per part and fidelity.
- **2026-10-14 05:34–11:25 checker-v5 baseline chain finished** (reported late, at 00:47 on 10-15).
  - Masked Ou et al. regenerated for trio, duo and solo violin.
  - **Gates:** all outcome 2/3; trio Δ Note_i F1 +0.090, Δ harmony +0.098. Recorded in DECODING.md
    (A4 result).
  - The repair baseline and the headroom re-measurement are also done.
- **02:00 control-S2 trained and evaluated** (dev split, melody-first):
  - double stops per 100 notes: trio violin 0.6, viola 4.4, cello 2.2; duo 0.2 / 1.9 (real parts
    2.3–6.1);
  - melody retention by duration 0.988 trio / 0.948 duo; interventions 1.5% / 1.2%;
  - drops 18% / 41%.
- **02:10 Bridge and Haydn rendered from control-S2,** trio and duo, masked and unmasked
  (`decoding/results/examples/control-S2-{trio,duo}/`).
- **11:20 confirmatory decode chain launched** (`model/run_confirm.sh`): control-S2, v2b and S, melody-first, checker-v5, trio/duo, plain/masked, 6 shards on GPU 1.
- **11:24 PROJECT_GUIDE.md written:** the project map (pipeline, vocabulary, directory structure, how
  the components attach, every `decoding/results` folder, the history of the last few days, files
  written, next steps).
- **11:22** `control-S2-trio/022_bars60-75/DIFFERENCES.md`: bar-by-bar comparison of Bridge's quartet
  with the control-S2 trio.
- **12:15 detached watcher `model/run_week_summary.sh`** (survives session restarts): waits for the confirmatory evaluation, then builds the week-summary table and figure; the session-bound watcher was stopped.
- **12:25 GitHub export prepared** (`tools_export_github.sh`): private repo, fresh history, relevant tracked files only (no data, checkpoints, logs, study/ PRIVATE files or legacy code). Untracked 240 large record and metrics copies from the local repo (tracked size 890 MB → 138 MB). Waiting for the user to create the empty repo on GitHub.
- **12:30 pushed to GitHub:** private `aschleigh/playable-string-reductions`, 1 commit authored by the user (no co-author line, at the user's request), 1,322 files (96 MB). WEEK_SUMMARY.md will follow as a second commit.
- **12:47 confirmatory test evaluated** (R47): criterion B holds in the duo; the trio fails on viola
  double stops only (5.2 against 5.1); criterion A fails in both, as anticipated.
- **13:06** summary table and figure built by the detached watcher.
- **14:57** session resumed after a restart; the results were read and recorded.
- **15:10 WEEK_SUMMARY.md written:** annotated results table, double-stop figure, confirmatory verdict, Bridge images and bar-by-bar analysis, RL lessons, the idiomatic-term proposal, presentation plan and caveats.
- **15:15 GitHub repo updated:** second commit (authored by the user) adding WEEK_SUMMARY.md, the figure, the confirmatory results and updated documents.
- **16:40 GitHub authorship changed (user request):** the user asked for all past and current GitHub changes to be attributed to `ashleyzhang04@gmail.com` (aschleigh account). Both commits in `playable-string-reductions` were rewritten (author and committer `Ashley Zhang <ashleyzhang04@gmail.com>`; file contents identical, empty tree diff), then force-pushed (`fcd0e47` → `25da432`). The export repo's local git config and `tools_export_github.sh` now use the gmail address.
- **16:35 viola double-stop analysis (S2 targets, first 200 train movements):** viola 6.11 double stops per 100 notes; 98.7% are supported by the source (simultaneous in the quartet), 68% involve inner voices only, 53% follow another viola double stop within 1 quarter. This feeds the stricter viola rule (pending).
- **17:05 S2b rules implemented** in `model/targets_s2.py`: U20 cello moved-note limit D5 (74, was G4); U21 viola spacing rule (`--viola-gap`, `--tag`). Calibration on 200 train movements: gap 0.5/1/2/4 -> viola 5.88/5.28/4.45/3.68 per 100 (S2 6.11); melody/bass retention unchanged; D5 leaves cello double stops at 4.54 (S2 4.64). **Gap 2 chosen** (target ~4.5). Calibration pickles deleted.
- **17:10 BLOCK5.md written** (proposal; six decisions for the user). UNSOURCED U14 (confirmed), U20 (D5), U21 (new); REVIEW R48–R50.
- **17:12 full S2b build started** (CPU only, 16 workers; `model/results/rl/logs/targets_s2b.log`).
- **17:45 S2b targets built** (`model/results/rl/targets_s2b__train.pkl`, 476 movements, trio and duo; S2 file untouched). Trio: top dropped 0.4%, bass 0.4%, inner 17.6%; the viola rule refused 30,311 options (those notes took their next option). Duo: unaffected by U21 (no viola); D5 limit only.
- **17:50 GitHub updated:** commit `2a1488b` (author Ashley Zhang <ashleyzhang04@gmail.com>, no trailer): BLOCK5.md, S2b rules, records.
- **18:29 Block 5 approved (R51, all six recommended options).** control-S2b chain started detached (`model/run_s2b.sh`: train on GPU 1, 3,000 steps; then dev double-stop stats and dev compare, 16 CPU workers). `train_s.py` gained `--targets s2b`. The S2 double-stop stats were copied to `double_stop_stats_mf_S2.json` before being overwritten.
- **18:40 Step 0:** fresh-data count: 0 unused OpenScore movements; 21 unused ABC Beethoven movements (< 60) -> confirmation on the 145 with the second-use caveat (R52).
- **18:45 P (model/idiom.py) training on GPU 1** (6,000 steps, 3.28M parameters, 1,904 train parts, 1.58M events). Dev decode dump `model/dev_outputs.py` running (v2b, control-S2, rl-AZ2; 16 CPU workers). Gate script `model/idiom_gate.py` and RL settings MI05/MI10 (`model/grpo.py`, `window_term` in `model/idiom.py`) written (R52).
- **18:47 P trained** (dev log-lik −3.91/event, train −3.75) and calibrated (`model/results/idiom/P/calib.json`). RL smoke run MI05 (2 steps) passed; found the inner retention floor fights the S2 targets (−1.1 per window) -> floors top/bass only for MI05/MI10 (R53). Stage A (`model/run_block5_a.sh`: dev outputs control-S2b, gate) and stage B (`model/run_block5_b.sh`: base decision, gate check, contexts, RL MI05/MI10, dev selection) are queued detached.
- **19:12 confirm5_eval smoke-tested** on R46 records (passes; reproduces R47). It printed eval-set idiomatic z for Block 4 systems: disclosed in R54. control-S2b trained (18:55); dev double-stop stats done (19:10); dev compare running. Stage C (`model/run_block5_c.sh`) queued.
- **19:50 Gate FAIL** (R55): restrike16 hack above real in all slots; real vs S2b AUC 0.56 (violin); S2b vs v2b 0.49 (trio cello). Diagnosed (repetition is predictable). No RL with P; stage B stops before RL; stage C will confirm the base against criterion B. P v2 proposed in BLOCK5.md.
- **20:31 Block 5 confirmatory test done** (R56): base control-S2b (Step 1c replace=True). Duo criterion B holds; trio fails item 1 on cello CI upper (1.9 [1.4, 2.7] vs 2.5); viola fixed (2.5, was 5.2). Found R47 under-reported the trio failure (cello also exceeded): corrected in BLOCK4.md, WEEK_SUMMARY.md, REVIEW.md.
- **20:40 GitHub updated:** commit `7ce457b` (Ashley Zhang <ashleyzhang04@gmail.com>, no trailer).
- **20:50 P parked by the user (R57).**
- **21:30 control-S2b review excerpts rendered** for the user (review movements only): `decoding/results/examples/control-S2b-{trio,duo}/` (Bridge 60–75, Haydn 1–16; nearly identical to S2) and `decoding/results/examples/S2-vs-S2b-{trio,duo}/` (Franck 042 bars 649–664: viola DS 26 -> 1; Bridge 133–148: viola 17 -> 8; Haydn 61–76: viola 6 -> 2, 37 cello notes above G4 at written pitch; duo Haydn 61–76). Haydn bars 71–86 could not be rendered (source bar 77 has a duration too short for MusicXML).
- **(2026-10-16) R58: viola middle setting.** S2c targets (viola gap 1 quarter, 5.28 per 100 in calibration) building; `model/run_s2c.sh` queued (train control-S2c on GPU 1, dev double stops S2/S2b/S2c, dev compare, review-only decodes via new `model/decode.py --only-review`). No confirmatory test (third use needs the user).
- **02:10 control-S2c trained and checked on dev** (R58): trio viola 3.40 per 100 (S2 4.44, S2b 2.31), melody/interventions unchanged. Review decodes done; adding S2c to the comparison excerpts.
- **02:40 S2c added to the comparison excerpts** (`6_control-S2c_masked_*`). Viola double stops per excerpt, S2 / S2c / S2b: Franck 649–664 26 / 11 / 1; Bridge 133–148 17 / 17 / 8; Haydn 61–76 6 / 3 / 2.
- **(2026-10-16) R59: control-S2c adopted by the user** after listening. Rendering control-S2c-{trio,duo} (Bridge 60–75, Haydn 1–16, the three comparison windows); comparison folders renamed S2-S2c-S2b-{trio,duo}.
- **(2026-10-16) R60:** cello double-stop bar = composers' own writing (criterion B′: output vs same-movement source parts). Post hoc on R56: all parts hold (trio cello 1.92 vs 3.21). **R61:** MusicXML only. Full Bridge trio (all 162 bars) rendered: `decoding/results/examples/control-S2c-trio-full/022_bars1-162/`; control-S2c-{trio,duo} folders done.
- **(2026-10-16) BLOCK6.md written** (proposal; R62): solo piano and solo flute; six decisions for the user.
- **(2026-10-16) Block 6 approved (R63, all recommended).** Starting Step 1a: OpenScore Lieder.
- **(2026-10-16) Step 2 code:** `model/targets_fk.py` (F flute, K piano) written and smoke-tested; flute weaving removed as redundant (R64). Lieder measurement running (`arrangement/calibrate_piano.py`, 16 workers).
- **(2026-10-16) Lieder measured** (1,425 piano parts). Sounding-set spans are pedal/held notes (3.5% above 14 held-out; dev max 43); struck-set spans 99.9th pct 16.7 -> recommended checker-v6: piano hand rules on struck sets, span 16 (R65). Re-measuring leaps at span 16.
- **(2026-10-16) checker-v6 (R66):** piano hand rules on struck notes; span 16; leap 18 + 32/quarter (Lieder-calibrated). 1,325 tests pass. Tagged.
- **(2026-10-16 14:00) F/K targets built** (piano keeps 99.8%; flute top line). **control-J joint training started** (`model/run_block6_j.sh`, GPU 1, 88,904 windows, from control-S2c; then dev flute/piano + strings). Breath rule limited by vocabulary (R67). Ou piano masked regenerating under checker-v6 (`decoding/run_v6.sh`).
- **(2026-10-16) control-J trained** (3,000 steps). Loss by 1,000-step block 0.21 / 0.185 / 0.184: flat, so no second 3,000 (BLOCK6 Step 3 rule). Dev evaluation running. Renderer extended for piano (grand-staff display split at C4) and solo flute.
- **15:02 control-J dev:** fallback triggered (trio viola 3.40 -> 4.38) -> separate models (R68): control-FK training (GPU 1). Piano dev excellent; flute below the top line on melody (0.892 vs 0.949), vocabulary limit (R69).
- **(2026-10-16 15:35) control-FK** (flute + piano only, R68) trained and dev-checked: flute melody 0.900 (top line 0.949), breaths 1.7 per 32 quarters, median longest run 106 quarters; piano melody 0.987, bass 0.989, inner 0.956, harmony 0.996, interventions 1.8%.
- **(2026-10-16 16:00) checker-v6 piano baseline done:** Ou et al. piano masked regenerated (150/150); gate verdict unchanged ("outcome 1: blocking is enough").
- **(2026-10-17) listening step started** (`model/run_block6_listen.sh`): control-FK review decodes (piano, solo flute) -> MusicXML: Bridge 60–75, Haydn 1–16, full Bridge movement.
- **(2026-10-17) R70 CUT realisation implemented;** F3 targets (dev melody 0.921 vs top line 0.927); control-FK2 chain launched (`model/run_block6_fk2.sh`: targets, train n_real 6 on GPU 1, dev). decode.py piano/flute reference bug fixed; control-FK listening chain relaunched.
- **(2026-10-17 23:55) control-FK2 trained and dev-checked** (R71): flute melody 0.940 (top line 0.949), breaths 3.6/32q, median longest run 39.5q; piano unchanged. control-FK listening excerpts rendered; control-FK2 excerpts rendering (`model/run_block6_listen2.sh`).
- **(2026-10-18 00:05) control-FK2 listening excerpts rendered** (MusicXML): `decoding/results/examples/control-FK2-{piano,solo_flute}[-full]/`. Awaiting the user's listening verdict before the confirmatory test (BLOCK6 Step 6).
- **(2026-10-24) BLOCK6 Amendment A written** (proposal, R72): RL stage for flute/piano from control-FK2, P v2 for strings, criterion E. Six decisions for the user; nothing run.
- **(2026-10-24) Amendment A approved (R73).** Starting A1: GRPO for piano / solo_flute.
- **(2026-10-24) A1 code done:** `model/grpo.py` (solo_flute/piano, n_real 6 with CUT, settings F05/F10/K), `tests/test_grpo_fk.py` 5/5 and `tests/test_grpo.py` 7/7 pass (R74). 2-step smoke run on 3 movements in progress.
- **(2026-10-24) A1 smoke run passed** (3 train movements, 2 steps each, F05 flute and K piano, GPU 1): contexts, rollouts, A2 reward terms, update and melody-first validation all run. Rollout ~1-3 s per 16 trajectories; dev validation ~45 s per 2 movements. Smoke outputs deleted. Estimate per full run (32 windows x 8, 1,000 steps, 12+4 CPU workers): 5-8 hours.
- **(2026-10-27) BLOCK7.md written** (RL with an aligned reward; proposal, R75).
- **(2026-10-27) Block 7 approved (R76).** Step 0: fresh confirmation set.
- **(2026-10-27) Step 0 done (R77):** fresh set of 31 movements (`model/data/fresh_sources.jsonl`; Beethoven ABC 21, Mendelssohn Op. 44/3, Pleyel 6); KernScores down. `model/decode.py --source-records` added.
- **(2026-10-27) Record collision fixed (R78):** Block 7 entries renumbered R75–R77; Block 6 Amendment A (another session, 2026-10-24, R72–R74) found uncommitted in model/grpo.py, tests/test_grpo_fk.py, BLOCK6.md; left untouched pending the user.
- **(2026-10-27) R79: plans merged; reward R8 implemented** in model/grpo.py (note cost, melody line integrity, melody-first rollouts, B' for strings, dev targets on the fly). Amendment A code committed after 12/12 tests. Reward gate (`model/reward_gate.py`) smoke test running.
- **(2026-10-27) R8 chain launched** (`model/run_rl8.sh`): full reward gate -> contexts -> six RL runs on GPU 1 -> dev decodes. Smoke gate (3 dev movements): every hack below base; inner_dump closest (strings 1.127 vs 1.137).
- **(2026-10-29) Status check:** R8 reward gate FAILED on 2026-10-27 13:30 (duo inner_dump: base outscores the hack in only 62.8% of dev windows, both λ settings; every other hack/regime passes). Chain stopped as designed; no contexts, no RL runs. Failure was not reported to the user until now. Awaiting a decision on the reward fix.
- **(2026-10-29) R80: R8.1 implemented** (reloc credit ±12 only; inner line-integrity 0.2); duo gate re-running.
- **(2026-10-29) R8.1 duo gate FAILED again** (inner_dump 60.3%, ties 72.5%). Diagnosis (all 61 dev): 1972/2735 duo windows keep no inner note, so the hack changes nothing there (ties); in the rest the new inner line term let the hack win (moving a whole inner voice 2 octaves removes its register jumps). Without that term, base beats the hack in 720/763 changed windows (94.4%; 18 hack wins, 25 ties; 96.0% with ties half). Awaiting the user's decision on dropping the inner line term and scoring the gate on changed windows only.
- **(2026-10-29) R81:** inner line term dropped; gate scored on changed windows; chain relaunched (full gate first).
- **(2026-10-29 10:30) Status:** full R8.1 gate PASSED 01:52 (all hacks, all regimes; duo inner_dump 0.960 on 763 changed windows). Contexts built. rl8-F05 done 06:57 (1000 steps, train R 0.948->0.993); rl8-F10 at step 936/1000 (R 0.862->0.919). Remaining: K1, K3, S2, S4, then dev decodes.
- **(2026-10-30 01:30) R8 chain finished (2026-10-29 23:35).** All six runs and dev decodes done.
  - **Strings (vs control-S2c, dev):** rl8-S2 / rl8-S4 both pass the Block 7 Step 4 eligibility checks. Melody (count) trio 0.991 -> 0.998, duo 0.962 -> 0.985 / 0.984; interventions trio 1.5% -> 0.7%, duo 1.3% -> 1.1% / 1.0%; trio viola DS 3.40 -> 1.92 / 1.24; no repeats; note and duration ratios within limits. The primary selection measure is a tie (0.9532 / 0.9548); the harmony tie-break is not in the dev outputs and still has to be computed.
  - **Flute/piano (Amendment A3 vs control-FK2):** no run is eligible. Flute F05/F10: interventions 1.2% / 0.9% (base 0.6%), longest run 42.5 / 40.5 (base 39.5). Piano K1/K3: interventions 1.8% -> 0.7% / 0.6%, but melody 0.981 / 0.971 (limit 0.982), bass 0.977 / 0.966, inner 0.958 -> 0.88 / 0.85. So control-FK2 stays, and the RL result is negative for flute/piano.
- **(2026-10-30) User listening verdict, control-FK2:** flute "looks pretty good"; piano "quite thick", "too many >octave chords", should split between the hands, left hand too often in treble clef.
- **(2026-10-30) Renderer fix (display only, `decoding/render_excerpts.py`):** the piano left-hand staff had no clef entry and was drawn in treble clef; now bass clef. The grand-staff split was at middle C; now each struck chord is split between the hands as the checker can play it (≤ 5 notes a hand, smallest larger span, ties nearest middle C). Re-rendered `control-FK2-piano[-full]`. Full Bridge movement: staff chords over an octave 145 → 67; struck chords that need a hand over an octave under any split: 56 of 1,027 onsets (allowed by checker-v6 span 16). The masked piano keeps 2,202 of 2,234 source notes (98.6%): the thickness is real, from the targets, not the display. No checker or target change made; awaiting the user.
- **(2026-11-03) User:** re-rendered piano "looks better"; readability issue: greyed-out rests and stray 8th notes "under" the score (the hidden voice-2 rests and second-voice notes). Not yet fixed. Nothing running; waiting on the user for the piano fix, the flute confirmatory test and the string RL render.
- **(2026-11-03) R82, user: "go on all".** Started: flute criterion D (control-FK2, `model/run_block6_c2.sh`, GPU 1); review decodes for rl8-S2 / rl8-S4 (done 08:34); string RL excerpts rendering (`decoding/results/examples/rl8-vs-S2c-{trio,duo}[-full]`); Lieder hand-leap refit at span 12 for checker-v7 (CPU, 12 workers); K2 piano targets coded (`model/targets_fk.py --piano-k2`). Piano renderer: one voice per hand, no hidden rests.
- **(2026-11-03) Flute criterion D HOLDS** (control-FK2 vs Ou et al. masked, 145 evaluation movements; `model/results/confirm6/CONFIRM6_solo_flute.md`): melody 0.555 → 0.943 (Δ +0.388 [+0.371, +0.406]); harmony +0.217 [+0.207, +0.227]; 0 hard violations masked; unmasked violations per 100 notes 280 → 2.3; interventions 0.5%; vs the top line −0.006 [−0.007, −0.005] (limit −0.01). All five items hold.
- **(2026-11-03) String RL excerpts rendered** (`decoding/results/examples/rl8-vs-S2c-{trio,duo}`, `rl8-vs-S2c-trio-full`; files 4 control-S2c, 5 rl8-S2, 6 rl8-S4, masked). Full Bridge trio: ~265 of 1,767 notes differ from control-S2c; drawn chord onsets (violin, viola, cello) S2c 0/33/43, rl8-S2 17/13/43, rl8-S4 9/7/36.
- **(2026-11-03) checker-v7 committed and tagged (13b29f0):** piano hand span 12; Lieder hand-leap refit at span 12: 24 + 48 per quarter (held-out fail share 1.2e-5); UNSOURCED U8/U12/U13 updated; test_checker_v2 hand-leap case moved to the new envelope; suite 1324 passed before that fix (the one failure was that test). Chain launched: `model/run_block6_fk3.sh` (K2 targets, control-FK3, dev, review decodes), then `decoding/run_v7.sh` (Ou et al. piano re-masked under checker-v7, GPU 1, ~2 h).
- **(2026-11-03) Block 7 Step 4.2 tie-break** (`model/results/rl/dev_harmony_rl8.json`, dev, masked melody-first): harmony trio / duo / mean: control-S2c 0.950 / 0.871 / 0.910; rl8-S2 0.946 / 0.873 / 0.910; rl8-S4 0.944 / 0.872 / 0.908. The protocol picks **rl8-S2** (selection measure tied, 0.9532 vs 0.9548; harmony higher). The user still chooses by ear (R82).
- **(2026-11-03) K2 piano targets** (train): 10.6% of notes dropped as inner doublings, 0.5% as inner notes that do not fit; about 89% of source notes kept (K: about 99%). control-FK3 training (GPU 1, ~25 min).
- **(2026-11-03 11:40) control-FK3 done** (dev, checker-v7): piano note ratio 0.950 (FK2) -> 0.868, inner 0.921 -> 0.723, melody 0.987 -> 0.989, bass 0.989 -> 0.988, harmony 0.994 -> 0.979, interventions 3.0% -> 1.5%. Flute unchanged. Excerpts: `decoding/results/examples/control-FK3-piano{,-full}` (full Bridge masked 2,202 -> 2,036 notes). Ou et al. piano re-masked under checker-v7 (150/150, 11:37); gate running. Waiting on the user: string RL pick, FK3 piano listen.
- **(2026-11-10) Status:** nothing has run since 2026-11-03 11:40. Ou et al. piano re-masked under checker-v7 (150/150); gate verdict as under v6 ("blocking is enough"). Waiting on the user: string pick (control-S2c / rl8-S2 / rl8-S4) and the control-FK3 piano listen. The other python processes on the machine belong to another user.
- **(2026-11-10) Human-reference demo (user request, demonstration only):** Clementi's 1803 piano setting of Haydn's Emperor hymn (Op. 42 Lesson XXVII; Mutopia, CC BY-SA 4.0) aligned to Op. 76/3 II bars 1-20 and compared with control-FK2 / control-FK3 (masked, melody-first, checker-v7). `decoding/results/examples/human-ref-haydn-emperor/`. Clementi passes checker-v7 with 0 violations (max hand span 12). Clementi 298 notes, 3.3 per onset, keeps 92% melody / 90% bass / 56% inner of the quartet; FK2 292 notes, 98/100/99%; FK3 255 notes, 98/100/72%. Agreement with Clementi (FK2 / FK3): exact pitch 74% / 65% of his notes; pitch class 95% / 93%; harmony 0.95 / 0.94. Caveat: the movement is in the training split.
- **(2026-11-10) Pianist feedback on the Clementi comparison (via the user):** thickness is fine; LH top should be at least a third below the RH bottom (else move the note to the RH if it makes a good chord, else LH note down an octave); chords up to an octave at any speed, 9ths/10ths need set-up time; chord/single alternation helps; inner fingers should not cluster toward the pinky (toward the thumb if needed). Measured: every struck chord in Clementi / FK2 / FK3 (Emperor bars 1-20) has a split with hands >= 3 semitones apart; the overlaps come from held notes (checker-v6/v7 hand rules see struck notes only) and the display split. Sounding LH/RH closer than a minor third: Clementi 4/81 moments, FK2 4/99, FK3 0/98; full Bridge movement FK2 164/943 (17%), FK3 119/940 (13%). Proposal to the user (checker-v8, fuller targets K3); nothing changed.
- **(2026-11-10) R83 approved (checker-v8, fuller piano targets).** Lieder v8 measurement running (`arrangement/calibrate_piano.py measure8`, staves = hands, 12 workers).
- **(2026-11-10) checker-v8 (R83) implemented:** piano hand rule at each onset: a contiguous split of the sounding notes with the hands >= 3 semitones apart, <= 5 struck notes and <= 16 struck span per hand; > 12 needs >= 0.25 quarters since the part's previous onset; hand_leap back to v6 (18 + 32 at span 16). Lieder with staves (`results/calibration_piano/piano_v8.json`, 1,424 songs): staves closer than a minor third 3.6% of sounding moments; set-up before 13-16 chords: dev 1st pct 0.25 q, no longer than before narrow chords. `tests/test_piano_v8.py` (incremental == batch == growing, both gap bases, removal; unit cases); full suite 1448 passed. New `arrangement/piano_hands.py` (hands consistent in time, keeping held notes; soft measures). With it the Bridge display gap problems go 164/943 -> 0 (FK2): most of the pianist's overlap was the display split. Renderer uses it. K3 targets coded (`targets_fk.py --piano-k3`).
