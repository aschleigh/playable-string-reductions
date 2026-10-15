# rl-A (setting A) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | rl-A | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9278 | 0.9780 | +0.0502 [+0.0408, +0.0604] |
| unneeded_ds_per_source_note | 0.1524 | 0.1367 | -0.0157 [-0.0194, -0.0124] |
| retention_top | 0.9422 | 0.9864 | +0.0442 [+0.0322, +0.0578] |
| retention_inner | 0.8988 | 0.9199 | +0.0211 [+0.0155, +0.0272] |
| retention_bass | 0.9178 | 0.9941 | +0.0764 [+0.0516, +0.1052] |
| note_i_f1 | 0.7308 | 0.7673 | +0.0365 [+0.0264, +0.0475] |
| note_f1 | 0.9001 | 0.9536 | +0.0535 [+0.0453, +0.0628] |
| mel_top_f1 | 0.8949 | 0.9588 | +0.0639 [+0.0511, +0.0780] |
| harmony | 0.9779 | 0.9800 | +0.0021 [+0.0014, +0.0028] |
| intervention_rate | 0.1053 | 0.1014 | -0.0039 [-0.0063, -0.0016] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | True |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.952 | [0.970, 1.000] | False |
| doubling_rate | 0.234 | [0.210, 0.289] | True |
| polyphony_rate | 0.895 | [0.878, 0.908] | True |
| rhythmic_independence | 0.555 | [0.508, 0.572] | True |
| duration_ratio | 0.953 | [0.907, 1.000] | True |
| harmony | 0.980 | [0.976, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.11, retention_top +1.23, retention_inner +0.89, retention_bass +1.05

## duo (150 movements): success = False

| Metric | arranger-v2b | rl-A | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.8402 | 0.9172 | +0.0770 [+0.0682, +0.0862] |
| unneeded_ds_per_source_note | 0.2223 | 0.2266 | +0.0043 [+0.0009, +0.0074] |
| retention_top | 0.8656 | 0.9683 | +0.1027 [+0.0848, +0.1219] |
| retention_inner | 0.6892 | 0.7088 | +0.0196 [+0.0121, +0.0266] |
| retention_bass | 0.8758 | 0.9374 | +0.0617 [+0.0477, +0.0769] |
| note_i_f1 | 0.6012 | 0.6311 | +0.0299 [+0.0235, +0.0368] |
| note_f1 | 0.8309 | 0.8840 | +0.0531 [+0.0467, +0.0599] |
| mel_top_f1 | 0.8112 | 0.9197 | +0.1085 [+0.0891, +0.1294] |
| harmony | 0.9243 | 0.9280 | +0.0037 [+0.0027, +0.0048] |
| intervention_rate | 0.1971 | 0.2145 | +0.0174 [+0.0145, +0.0204] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | False |
| 4_noninferior | True |
| 5_detectors_inside | True |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.859 | [0.838, 1.000] | True |
| doubling_rate | 0.154 | [0.125, 0.233] | True |
| polyphony_rate | 0.882 | [0.859, 0.908] | True |
| rhythmic_independence | 0.538 | [0.439, 0.575] | True |
| duration_ratio | 0.887 | [0.862, 1.000] | True |
| harmony | 0.930 | [0.921, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.39, retention_top +1.35, retention_inner -3.70, retention_bass +1.21
