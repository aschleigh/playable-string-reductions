# control-S (setting A) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | control-S | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9317 | 0.9700 | +0.0383 [+0.0299, +0.0474] |
| unneeded_ds_per_source_note | 0.1526 | 0.1620 | +0.0093 [+0.0067, +0.0119] |
| retention_top | 0.9419 | 0.9728 | +0.0309 [+0.0211, +0.0414] |
| retention_inner | 0.8972 | 0.9131 | +0.0159 [+0.0105, +0.0214] |
| retention_bass | 0.9319 | 0.9955 | +0.0636 [+0.0417, +0.0891] |
| note_i_f1 | 0.7374 | 0.7884 | +0.0511 [+0.0432, +0.0595] |
| note_f1 | 0.9164 | 0.9586 | +0.0422 [+0.0341, +0.0512] |
| mel_top_f1 | 0.9026 | 0.9375 | +0.0350 [+0.0239, +0.0473] |
| harmony | 0.9794 | 0.9767 | -0.0027 [-0.0039, -0.0016] |
| intervention_rate | 0.1135 | 0.0428 | -0.0708 [-0.0755, -0.0662] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.980 | [0.989, 1.012] | False |
| doubling_rate | 0.235 | [0.216, 0.289] | True |
| polyphony_rate | 0.892 | [0.878, 0.908] | True |
| rhythmic_independence | 0.585 | [0.508, 0.568] | False |
| duration_ratio | 0.934 | [0.908, 1.000] | True |
| harmony | 0.977 | [0.978, 1.000] | False |

Ceiling gap closed: weighted_fidelity +0.93, retention_top +0.85, retention_inner +0.63, retention_bass +1.09

## duo (150 movements): success = False

| Metric | arranger-v2b | control-S | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.8520 | 0.9018 | +0.0499 [+0.0423, +0.0581] |
| unneeded_ds_per_source_note | 0.2225 | 0.2046 | -0.0179 [-0.0209, -0.0151] |
| retention_top | 0.8882 | 0.9535 | +0.0653 [+0.0506, +0.0818] |
| retention_inner | 0.6774 | 0.6436 | -0.0337 [-0.0432, -0.0248] |
| retention_bass | 0.8809 | 0.9479 | +0.0671 [+0.0541, +0.0812] |
| note_i_f1 | 0.6124 | 0.6633 | +0.0509 [+0.0449, +0.0575] |
| note_f1 | 0.8467 | 0.8833 | +0.0367 [+0.0308, +0.0429] |
| mel_top_f1 | 0.8412 | 0.9031 | +0.0619 [+0.0465, +0.0792] |
| harmony | 0.9244 | 0.9151 | -0.0093 [-0.0111, -0.0077] |
| intervention_rate | 0.2101 | 0.0491 | -0.1610 [-0.1703, -0.1517] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | True |
| 3_interventions_down | True |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.841 | [0.848, 1.000] | False |
| doubling_rate | 0.162 | [0.131, 0.233] | True |
| polyphony_rate | 0.868 | [0.858, 0.908] | True |
| rhythmic_independence | 0.547 | [0.439, 0.574] | True |
| duration_ratio | 0.881 | [0.864, 1.000] | True |
| harmony | 0.917 | [0.921, 1.000] | False |

Ceiling gap closed: weighted_fidelity +1.15, retention_top +1.22, retention_inner -5.18, retention_bass +1.47
