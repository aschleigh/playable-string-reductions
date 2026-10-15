# rl-A (setting A) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | rl-A | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9317 | 0.9772 | +0.0455 [+0.0365, +0.0553] |
| unneeded_ds_per_source_note | 0.1526 | 0.1382 | -0.0144 [-0.0178, -0.0112] |
| retention_top | 0.9419 | 0.9862 | +0.0443 [+0.0327, +0.0570] |
| retention_inner | 0.8972 | 0.9155 | +0.0183 [+0.0135, +0.0234] |
| retention_bass | 0.9319 | 0.9941 | +0.0622 [+0.0402, +0.0876] |
| note_i_f1 | 0.7374 | 0.7677 | +0.0304 [+0.0216, +0.0401] |
| note_f1 | 0.9164 | 0.9664 | +0.0500 [+0.0416, +0.0591] |
| mel_top_f1 | 0.9026 | 0.9588 | +0.0562 [+0.0442, +0.0697] |
| harmony | 0.9794 | 0.9821 | +0.0026 [+0.0020, +0.0033] |
| intervention_rate | 0.1135 | 0.1121 | -0.0014 [-0.0038, +0.0010] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | True |
| 3_interventions_down | False |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.978 | [0.989, 1.012] | False |
| doubling_rate | 0.244 | [0.216, 0.289] | True |
| polyphony_rate | 0.896 | [0.878, 0.908] | True |
| rhythmic_independence | 0.549 | [0.508, 0.568] | True |
| duration_ratio | 0.952 | [0.908, 1.000] | True |
| harmony | 0.982 | [0.978, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.10, retention_top +1.22, retention_inner +0.73, retention_bass +1.06

## duo (150 movements): success = False

| Metric | arranger-v2b | rl-A | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.8520 | 0.9152 | +0.0632 [+0.0551, +0.0719] |
| unneeded_ds_per_source_note | 0.2225 | 0.2265 | +0.0040 [+0.0008, +0.0069] |
| retention_top | 0.8882 | 0.9674 | +0.0792 [+0.0635, +0.0966] |
| retention_inner | 0.6774 | 0.7041 | +0.0267 [+0.0202, +0.0328] |
| retention_bass | 0.8809 | 0.9350 | +0.0541 [+0.0413, +0.0679] |
| note_i_f1 | 0.6124 | 0.6359 | +0.0236 [+0.0174, +0.0302] |
| note_f1 | 0.8467 | 0.8947 | +0.0480 [+0.0424, +0.0539] |
| mel_top_f1 | 0.8412 | 0.9197 | +0.0785 [+0.0622, +0.0967] |
| harmony | 0.9244 | 0.9285 | +0.0041 [+0.0031, +0.0050] |
| intervention_rate | 0.2101 | 0.2304 | +0.0203 [+0.0176, +0.0231] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | False |
| 4_noninferior | True |
| 5_detectors_inside | True |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.877 | [0.848, 1.000] | True |
| doubling_rate | 0.169 | [0.131, 0.233] | True |
| polyphony_rate | 0.882 | [0.858, 0.908] | True |
| rhythmic_independence | 0.532 | [0.439, 0.574] | True |
| duration_ratio | 0.885 | [0.864, 1.000] | True |
| harmony | 0.930 | [0.921, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.45, retention_top +1.48, retention_inner +4.09, retention_bass +1.18
