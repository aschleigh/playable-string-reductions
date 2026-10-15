# rl-SA (setting A) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | rl-SA | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9278 | 0.9819 | +0.0541 [+0.0447, +0.0643] |
| unneeded_ds_per_source_note | 0.1524 | 0.1467 | -0.0057 [-0.0089, -0.0027] |
| retention_top | 0.9422 | 0.9876 | +0.0455 [+0.0333, +0.0591] |
| retention_inner | 0.8988 | 0.9350 | +0.0362 [+0.0301, +0.0425] |
| retention_bass | 0.9178 | 0.9969 | +0.0791 [+0.0541, +0.1079] |
| note_i_f1 | 0.7308 | 0.7797 | +0.0489 [+0.0394, +0.0598] |
| note_f1 | 0.9001 | 0.9580 | +0.0579 [+0.0495, +0.0672] |
| mel_top_f1 | 0.8949 | 0.9571 | +0.0622 [+0.0491, +0.0765] |
| harmony | 0.9779 | 0.9802 | +0.0023 [+0.0013, +0.0033] |
| intervention_rate | 0.1053 | 0.0554 | -0.0499 [-0.0531, -0.0466] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | True |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.955 | [0.970, 1.000] | False |
| doubling_rate | 0.232 | [0.210, 0.289] | True |
| polyphony_rate | 0.895 | [0.878, 0.908] | True |
| rhythmic_independence | 0.573 | [0.508, 0.572] | False |
| duration_ratio | 0.952 | [0.907, 1.000] | True |
| harmony | 0.980 | [0.976, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.20, retention_top +1.26, retention_inner +1.53, retention_bass +1.09

## duo (150 movements): success = False

| Metric | arranger-v2b | rl-SA | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.8402 | 0.9261 | +0.0860 [+0.0769, +0.0953] |
| unneeded_ds_per_source_note | 0.2223 | 0.2221 | -0.0002 [-0.0038, +0.0031] |
| retention_top | 0.8656 | 0.9713 | +0.1057 [+0.0875, +0.1251] |
| retention_inner | 0.6892 | 0.7204 | +0.0312 [+0.0229, +0.0390] |
| retention_bass | 0.8758 | 0.9558 | +0.0800 [+0.0655, +0.0959] |
| note_i_f1 | 0.6012 | 0.6571 | +0.0559 [+0.0490, +0.0632] |
| note_f1 | 0.8309 | 0.8930 | +0.0621 [+0.0555, +0.0689] |
| mel_top_f1 | 0.8112 | 0.9176 | +0.1064 [+0.0867, +0.1275] |
| harmony | 0.9243 | 0.9260 | +0.0017 [-0.0001, +0.0034] |
| intervention_rate | 0.1971 | 0.1420 | -0.0551 [-0.0593, -0.0508] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | True |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.859 | [0.838, 1.000] | True |
| doubling_rate | 0.162 | [0.125, 0.233] | True |
| polyphony_rate | 0.880 | [0.859, 0.908] | True |
| rhythmic_independence | 0.537 | [0.439, 0.575] | True |
| duration_ratio | 0.882 | [0.862, 1.000] | True |
| harmony | 0.927 | [0.921, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.55, retention_top +1.39, retention_inner -5.88, retention_bass +1.58
