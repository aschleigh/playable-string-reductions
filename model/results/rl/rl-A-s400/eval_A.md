# rl-A-s400 (setting A) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | rl-A-s400 | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9317 | 0.9779 | +0.0462 [+0.0371, +0.0561] |
| unneeded_ds_per_source_note | 0.1526 | 0.1414 | -0.0113 [-0.0145, -0.0082] |
| retention_top | 0.9419 | 0.9865 | +0.0446 [+0.0329, +0.0574] |
| retention_inner | 0.8972 | 0.9182 | +0.0210 [+0.0159, +0.0262] |
| retention_bass | 0.9319 | 0.9946 | +0.0627 [+0.0408, +0.0882] |
| note_i_f1 | 0.7374 | 0.7721 | +0.0348 [+0.0261, +0.0442] |
| note_f1 | 0.9164 | 0.9673 | +0.0509 [+0.0425, +0.0602] |
| mel_top_f1 | 0.9026 | 0.9595 | +0.0569 [+0.0444, +0.0710] |
| harmony | 0.9794 | 0.9822 | +0.0027 [+0.0021, +0.0034] |
| intervention_rate | 0.1135 | 0.1161 | +0.0026 [+0.0003, +0.0048] |

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
| doubling_rate | 0.242 | [0.216, 0.289] | True |
| polyphony_rate | 0.896 | [0.878, 0.908] | True |
| rhythmic_independence | 0.555 | [0.508, 0.568] | True |
| duration_ratio | 0.952 | [0.908, 1.000] | True |
| harmony | 0.982 | [0.978, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.12, retention_top +1.23, retention_inner +0.83, retention_bass +1.07

## duo (150 movements): success = False

| Metric | arranger-v2b | rl-A-s400 | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.8520 | 0.9144 | +0.0624 [+0.0543, +0.0711] |
| unneeded_ds_per_source_note | 0.2225 | 0.2251 | +0.0026 [-0.0003, +0.0053] |
| retention_top | 0.8882 | 0.9670 | +0.0788 [+0.0632, +0.0961] |
| retention_inner | 0.6774 | 0.6905 | +0.0131 [+0.0068, +0.0192] |
| retention_bass | 0.8809 | 0.9403 | +0.0595 [+0.0468, +0.0734] |
| note_i_f1 | 0.6124 | 0.6432 | +0.0309 [+0.0247, +0.0375] |
| note_f1 | 0.8467 | 0.8924 | +0.0457 [+0.0402, +0.0514] |
| mel_top_f1 | 0.8412 | 0.9182 | +0.0769 [+0.0611, +0.0947] |
| harmony | 0.9244 | 0.9282 | +0.0037 [+0.0029, +0.0046] |
| intervention_rate | 0.2101 | 0.2308 | +0.0207 [+0.0182, +0.0232] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | False |
| 4_noninferior | True |
| 5_detectors_inside | True |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.872 | [0.848, 1.000] | True |
| doubling_rate | 0.169 | [0.131, 0.233] | True |
| polyphony_rate | 0.882 | [0.858, 0.908] | True |
| rhythmic_independence | 0.539 | [0.439, 0.574] | True |
| duration_ratio | 0.888 | [0.864, 1.000] | True |
| harmony | 0.930 | [0.921, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.43, retention_top +1.48, retention_inner +2.01, retention_bass +1.30
