**⚠ EVERY NUMBER IN THIS DIRECTORY IS INVENTED. These are mock figures drawn before any model exists. They are not results and must never be cited, reused, or shown as results.**

# Mock primary figures (Step 6)

These figures exist to test the plan, not to illustrate it. They draw each outcome in the project's interpretation table, so we can check *before* running anything whether the planned experiments can tell the outcomes apart. The analysis is in [DISTINGUISHABILITY.md](DISTINGUISHABILITY.md).

| File | What it shows |
|---|---|
| `FABRICATED_outcome1_blocking_matches_training.png` | Outcome 1: blocking matches training on fidelity (and quality) |
| `FABRICATED_outcome2_training_beats_blocking.png` | Outcome 2: training beats blocking at the same playability |
| `FABRICATED_outcome3_training_beats_blocking_blocking_degrades.png` | Outcome 3: training beats blocking, and blocking degrades as constraints tighten. At one tightness level it looks the same as outcome 2. |
| `FABRICATED_outcome4_neither_improves.png` | Outcome 4: neither improves on the unconstrained model |
| `FABRICATED_tightness_gap.png` | Second figure: trio → duo → solo violin, comparing outcome 3 (gap widens) with outcome 2 (gap constant), plus the within-level gap |

To regenerate: `MPLCONFIGDIR=<scratch dir> .venv/bin/python mock_figures/make_mock_figures.py`. The script is deterministic, and all its numbers are hard-coded.

## Conventions (keep these when the real figure is drawn)

- **x axis:** hard violations per 100 notes for the **worst single check type**, D from DECISION.md. Lower is more playable, and 0 is at the left. It's one check type, never a sum across checks. The real figure should also be drawn once per check type. Keep in mind that D's check type can change along a curve.
- **y axis:** Note_i F1 (Ou et al., Appendix C.1), the paper's headline metric. The other fidelity metrics each get the same plot. Playability and fidelity are never combined into one score.
- **Marks:**
  - unconstrained model: one point, which is the same as the trained model at reward weight w = 0;
  - constrained decoding (blocking): one point at exactly x = 0;
  - trained model: a curve of reward-weight sweep points, each labelled with its weight;
  - rule-based continuity assigner: a gray reference point.
- **Error bars:** invented 95% CIs. On the real figure they are score-bootstrap CIs, as in DECISION.md.
- **Unconstrained x positions:** loosely on the scale of HEADROOM.md's Ou et al. D values (trio about 5, duo about 8, solo violin about 16). Every fidelity value is made up.
