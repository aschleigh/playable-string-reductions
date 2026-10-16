# Block 5 confirmatory test: control-S2b (criterion C against control-S2b; criterion B against v2b)

checker-v5, METRICS 1.5.0-draft, melody-first decoding, 145 evaluation movements (5 review movements excluded), paired 95% movement bootstrap. **Caveat:** this is the evaluation set's second confirmatory use (R46 was the first, and its result was seen); it is weaker evidence than a first look.

## trio (145 movements): criterion B = False

| control-S2b vs arranger-v2b | reference | control-S2b | Δ [95% CI] |
|---|---|---|---|
| retention_top | 0.967 | 0.995 | +0.028 [+0.018, +0.040] |
| retention_inner | 0.869 | 0.551 | -0.319 [-0.330, -0.308] |
| retention_bass | 0.961 | 0.985 | +0.023 [+0.008, +0.042] |
| harmony | 0.980 | 0.943 | -0.037 [-0.039, -0.036] |
| intervention_rate | 0.113 | 0.012 | -0.102 [-0.108, -0.096] |
| drop_rate | 0.062 | 0.191 | +0.129 [+0.122, +0.136] |
| duration_ratio | 0.930 | 0.981 | +0.051 [+0.043, +0.061] |

| Double stops per 100 notes | real parts | control-S2b | arranger-v2b |
|---|---|---|---|
| violin | 6.1 | 0.7 [0.5, 0.8] | 24.5 [23.2, 25.8] |
| viola | 5.1 | 2.5 [2.2, 2.9] | 17.9 [17.1, 18.7] |
| cello | 2.5 | 1.9 [1.4, 2.7] | 5.1 [4.4, 6.0] |

Mean idiomatic z: control-S2b -0.65, arranger-v2b -1.46

| Criterion B | Holds |
|---|---|
| 1_double_stops_at_real_levels | False |
| 2_melody_noninferior | True |
| 3_interventions_down | True |
| 4_no_rhythm_rewriting | True |

## duo (145 movements): criterion B = True

| control-S2b vs arranger-v2b | reference | control-S2b | Δ [95% CI] |
|---|---|---|---|
| retention_top | 0.953 | 0.973 | +0.020 [+0.009, +0.032] |
| retention_inner | 0.537 | 0.030 | -0.507 [-0.529, -0.486] |
| retention_bass | 0.866 | 0.903 | +0.037 [+0.014, +0.061] |
| harmony | 0.931 | 0.857 | -0.074 [-0.077, -0.071] |
| intervention_rate | 0.220 | 0.011 | -0.209 [-0.220, -0.198] |
| drop_rate | 0.217 | 0.426 | +0.210 [+0.201, +0.218] |
| duration_ratio | 0.919 | 0.974 | +0.055 [+0.044, +0.067] |

| Double stops per 100 notes | real parts | control-S2b | arranger-v2b |
|---|---|---|---|
| violin | 6.1 | 0.2 [0.1, 0.2] | 27.5 [26.2, 28.7] |
| cello | 5.1 | 1.8 [1.4, 2.4] | 30.1 [29.1, 31.1] |

Mean idiomatic z: control-S2b -0.53, arranger-v2b -2.32

| Criterion B | Holds |
|---|---|
| 1_double_stops_at_real_levels | True |
| 2_melody_noninferior | True |
| 3_interventions_down | True |
| 4_no_rhythm_rewriting | True |
