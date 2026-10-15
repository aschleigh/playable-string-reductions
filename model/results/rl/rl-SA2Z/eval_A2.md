# rl-SA2Z (setting A2) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | rl-SA2Z | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9278 | 0.9791 | +0.0513 [+0.0421, +0.0613] |
| unneeded_ds_per_source_note | 0.1524 | 0.1548 | +0.0024 [-0.0016, +0.0061] |
| retention_top | 0.9422 | 0.9821 | +0.0399 [+0.0281, +0.0531] |
| retention_inner | 0.8988 | 0.9402 | +0.0414 [+0.0349, +0.0482] |
| retention_bass | 0.9178 | 0.9946 | +0.0769 [+0.0522, +0.1057] |
| note_i_f1 | 0.7308 | 0.7516 | +0.0208 [+0.0111, +0.0318] |
| note_f1 | 0.9001 | 0.9465 | +0.0464 [+0.0385, +0.0551] |
| mel_top_f1 | 0.8949 | 0.9393 | +0.0444 [+0.0321, +0.0581] |
| harmony | 0.9779 | 0.9823 | +0.0044 [+0.0034, +0.0055] |
| intervention_rate | 0.1053 | 0.0342 | -0.0711 [-0.0750, -0.0673] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | True |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.990 | [0.970, 1.000] | True |
| doubling_rate | 0.238 | [0.210, 0.289] | True |
| polyphony_rate | 0.895 | [0.878, 0.908] | True |
| rhythmic_independence | 0.549 | [0.508, 0.572] | True |
| duration_ratio | 0.931 | [0.907, 1.000] | True |
| harmony | 0.983 | [0.976, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.14, retention_top +1.11, retention_inner +1.75, retention_bass +1.06

## duo (150 movements): success = False

| Metric | arranger-v2b | rl-SA2Z | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.8402 | 0.9072 | +0.0670 [+0.0582, +0.0760] |
| unneeded_ds_per_source_note | 0.2223 | 0.2531 | +0.0309 [+0.0262, +0.0356] |
| retention_top | 0.8656 | 0.9565 | +0.0909 [+0.0729, +0.1101] |
| retention_inner | 0.6892 | 0.7159 | +0.0267 [+0.0145, +0.0377] |
| retention_bass | 0.8758 | 0.9215 | +0.0458 [+0.0313, +0.0613] |
| note_i_f1 | 0.6012 | 0.6298 | +0.0286 [+0.0218, +0.0357] |
| note_f1 | 0.8309 | 0.8557 | +0.0248 [+0.0187, +0.0309] |
| mel_top_f1 | 0.8112 | 0.8771 | +0.0659 [+0.0461, +0.0868] |
| harmony | 0.9243 | 0.9328 | +0.0085 [+0.0066, +0.0105] |
| intervention_rate | 0.1971 | 0.0979 | -0.0992 [-0.1053, -0.0932] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.925 | [0.838, 1.000] | True |
| doubling_rate | 0.165 | [0.125, 0.233] | True |
| polyphony_rate | 0.880 | [0.859, 0.908] | True |
| rhythmic_independence | 0.512 | [0.439, 0.575] | True |
| duration_ratio | 0.846 | [0.862, 1.000] | False |
| harmony | 0.935 | [0.921, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.21, retention_top +1.20, retention_inner -5.05, retention_bass +0.90
