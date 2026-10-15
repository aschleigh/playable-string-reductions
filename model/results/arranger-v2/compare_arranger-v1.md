# arranger-v2 vs arranger-v1 (checker-v4, METRICS 1.3.0-draft; 150 evaluation movements)

## trio

| System | D | Note_i F1 | Note F1 | Mel F1 | Harmony | Polyphony | Rhythmic ind. | Doubling | Note ratio | Retention top / inner / bass | Unneeded double stops per 100 notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| arranger-v1 masked | 0.00 | 0.741 | 0.931 | 0.747 | 0.982 | 0.887 | 0.582 | 0.225 | 0.961 | 0.940 / 0.907 / 0.908 | 15.9 |
| arranger-v2 masked | 0.00 | 0.887 | 0.887 | 0.622 | 0.955 | 0.880 | 0.539 | 0.239 | 0.949 | 0.840 / 0.875 / 0.954 | 12.0 |
| arranger-v1 plain | 12.18 | 0.871 | 0.991 | 0.693 | 0.999 | 0.893 | 0.579 | 0.233 | 0.989 | 0.978 / 0.998 / 1.000 | 28.3 |
| arranger-v2 plain | 11.19 | 0.972 | 0.972 | 0.703 | 0.999 | 0.897 | 0.544 | 0.249 | 1.016 | 0.995 / 0.995 / 0.995 | 27.2 |

Intervention rate (masked): arranger-v1 0.118, arranger-v2 0.104.

Paired deltas (arranger-v2 − arranger-v1), 95% CI:

| Mode | Note_i F1 | Note F1 | Mel F1 | Harmony | D |
|---|---|---|---|---|---|
| arranger | +0.102 [+0.092, +0.111] | -0.019 [-0.024, -0.015] | +0.010 [+0.002, +0.018] | +0.000 [-0.000, +0.000] | -0.988 [-1.276, -0.593] |
| arranger_masked | +0.146 [+0.132, +0.161] | -0.044 [-0.056, -0.032] | -0.124 [-0.143, -0.106] | -0.027 [-0.030, -0.025] | +0.000 [+0.000, +0.000] |

## duo

| System | D | Note_i F1 | Note F1 | Mel F1 | Harmony | Polyphony | Rhythmic ind. | Doubling | Note ratio | Retention top / inner / bass | Unneeded double stops per 100 notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| arranger-v1 masked | 0.00 | 0.608 | 0.844 | 0.660 | 0.928 | 0.871 | 0.580 | 0.139 | 0.843 | 0.864 / 0.688 / 0.874 | 26.6 |
| arranger-v2 masked | 0.00 | 0.640 | 0.827 | 0.615 | 0.906 | 0.853 | 0.518 | 0.160 | 0.861 | 0.834 / 0.759 / 0.805 | 24.0 |
| arranger-v1 plain | 20.60 | 0.707 | 0.990 | 0.689 | 0.999 | 0.892 | 0.503 | 0.179 | 0.987 | 0.975 / 0.997 / 1.000 | 49.5 |
| arranger-v2 plain | 19.49 | 0.741 | 0.970 | 0.696 | 0.998 | 0.897 | 0.482 | 0.194 | 1.012 | 0.995 / 0.995 / 0.995 | 50.0 |

Intervention rate (masked): arranger-v1 0.222, arranger-v2 0.189.

Paired deltas (arranger-v2 − arranger-v1), 95% CI:

| Mode | Note_i F1 | Note F1 | Mel F1 | Harmony | D |
|---|---|---|---|---|---|
| arranger | +0.033 [+0.029, +0.038] | -0.019 [-0.024, -0.015] | +0.007 [-0.001, +0.014] | -0.000 [-0.000, +0.000] | -1.107 [-1.518, -0.685] |
| arranger_masked | +0.032 [+0.021, +0.043] | -0.017 [-0.027, -0.007] | -0.046 [-0.065, -0.025] | -0.021 [-0.024, -0.019] | +0.000 [+0.000, +0.000] |
