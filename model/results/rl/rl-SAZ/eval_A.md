# rl-SAZ (setting A) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | rl-SAZ | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9278 | 0.9787 | +0.0508 [+0.0416, +0.0608] |
| unneeded_ds_per_source_note | 0.1524 | 0.1585 | +0.0060 [+0.0019, +0.0101] |
| retention_top | 0.9422 | 0.9808 | +0.0387 [+0.0268, +0.0518] |
| retention_inner | 0.8988 | 0.9443 | +0.0455 [+0.0388, +0.0526] |
| retention_bass | 0.9178 | 0.9933 | +0.0755 [+0.0509, +0.1042] |
| note_i_f1 | 0.7308 | 0.7438 | +0.0130 [+0.0033, +0.0239] |
| note_f1 | 0.9001 | 0.9380 | +0.0379 [+0.0299, +0.0465] |
| mel_top_f1 | 0.8949 | 0.9254 | +0.0305 [+0.0182, +0.0442] |
| harmony | 0.9779 | 0.9817 | +0.0037 [+0.0026, +0.0048] |
| intervention_rate | 0.1053 | 0.0336 | -0.0717 [-0.0755, -0.0679] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 1.015 | [0.970, 1.000] | False |
| doubling_rate | 0.244 | [0.210, 0.289] | True |
| polyphony_rate | 0.895 | [0.878, 0.908] | True |
| rhythmic_independence | 0.529 | [0.508, 0.572] | True |
| duration_ratio | 0.909 | [0.907, 1.000] | True |
| harmony | 0.982 | [0.976, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.13, retention_top +1.07, retention_inner +1.92, retention_bass +1.04

## duo (150 movements): success = False

| Metric | arranger-v2b | rl-SAZ | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.8402 | 0.9041 | +0.0639 [+0.0551, +0.0730] |
| unneeded_ds_per_source_note | 0.2223 | 0.2637 | +0.0414 [+0.0356, +0.0476] |
| retention_top | 0.8656 | 0.9533 | +0.0877 [+0.0695, +0.1071] |
| retention_inner | 0.6892 | 0.7375 | +0.0483 [+0.0358, +0.0600] |
| retention_bass | 0.8758 | 0.9055 | +0.0297 [+0.0150, +0.0458] |
| note_i_f1 | 0.6012 | 0.6175 | +0.0163 [+0.0093, +0.0235] |
| note_f1 | 0.8309 | 0.8467 | +0.0158 [+0.0097, +0.0218] |
| mel_top_f1 | 0.8112 | 0.8566 | +0.0454 [+0.0257, +0.0659] |
| harmony | 0.9243 | 0.9340 | +0.0097 [+0.0078, +0.0117] |
| intervention_rate | 0.1971 | 0.0943 | -0.1027 [-0.1091, -0.0965] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.959 | [0.838, 1.000] | True |
| doubling_rate | 0.173 | [0.125, 0.233] | True |
| polyphony_rate | 0.881 | [0.859, 0.908] | True |
| rhythmic_independence | 0.481 | [0.439, 0.575] | True |
| duration_ratio | 0.824 | [0.862, 1.000] | False |
| harmony | 0.936 | [0.921, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.16, retention_top +1.15, retention_inner -9.11, retention_bass +0.59
