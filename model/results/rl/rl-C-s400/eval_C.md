# rl-C-s400 (setting C) vs arranger-v2b, masked, METRICS 1.4.0-draft

## trio (150 movements): success = False

| Metric | arranger-v2b | rl-C-s400 | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.9210 | 0.9665 | +0.0455 [+0.0385, +0.0532] |
| unneeded_ds_per_source_note | 0.1526 | 0.1707 | +0.0181 [+0.0149, +0.0214] |
| retention_top | 0.9419 | 0.9794 | +0.0375 [+0.0255, +0.0505] |
| retention_inner | 0.8972 | 0.9398 | +0.0426 [+0.0374, +0.0478] |
| retention_bass | 0.9319 | 0.9940 | +0.0622 [+0.0402, +0.0877] |
| note_i_f1 | 0.7374 | 0.7589 | +0.0216 [+0.0130, +0.0311] |
| note_f1 | 0.9164 | 0.9353 | +0.0190 [+0.0101, +0.0282] |
| mel_top_f1 | 0.9026 | 0.9133 | +0.0107 [-0.0021, +0.0250] |
| harmony | 0.9794 | 0.9822 | +0.0028 [+0.0020, +0.0035] |
| intervention_rate | 0.1135 | 0.1136 | +0.0001 [-0.0020, +0.0021] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | False |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 1.066 | [0.989, 1.012] | False |
| doubling_rate | 0.250 | [0.216, 0.289] | True |
| polyphony_rate | 0.895 | [0.878, 0.908] | True |
| rhythmic_independence | 0.522 | [0.508, 0.568] | True |
| duration_ratio | 0.884 | [0.908, 1.000] | False |
| harmony | 0.983 | [0.978, 1.000] | True |

Ceiling gap closed: weighted_fidelity +1.23, retention_top +1.03, retention_inner +1.69, retention_bass +1.06

## duo (150 movements): success = False

| Metric | arranger-v2b | rl-C-s400 | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity | 0.7992 | 0.8651 | +0.0660 [+0.0603, +0.0719] |
| unneeded_ds_per_source_note | 0.2225 | 0.2558 | +0.0333 [+0.0286, +0.0386] |
| retention_top | 0.8882 | 0.9546 | +0.0665 [+0.0499, +0.0843] |
| retention_inner | 0.6774 | 0.7529 | +0.0756 [+0.0677, +0.0830] |
| retention_bass | 0.8809 | 0.9297 | +0.0488 [+0.0362, +0.0627] |
| note_i_f1 | 0.6124 | 0.6263 | +0.0139 [+0.0078, +0.0203] |
| note_f1 | 0.8467 | 0.8771 | +0.0304 [+0.0241, +0.0367] |
| mel_top_f1 | 0.8412 | 0.8663 | +0.0251 [+0.0081, +0.0444] |
| harmony | 0.9244 | 0.9272 | +0.0028 [+0.0015, +0.0042] |
| intervention_rate | 0.2101 | 0.2162 | +0.0061 [+0.0028, +0.0094] |

| Criterion | Holds |
|---|---|
| 1_weighted_fidelity_up | True |
| 2_unneeded_ds_down | False |
| 3_interventions_down | False |
| 4_noninferior | True |
| 5_detectors_inside | False |

| Detector | Value | Fixed range | Inside |
|---|---|---|---|
| note_ratio | 0.951 | [0.848, 1.000] | True |
| doubling_rate | 0.173 | [0.131, 0.233] | True |
| polyphony_rate | 0.880 | [0.858, 0.908] | True |
| rhythmic_independence | 0.501 | [0.439, 0.574] | True |
| duration_ratio | 0.825 | [0.864, 1.000] | False |
| harmony | 0.929 | [0.921, 1.000] | True |

Ceiling gap closed: weighted_fidelity +2.05, retention_top +1.24, retention_inner +11.59, retention_bass +1.07
