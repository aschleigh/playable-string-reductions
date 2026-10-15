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
