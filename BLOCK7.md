# Block 7 brief: RL with a reward built from what Blocks 4–6 taught us (PROPOSAL, awaiting approval)

Status: **approved 2026-10-27 (R76: all six as recommended).** Originally a **proposal, 2026-10-27.** Nothing has been run or changed. Every weight, threshold and criterion below is a
proposal. Research-consequence decisions are marked **[U]**.

State before this block: control-S2c (strings, R59) and control-FK2 (flute, piano, R71) are supervised systems; Block 4's
GRPO runs are development results only (R39). The user: "I want to try a better rl reward function given what we know now."

**Goal.** Show whether RL, given a reward that matches the user's stated priorities and is hard to game, improves on the
best supervised system, starting from it. The question for the thesis: *does RL add anything once supervision on playable
targets has done its work, and if so, where?*

---

## What went wrong in Block 4, and what changes

| Block 4 problem | Evidence | Block 7 change |
|---|---|---|
| **The reward asked for the wrong thing:** keep as many source notes as possible | criterion A against B; RL pushed toward more notes, so toward more double stops; the user wants melody first, occasional double stops, inner voices droppable | **reward = the user's priorities:** duration-weighted melody and bass; inner voices weighted low with no floor; double stops judged against the composers' own rate (criterion B′) |
| **The reward was gameable** | rl-C, rl-AZ2 re-struck held notes as repeats (R36); patched twice (A2, M) | credit only for notes **held** as written (≥ 75%); a **cost per output note**, so splitting notes never pays; a **reward gate** against a hack suite before any run (Step 2) |
| **Rollouts decoded differently from evaluation** | rollouts used confidence order; evaluation used melody-first (R42), which alone fixed most held-melody losses | **melody-first rollouts** (decode v3 inside the RL engine) |
| **A weak starting point** | RL started from v2b / control S, far from playable targets | start from **control-S2c**, with the KL anchor to it |
| **Tuned on the evaluation set** | R39 | dev split only; **a fresh confirmation set** (Step 0) |
| **The mask hides playability from the reward** | every rollout is playable, so only interventions signal it | keep the feasibility term (interventions); playability itself is not rewarded (it is guaranteed) |

Not changed: GRPO (the algorithm optimised what it was given), the checker (checker-v6; strings as v5), the window
layout (16 quarters + 8 context).

---

## Step 0: state check and a fresh confirmation set **[U]**

- Checker-v6, METRICS 1.5.0-draft; control-S2c and control-FK2 present.
- **Fresh data (recommended):** the KernScores Humdrum editions of the Haydn and Mozart quartets (public, and readable by
  music21), keeping only movements whose work is **not** in OpenScore (checked by composer, opus and number). Target at
  least 60 movements, the same filtering as the split. Fallbacks, in order: the music21 corpus quartets not in OpenScore
  (about 20) plus the 21 ABC Beethoven movements; else the 145 evaluation movements as a third use, caveat stated.
- These movements are not looked at (no decoding, no listening) until Step 5.

## Step 1: the reward R7 (per rollout window; strings: trio and duo)

`R7 = F_mel + 0.25·H − λ_DS·DS_excess − c·N_extra + G − feas` (`feas` as in Block 4; KL to control-S2c in the loss)

- **F_mel (fidelity, the user's priorities):** duration-weighted retention with tier weights **top 1.0, bass 0.8, inner
  0.1**. A note counts if it is in the output at the same onset (within a 16th) and held at least 75% of its written
  length, at its pitch (full credit) or an octave or two away, in any part (0.8 credit).
- **H (harmony):** beat-chroma cosine against the source, weight 0.25, as before.
- **DS_excess (criterion B′ inside the window):** for each output part, its double-stop moments minus the double-stop
  moments of the source parts that feed it (trio violin ← Vn1+Vn2, viola ← Va, cello ← Vc; duo cello ← Va+Vc), floored at
  0, divided by the window's source notes. Double stops the composers wrote cost nothing; extra ones cost λ_DS.
  **[U]** λ_DS ∈ {2, 4}.
- **N_extra (anti-splitting):** output notes beyond the source notes they come from (repeats, tremolo and arpeggio
  splits), per source note, cost c = 0.05. Re-striking a held note into repeats now loses credit *and* pays.
- **G (floors, top and bass only):** −5 × the shortfall below 0.9 × control-S2c's dev retention, per tier, as R53.
- **No term for "idiomatic":** P stays parked (R57).

## Step 2: the reward gate (before any RL run)

R7 must rank, on the dev split (mean per window):
**the S2c targets ≥ control-S2c outputs > every hack**, where the hacks are:
1. v2b's outputs (double-stop heavy);
2. control-S2c with every held note re-struck as 8ths (the rl-AZ2 hack);
3. melody only (everything else dropped);
4. everything kept in place (no reduction; masked, so playable but double-stop heavy);
5. every inner note moved an octave into an empty register.

**Pass:** each hack's mean R7 is below control-S2c's with a paired-window AUC ≥ 0.90. **If it fails,** the reward is
redesigned on dev before any run, and the gate re-runs with a hack I have not used for design.

## Step 3: RL runs

- GRPO, from control-S2c, KL β 0.02 to control-S2c, feasibility term 1.0, **melody-first rollouts**, 400 steps, group 8,
  16 windows per step, GPU 1 only, ≤ 16 CPU workers.
- **Two runs [U]:** λ_DS = 2 and λ_DS = 4 (c = 0.05). About 2–3 hours each.
- **Stop rules during training (dev, every 100 steps):** repeat/tremolo share above control-S2c's + 0.01, note ratio
  outside ±5% of control-S2c's, mean duration ratio below control-S2c's − 0.02, or any string part's double stops above
  its composer rate: stop the run and report it.

## Step 4: selection (dev only)

1. **Eligible:** no stop rule fired; criterion B′ holds on dev for every part; interventions ≤ control-S2c's + 0.005.
2. **Choose** the higher mean (trio, duo) dev duration-weighted melody + bass retention. A difference < 0.005 is a tie,
   broken by the higher dev harmony.
3. **Listening:** you hear the Bridge 60–75, Haydn 1–16 and one full movement (review movements, MusicXML) from the
   selected run against control-S2c before the confirmatory test.
4. **If neither is eligible,** report it; no confirmatory test; control-S2c stays.

## Step 5: one confirmatory test (criterion E, pre-registered with this brief)

Selected RL run against **control-S2c**, both masked, melody-first, per regime (trio, duo), on the fresh set (Step 0),
paired movement bootstrap:
1. **Better where S2c paid:** Δ duration-weighted melody + bass retention CI lower bound > 0, **or** Δ harmony CI lower
   bound > 0;
2. **Non-inferior:** Δ melody retention (count) CI lower > −0.01; Δ harmony CI lower > −0.01; Δ interventions CI upper
   < +0.005;
3. **Criterion B′** holds for the RL run (every part's double stops at or below the composers' rate in the same movements);
4. **No rhythm rewriting:** repeat share ≤ control-S2c's + 0.01; Δ mean duration ratio CI lower > −0.02.

Also reported, not criteria: Block 4's rl-SM2Z re-decoded melody-first; AMT (secondary, trio, with the copy-dilution caveat).

**Reading:** holds → RL with an aligned reward adds to supervision (the original thesis claim, on a strong base). Fails on
1 only → RL could not improve a well-supervised system (a clean negative result). Fails on 2–4 → RL traded the user's
priorities for reward; report what it gamed.

## Step 6 (optional, after Step 5): RL where supervision cannot help **[U]**

The duo infilling (Block 5 Step 6, deferred): a new action, "add back one dropped source chord tone here", chosen by RL
with reward = harmony gain − note cost, within the ≤ 2% budget and source pitch classes. No rule writes a single correct
target for it, so it is a natural RL task. A separate brief when Steps 1–5 are done.

## Compute

GPU 1 only (GPU 0 is Jon's); ≤ 16 CPU workers. Fresh-set download and parsing: half a day. Reward code and gate: half a
day. Two runs: 5–6 hours. Dev, listening and confirmatory decodes: 4 hours.

## Decisions requested

1. **Fresh confirmation set** from KernScores Haydn and Mozart, works not in OpenScore (recommended), with the fallbacks.
2. **Reward R7** as written: tier weights 1.0 / 0.8 / 0.1, held-note credit, B′ double-stop term, note cost 0.05, top/bass
   floors.
3. **The reward gate** with the five hacks and AUC ≥ 0.90.
4. **Two runs,** λ_DS = 2 and 4, from control-S2c with melody-first rollouts.
5. **Criterion E** as written (against control-S2c, on the fresh set).
6. **Step 6** (infilling with RL) later, as its own brief.
