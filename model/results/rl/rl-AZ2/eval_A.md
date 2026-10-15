# rl-AZ2 (setting A) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | rl-AZ2 | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9317 | 0.9829 | +0.0512 [+0.0422, +0.0610] |
| unneeded_ds_per_source_note | 0.1526 | 0.2283 | +0.0757 [+0.0652, +0.0863] |
| retention_top | 0.9419 | 0.9892 | +0.0474 [+0.0358, +0.0601] |
| retention_inner | 0.8972 | 0.9460 | +0.0487 [+0.0428, +0.0549] |
| retention_bass | 0.9319 | 0.9914 | +0.0595 [+0.0377, +0.0851] |
| note_i_f1 | 0.7374 | 0.6195 | -0.1179 [-0.1289, -0.1063] |
| note_f1 | 0.9164 | 0.8263 | -0.0900 [-0.1039, -0.0763] |
| mel_top_f1 | 0.9026 | 0.8233 | -0.0792 [-0.0954, -0.0635] |
| harmony | 0.9794 | 0.9917 | +0.0123 [+0.0107, +0.0138] |
| intervention_rate | 0.1135 | 0.0483 | -0.0652 [-0.0691, -0.0615] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | True |
| 4_noninferior | False |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 1.349 | [0.989, 1.012] | False |
| doubling_rate | 0.292 | [0.216, 0.289] | False |
| polyphony_rate | 0.896 | [0.878, 0.908] | True |
| rhythmic_independence | 0.379 | [0.508, 0.568] | False |
| duration_ratio | 0.738 | [0.908, 1.000] | False |
| harmony | 0.992 | [0.978, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.24, retention_top +1.30, retention_inner +1.93, retention_bass +1.02

## duo (150 movements): success = False

| Metric | arranger-v2b | rl-AZ2 | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.8520 | 0.9058 | +0.0539 [+0.0450, +0.0631] |
| unneeded_ds_per_source_note | 0.2225 | 0.3773 | +0.1548 [+0.1366, +0.1733] |
| retention_top | 0.8882 | 0.9522 | +0.0641 [+0.0475, +0.0819] |
| retention_inner | 0.6774 | 0.7117 | +0.0343 [+0.0222, +0.0453] |
| retention_bass | 0.8809 | 0.9270 | +0.0462 [+0.0317, +0.0615] |
| note_i_f1 | 0.6124 | 0.5460 | -0.0663 [-0.0752, -0.0572] |
| note_f1 | 0.8467 | 0.7509 | -0.0958 [-0.1066, -0.0847] |
| mel_top_f1 | 0.8412 | 0.7623 | -0.0789 [-0.0971, -0.0604] |
| harmony | 0.9244 | 0.9566 | +0.0322 [+0.0294, +0.0350] |
| intervention_rate | 0.2101 | 0.1602 | -0.0498 [-0.0553, -0.0446] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | True |
| 4_noninferior | False |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 1.230 | [0.848, 1.000] | False |
| doubling_rate | 0.207 | [0.131, 0.233] | True |
| polyphony_rate | 0.887 | [0.858, 0.908] | True |
| rhythmic_independence | 0.376 | [0.439, 0.574] | False |
| duration_ratio | 0.711 | [0.864, 1.000] | False |
| harmony | 0.956 | [0.921, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.24, retention_top +1.20, retention_inner +5.26, retention_bass +1.01
