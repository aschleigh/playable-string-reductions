# Confirmatory test (R46): control-S2 vs arranger-v2b, checker-v5, METRICS 1.5.0-draft

Melody-first decoding for all model systems; 145 evaluation movements (5 review movements excluded); paired 95% movement bootstrap.

## trio (145 movements): criterion B = False, criterion A = False

| Metric | arranger-v2b | control-S2 | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity_A | 0.950 | 0.920 | -0.030 [-0.037, -0.022] |
| retention_top | 0.967 | 0.994 | +0.027 [+0.017, +0.039] |
| retention_inner | 0.869 | 0.547 | -0.322 [-0.334, -0.310] |
| retention_bass | 0.961 | 0.985 | +0.023 [+0.008, +0.042] |
| unneeded_ds_per_source_note | 0.153 | 0.011 | -0.143 [-0.149, -0.136] |
| note_i_f1 | 0.739 | 0.618 | -0.121 [-0.130, -0.112] |
| note_f1 | 0.916 | 0.870 | -0.047 [-0.052, -0.040] |
| mel_top_f1 | 0.942 | 0.987 | +0.045 [+0.034, +0.058] |
| harmony | 0.980 | 0.944 | -0.036 [-0.038, -0.034] |
| intervention_rate | 0.113 | 0.013 | -0.101 [-0.106, -0.095] |
| drop_rate | 0.062 | 0.184 | +0.121 [+0.115, +0.128] |
| duration_ratio | 0.930 | 0.980 | +0.050 [+0.041, +0.059] |

| Double stops per 100 notes | real parts | arranger-v2b | control-S | control-S2 [95% CI] |
|---|---|---|---|---|
| violin | 6.1 | 24.5 | 26.8 | 0.7 [0.5, 0.8] |
| viola | 5.1 | 17.9 | 19.1 | 5.2 [4.4, 6.1] |
| cello | 2.5 | 5.1 | 4.2 | 2.1 [1.5, 2.8] |

Repeat/tremolo share: v2b 0.016, S2 0.000. Hard violations per movement: S2 masked 0.00, S2 unmasked 82.96, v2b unmasked 1209.21.

| Criterion B | Holds |
|---|---|
| 1_double_stops_at_real_levels | False |
| 2_melody_noninferior | True |
| 3_interventions_down | True |
| 4_no_rhythm_rewriting | True |

| Criterion A (2g) | Holds |
|---|---|
| 1_weighted_fidelity_up | False |
| 2_unneeded_ds_down | True |
| 3_interventions_down | True |
| 4_noninferior | False |
| 5_detectors_inside | False |

| Detector | S2 | range (v2b masked, continuity) | inside |
|---|---|---|---|
| note_ratio | 0.787 | [0.952, 1.000] | False |
| doubling_rate | 0.211 | [0.203, 0.289] | True |
| polyphony_rate | 0.894 | [0.876, 0.908] | True |
| rhythmic_independence | 0.568 | [0.507, 0.588] | True |
| duration_ratio | 0.980 | [0.922, 1.000] | True |
| harmony | 0.944 | [0.979, 1.000] | False |

## duo (145 movements): criterion B = True, criterion A = False

| Metric | arranger-v2b | control-S2 | Δ [95% CI] |
|---|---|---|---|
| weighted_fidelity_A | 0.860 | 0.795 | -0.065 [-0.073, -0.056] |
| retention_top | 0.953 | 0.971 | +0.018 [+0.007, +0.030] |
| retention_inner | 0.537 | 0.028 | -0.509 [-0.531, -0.488] |
| retention_bass | 0.866 | 0.889 | +0.023 [-0.000, +0.048] |
| unneeded_ds_per_source_note | 0.219 | 0.003 | -0.216 [-0.227, -0.206] |
| note_i_f1 | 0.612 | 0.602 | -0.010 [-0.018, -0.002] |
| note_f1 | 0.815 | 0.700 | -0.115 [-0.123, -0.107] |
| mel_top_f1 | 0.918 | 0.943 | +0.024 [+0.014, +0.035] |
| harmony | 0.931 | 0.857 | -0.074 [-0.077, -0.071] |
| intervention_rate | 0.220 | 0.010 | -0.209 [-0.220, -0.198] |
| drop_rate | 0.217 | 0.426 | +0.210 [+0.202, +0.219] |
| duration_ratio | 0.919 | 0.974 | +0.055 [+0.044, +0.067] |

| Double stops per 100 notes | real parts | arranger-v2b | control-S | control-S2 [95% CI] |
|---|---|---|---|---|
| violin | 6.1 | 27.5 | 27.7 | 0.1 [0.1, 0.1] |
| cello | 5.1 | 30.1 | 26.5 | 1.8 [1.4, 2.3] |

Repeat/tremolo share: v2b 0.019, S2 0.000. Hard violations per movement: S2 masked 0.00, S2 unmasked 60.42, v2b unmasked 2007.19.

| Criterion B | Holds |
|---|---|
| 1_double_stops_at_real_levels | True |
| 2_melody_noninferior | True |
| 3_interventions_down | True |
| 4_no_rhythm_rewriting | True |

| Criterion A (2g) | Holds |
|---|---|
| 1_weighted_fidelity_up | False |
| 2_unneeded_ds_down | True |
| 3_interventions_down | True |
| 4_noninferior | False |
| 5_detectors_inside | False |

| Detector | S2 | range (v2b masked, continuity) | inside |
|---|---|---|---|
| note_ratio | 0.552 | [0.793, 1.000] | False |
| doubling_rate | 0.137 | [0.127, 0.233] | True |
| polyphony_rate | 0.847 | [0.855, 0.908] | False |
| rhythmic_independence | 0.571 | [0.437, 0.599] | True |
| duration_ratio | 0.974 | [0.907, 1.000] | True |
| harmony | 0.860 | [0.928, 1.000] | False |
