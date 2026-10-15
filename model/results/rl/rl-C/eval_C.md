# rl-C (setting C) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | rl-C | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9183 | 0.9692 | +0.0509 [+0.0431, +0.0591] |
| unneeded_ds_per_source_note | 0.1524 | 0.1690 | +0.0166 [+0.0131, +0.0203] |
| retention_top | 0.9422 | 0.9802 | +0.0381 [+0.0257, +0.0519] |
| retention_inner | 0.8988 | 0.9454 | +0.0466 [+0.0404, +0.0533] |
| retention_bass | 0.9178 | 0.9942 | +0.0765 [+0.0516, +0.1052] |
| note_i_f1 | 0.7308 | 0.7584 | +0.0275 [+0.0177, +0.0382] |
| note_f1 | 0.9001 | 0.9240 | +0.0239 [+0.0147, +0.0335] |
| mel_top_f1 | 0.8949 | 0.9142 | +0.0193 [+0.0056, +0.0343] |
| harmony | 0.9779 | 0.9803 | +0.0023 [+0.0016, +0.0031] |
| intervention_rate | 0.1053 | 0.1018 | -0.0035 [-0.0056, -0.0014] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 1.040 | [0.970, 1.000] | False |
| doubling_rate | 0.240 | [0.210, 0.289] | True |
| polyphony_rate | 0.895 | [0.878, 0.908] | True |
| rhythmic_independence | 0.527 | [0.508, 0.572] | True |
| duration_ratio | 0.886 | [0.907, 1.000] | False |
| harmony | 0.981 | [0.976, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.28, retention_top +1.06, retention_inner +1.97, retention_bass +1.05

## duo (150 movements): success = False

| Metric | arranger-v2b | rl-C | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.7950 | 0.8717 | +0.0766 [+0.0707, +0.0826] |
| unneeded_ds_per_source_note | 0.2223 | 0.2605 | +0.0382 [+0.0329, +0.0440] |
| retention_top | 0.8656 | 0.9541 | +0.0885 [+0.0701, +0.1078] |
| retention_inner | 0.6892 | 0.7692 | +0.0800 [+0.0709, +0.0887] |
| retention_bass | 0.8758 | 0.9295 | +0.0538 [+0.0395, +0.0693] |
| note_i_f1 | 0.6012 | 0.6216 | +0.0204 [+0.0141, +0.0270] |
| note_f1 | 0.8309 | 0.8659 | +0.0350 [+0.0284, +0.0416] |
| mel_top_f1 | 0.8112 | 0.8637 | +0.0525 [+0.0321, +0.0738] |
| harmony | 0.9243 | 0.9278 | +0.0035 [+0.0022, +0.0049] |
| intervention_rate | 0.1971 | 0.1986 | +0.0015 [-0.0018, +0.0049] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | False |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.945 | [0.838, 1.000] | True |
| doubling_rate | 0.158 | [0.125, 0.233] | True |
| polyphony_rate | 0.879 | [0.859, 0.908] | True |
| rhythmic_independence | 0.503 | [0.439, 0.575] | True |
| duration_ratio | 0.820 | [0.862, 1.000] | False |
| harmony | 0.929 | [0.921, 1.000] | True |

Ceiling gap closed: weighted_fidelity +2.11, retention_top +1.16, retention_inner -15.10, retention_bass +1.06
