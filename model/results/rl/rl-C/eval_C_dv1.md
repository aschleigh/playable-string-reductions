# rl-C (setting C) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | rl-C | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9210 | 0.9678 | +0.0468 [+0.0397, +0.0545] |
| unneeded_ds_per_source_note | 0.1526 | 0.1710 | +0.0183 [+0.0149, +0.0220] |
| retention_top | 0.9419 | 0.9802 | +0.0383 [+0.0262, +0.0513] |
| retention_inner | 0.8972 | 0.9423 | +0.0451 [+0.0395, +0.0510] |
| retention_bass | 0.9319 | 0.9939 | +0.0620 [+0.0400, +0.0874] |
| note_i_f1 | 0.7374 | 0.7588 | +0.0215 [+0.0128, +0.0307] |
| note_f1 | 0.9164 | 0.9364 | +0.0200 [+0.0111, +0.0290] |
| mel_top_f1 | 0.9026 | 0.9143 | +0.0117 [-0.0013, +0.0261] |
| harmony | 0.9794 | 0.9824 | +0.0030 [+0.0022, +0.0038] |
| intervention_rate | 0.1135 | 0.1130 | -0.0006 [-0.0028, +0.0016] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | False |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 1.068 | [0.989, 1.012] | False |
| doubling_rate | 0.251 | [0.216, 0.289] | True |
| polyphony_rate | 0.895 | [0.878, 0.908] | True |
| rhythmic_independence | 0.520 | [0.508, 0.568] | True |
| duration_ratio | 0.885 | [0.908, 1.000] | False |
| harmony | 0.983 | [0.978, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.26, retention_top +1.05, retention_inner +1.79, retention_bass +1.06

## duo (150 movements): success = False

| Metric | arranger-v2b | rl-C | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.7992 | 0.8687 | +0.0695 [+0.0638, +0.0754] |
| unneeded_ds_per_source_note | 0.2225 | 0.2613 | +0.0388 [+0.0333, +0.0450] |
| retention_top | 0.8882 | 0.9538 | +0.0656 [+0.0490, +0.0837] |
| retention_inner | 0.6774 | 0.7638 | +0.0865 [+0.0781, +0.0945] |
| retention_bass | 0.8809 | 0.9268 | +0.0459 [+0.0334, +0.0598] |
| note_i_f1 | 0.6124 | 0.6261 | +0.0137 [+0.0074, +0.0203] |
| note_f1 | 0.8467 | 0.8753 | +0.0286 [+0.0221, +0.0350] |
| mel_top_f1 | 0.8412 | 0.8628 | +0.0216 [+0.0038, +0.0413] |
| harmony | 0.9244 | 0.9283 | +0.0039 [+0.0025, +0.0055] |
| intervention_rate | 0.2101 | 0.2146 | +0.0045 [+0.0011, +0.0079] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | False |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.965 | [0.848, 1.000] | True |
| doubling_rate | 0.174 | [0.131, 0.233] | True |
| polyphony_rate | 0.879 | [0.858, 0.908] | True |
| rhythmic_independence | 0.495 | [0.439, 0.574] | True |
| duration_ratio | 0.820 | [0.864, 1.000] | False |
| harmony | 0.930 | [0.921, 1.000] | True |

Ceiling gap closed: weighted_fidelity +2.16, retention_top +1.23, retention_inner +13.26, retention_bass +1.00
