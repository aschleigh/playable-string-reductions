# rl-SA3D9Z (setting A3D9) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | rl-SA3D9Z | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9278 | 0.9713 | +0.0435 [+0.0342, +0.0535] |
| unneeded_ds_per_source_note | 0.1524 | 0.1227 | -0.0298 [-0.0344, -0.0254] |
| retention_top | 0.9422 | 0.9744 | +0.0322 [+0.0201, +0.0455] |
| retention_inner | 0.8988 | 0.9210 | +0.0222 [+0.0157, +0.0289] |
| retention_bass | 0.9178 | 0.9929 | +0.0752 [+0.0504, +0.1039] |
| note_i_f1 | 0.7308 | 0.7616 | +0.0307 [+0.0208, +0.0419] |
| note_f1 | 0.9001 | 0.9523 | +0.0522 [+0.0438, +0.0615] |
| mel_top_f1 | 0.8949 | 0.9301 | +0.0352 [+0.0220, +0.0496] |
| harmony | 0.9779 | 0.9681 | -0.0098 [-0.0117, -0.0080] |
| intervention_rate | 0.1053 | 0.0201 | -0.0852 [-0.0898, -0.0805] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | True |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.943 | [0.970, 1.000] | False |
| doubling_rate | 0.230 | [0.210, 0.289] | True |
| polyphony_rate | 0.892 | [0.878, 0.908] | True |
| rhythmic_independence | 0.558 | [0.508, 0.572] | True |
| duration_ratio | 0.933 | [0.907, 1.000] | True |
| harmony | 0.969 | [0.976, 1.000] | False |

Ceiling gap closed: weighted_fidelity +0.97, retention_top +0.89, retention_inner +0.94, retention_bass +1.03

## duo (150 movements): success = False

| Metric | arranger-v2b | rl-SA3D9Z | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.8402 | 0.8890 | +0.0488 [+0.0400, +0.0578] |
| unneeded_ds_per_source_note | 0.2223 | 0.1822 | -0.0401 [-0.0465, -0.0343] |
| retention_top | 0.8656 | 0.9471 | +0.0815 [+0.0635, +0.1005] |
| retention_inner | 0.6892 | 0.6568 | -0.0324 [-0.0452, -0.0208] |
| retention_bass | 0.8758 | 0.9095 | +0.0338 [+0.0189, +0.0500] |
| note_i_f1 | 0.6012 | 0.6403 | +0.0391 [+0.0312, +0.0471] |
| note_f1 | 0.8309 | 0.8642 | +0.0333 [+0.0262, +0.0406] |
| mel_top_f1 | 0.8112 | 0.8659 | +0.0547 [+0.0347, +0.0758] |
| harmony | 0.9243 | 0.8988 | -0.0255 [-0.0287, -0.0223] |
| intervention_rate | 0.1971 | 0.0346 | -0.1625 [-0.1711, -0.1539] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | True |
| 3_interventions_down | True |
| 4_noninferior | False |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.828 | [0.838, 1.000] | False |
| doubling_rate | 0.153 | [0.125, 0.233] | True |
| polyphony_rate | 0.856 | [0.859, 0.908] | False |
| rhythmic_independence | 0.527 | [0.439, 0.575] | True |
| duration_ratio | 0.847 | [0.862, 1.000] | False |
| harmony | 0.902 | [0.921, 1.000] | False |

Ceiling gap closed: weighted_fidelity +0.88, retention_top +1.07, retention_inner +6.12, retention_bass +0.66
