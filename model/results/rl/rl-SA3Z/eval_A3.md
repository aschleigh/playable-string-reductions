# rl-SA3Z (setting A3) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | rl-SA3Z | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9278 | 0.9699 | +0.0420 [+0.0328, +0.0520] |
| unneeded_ds_per_source_note | 0.1524 | 0.1226 | -0.0298 [-0.0346, -0.0253] |
| retention_top | 0.9422 | 0.9715 | +0.0293 [+0.0171, +0.0428] |
| retention_inner | 0.8988 | 0.9206 | +0.0218 [+0.0152, +0.0287] |
| retention_bass | 0.9178 | 0.9934 | +0.0757 [+0.0508, +0.1044] |
| note_i_f1 | 0.7308 | 0.7648 | +0.0340 [+0.0242, +0.0451] |
| note_f1 | 0.9001 | 0.9517 | +0.0516 [+0.0433, +0.0609] |
| mel_top_f1 | 0.8949 | 0.9249 | +0.0300 [+0.0168, +0.0443] |
| harmony | 0.9779 | 0.9680 | -0.0099 [-0.0118, -0.0082] |
| intervention_rate | 0.1053 | 0.0207 | -0.0846 [-0.0892, -0.0799] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | True |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.944 | [0.970, 1.000] | False |
| doubling_rate | 0.230 | [0.210, 0.289] | True |
| polyphony_rate | 0.892 | [0.878, 0.908] | True |
| rhythmic_independence | 0.558 | [0.508, 0.572] | True |
| duration_ratio | 0.933 | [0.907, 1.000] | True |
| harmony | 0.969 | [0.976, 1.000] | False |

Ceiling gap closed: weighted_fidelity +0.93, retention_top +0.81, retention_inner +0.92, retention_bass +1.04

## duo (150 movements): success = False

| Metric | arranger-v2b | rl-SA3Z | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.8402 | 0.8889 | +0.0487 [+0.0399, +0.0576] |
| unneeded_ds_per_source_note | 0.2223 | 0.1844 | -0.0379 [-0.0442, -0.0320] |
| retention_top | 0.8656 | 0.9447 | +0.0791 [+0.0613, +0.0980] |
| retention_inner | 0.6892 | 0.6575 | -0.0317 [-0.0445, -0.0200] |
| retention_bass | 0.8758 | 0.9132 | +0.0374 [+0.0225, +0.0536] |
| note_i_f1 | 0.6012 | 0.6422 | +0.0410 [+0.0333, +0.0490] |
| note_f1 | 0.8309 | 0.8635 | +0.0326 [+0.0256, +0.0398] |
| mel_top_f1 | 0.8112 | 0.8617 | +0.0505 [+0.0306, +0.0716] |
| harmony | 0.9243 | 0.9004 | -0.0239 [-0.0271, -0.0207] |
| intervention_rate | 0.1971 | 0.0378 | -0.1592 [-0.1676, -0.1508] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | True |
| 3_interventions_down | True |
| 4_noninferior | False |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.831 | [0.838, 1.000] | False |
| doubling_rate | 0.154 | [0.125, 0.233] | True |
| polyphony_rate | 0.859 | [0.859, 0.908] | False |
| rhythmic_independence | 0.525 | [0.439, 0.575] | True |
| duration_ratio | 0.848 | [0.862, 1.000] | False |
| harmony | 0.904 | [0.921, 1.000] | False |

Ceiling gap closed: weighted_fidelity +0.88, retention_top +1.04, retention_inner +5.99, retention_bass +0.74
