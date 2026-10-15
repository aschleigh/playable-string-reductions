# control-S (setting C) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | control-S | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9183 | 0.9565 | +0.0382 [+0.0309, +0.0464] |
| unneeded_ds_per_source_note | 0.1524 | 0.1630 | +0.0106 [+0.0078, +0.0133] |
| retention_top | 0.9422 | 0.9764 | +0.0342 [+0.0231, +0.0471] |
| retention_inner | 0.8988 | 0.9171 | +0.0183 [+0.0124, +0.0245] |
| retention_bass | 0.9178 | 0.9957 | +0.0780 [+0.0531, +0.1066] |
| note_i_f1 | 0.7308 | 0.7852 | +0.0544 [+0.0458, +0.0642] |
| note_f1 | 0.9001 | 0.9469 | +0.0468 [+0.0388, +0.0558] |
| mel_top_f1 | 0.8949 | 0.9384 | +0.0435 [+0.0315, +0.0568] |
| harmony | 0.9779 | 0.9752 | -0.0027 [-0.0039, -0.0016] |
| intervention_rate | 0.1053 | 0.0326 | -0.0727 [-0.0771, -0.0683] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.959 | [0.970, 1.000] | False |
| doubling_rate | 0.225 | [0.210, 0.289] | True |
| polyphony_rate | 0.892 | [0.878, 0.908] | True |
| rhythmic_independence | 0.594 | [0.508, 0.572] | False |
| duration_ratio | 0.934 | [0.907, 1.000] | True |
| harmony | 0.975 | [0.976, 1.000] | False |

Ceiling gap closed: weighted_fidelity +0.96, retention_top +0.95, retention_inner +0.78, retention_bass +1.07

## duo (150 movements): success = False

| Metric | arranger-v2b | control-S | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.7950 | 0.8281 | +0.0331 [+0.0274, +0.0392] |
| unneeded_ds_per_source_note | 0.2223 | 0.2052 | -0.0171 [-0.0204, -0.0141] |
| retention_top | 0.8656 | 0.9575 | +0.0919 [+0.0744, +0.1112] |
| retention_inner | 0.6892 | 0.6500 | -0.0392 [-0.0500, -0.0295] |
| retention_bass | 0.8758 | 0.9488 | +0.0731 [+0.0587, +0.0888] |
| note_i_f1 | 0.6012 | 0.6608 | +0.0597 [+0.0528, +0.0668] |
| note_f1 | 0.8309 | 0.8746 | +0.0437 [+0.0369, +0.0509] |
| mel_top_f1 | 0.8112 | 0.9042 | +0.0930 [+0.0736, +0.1139] |
| harmony | 0.9243 | 0.9145 | -0.0098 [-0.0117, -0.0080] |
| intervention_rate | 0.1971 | 0.0388 | -0.1582 [-0.1674, -0.1492] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | True |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.827 | [0.838, 1.000] | False |
| doubling_rate | 0.154 | [0.125, 0.233] | True |
| polyphony_rate | 0.868 | [0.859, 0.908] | True |
| rhythmic_independence | 0.548 | [0.439, 0.575] | True |
| duration_ratio | 0.881 | [0.862, 1.000] | True |
| harmony | 0.917 | [0.921, 1.000] | False |

Ceiling gap closed: weighted_fidelity +0.91, retention_top +1.21, retention_inner +7.40, retention_bass +1.44
