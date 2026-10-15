# rl-SA (setting A) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | rl-SA | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9317 | 0.9810 | +0.0493 [+0.0403, +0.0592] |
| unneeded_ds_per_source_note | 0.1526 | 0.1475 | -0.0051 [-0.0083, -0.0020] |
| retention_top | 0.9419 | 0.9874 | +0.0455 [+0.0337, +0.0583] |
| retention_inner | 0.8972 | 0.9305 | +0.0332 [+0.0275, +0.0389] |
| retention_bass | 0.9319 | 0.9967 | +0.0648 [+0.0429, +0.0904] |
| note_i_f1 | 0.7374 | 0.7820 | +0.0446 [+0.0359, +0.0543] |
| note_f1 | 0.9164 | 0.9710 | +0.0546 [+0.0461, +0.0639] |
| mel_top_f1 | 0.9026 | 0.9573 | +0.0547 [+0.0424, +0.0683] |
| harmony | 0.9794 | 0.9824 | +0.0029 [+0.0020, +0.0039] |
| intervention_rate | 0.1135 | 0.0676 | -0.0460 [-0.0494, -0.0425] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | True |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.981 | [0.989, 1.012] | False |
| doubling_rate | 0.243 | [0.216, 0.289] | True |
| polyphony_rate | 0.895 | [0.878, 0.908] | True |
| rhythmic_independence | 0.567 | [0.508, 0.568] | True |
| duration_ratio | 0.952 | [0.908, 1.000] | True |
| harmony | 0.982 | [0.978, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.20, retention_top +1.25, retention_inner +1.32, retention_bass +1.11

## duo (150 movements): success = False

| Metric | arranger-v2b | rl-SA | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.8520 | 0.9241 | +0.0722 [+0.0639, +0.0810] |
| unneeded_ds_per_source_note | 0.2225 | 0.2219 | -0.0006 [-0.0039, +0.0024] |
| retention_top | 0.8882 | 0.9706 | +0.0825 [+0.0663, +0.1004] |
| retention_inner | 0.6774 | 0.7114 | +0.0340 [+0.0262, +0.0414] |
| retention_bass | 0.8809 | 0.9550 | +0.0741 [+0.0610, +0.0882] |
| note_i_f1 | 0.6124 | 0.6603 | +0.0479 [+0.0413, +0.0550] |
| note_f1 | 0.8467 | 0.9033 | +0.0566 [+0.0509, +0.0626] |
| mel_top_f1 | 0.8412 | 0.9178 | +0.0766 [+0.0604, +0.0946] |
| harmony | 0.9244 | 0.9269 | +0.0025 [+0.0009, +0.0040] |
| intervention_rate | 0.2101 | 0.1589 | -0.0512 [-0.0556, -0.0466] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | True |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.875 | [0.848, 1.000] | True |
| doubling_rate | 0.172 | [0.131, 0.233] | True |
| polyphony_rate | 0.880 | [0.858, 0.908] | True |
| rhythmic_independence | 0.536 | [0.439, 0.574] | True |
| duration_ratio | 0.883 | [0.864, 1.000] | True |
| harmony | 0.928 | [0.921, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.66, retention_top +1.54, retention_inner +5.21, retention_bass +1.62
