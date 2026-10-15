# arranger-v2b vs arranger-v1 (checker-v4, METRICS 1.3.0-draft; 150 evaluation movements)

## trio

| System | D | Note_i F1 | Note F1 | Mel F1 | Harmony | Polyphony | Rhythmic ind. | Doubling | Note ratio | Retention top / inner / bass | Unneeded double stops per 100 notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| arranger-v1 masked | 0.00 | 0.741 | 0.931 | 0.747 | 0.982 | 0.887 | 0.582 | 0.225 | 0.961 | 0.940 / 0.907 / 0.908 | 15.9 |
| arranger-v2b masked | 0.00 | 0.737 | 0.916 | 0.729 | 0.979 | 0.889 | 0.554 | 0.229 | 1.000 | 0.942 / 0.900 / 0.930 | 15.3 |
| arranger-v1 plain | 12.18 | 0.871 | 0.991 | 0.693 | 0.999 | 0.893 | 0.579 | 0.233 | 0.989 | 0.978 / 0.998 / 1.000 | 28.3 |
| arranger-v2b plain | 11.12 | 0.855 | 0.980 | 0.681 | 0.999 | 0.895 | 0.560 | 0.239 | 1.026 | 0.987 / 0.996 / 1.000 | 27.7 |

Intervention rate (masked): arranger-v1 0.118, arranger-v2b 0.114.

Paired deltas (arranger-v2b − arranger-v1), 95% CI:

| Mode | Note_i F1 | Note F1 | Mel F1 | Harmony | D |
|---|---|---|---|---|---|
| arranger | -0.015 [-0.019, -0.012] | -0.012 [-0.014, -0.009] | -0.013 [-0.016, -0.010] | +0.000 [-0.000, +0.000] | -1.060 [-1.308, -0.083] |
| arranger_masked | -0.003 [-0.013, +0.007] | -0.015 [-0.023, -0.006] | -0.018 [-0.029, -0.007] | -0.002 [-0.003, -0.002] | +0.000 [+0.000, +0.000] |

## duo

| System | D | Note_i F1 | Note F1 | Mel F1 | Harmony | Polyphony | Rhythmic ind. | Doubling | Note ratio | Retention top / inner / bass | Unneeded double stops per 100 notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| arranger-v1 masked | 0.00 | 0.608 | 0.844 | 0.660 | 0.928 | 0.871 | 0.580 | 0.139 | 0.843 | 0.864 / 0.688 / 0.874 | 26.6 |
| arranger-v2b masked | 0.00 | 0.612 | 0.847 | 0.670 | 0.924 | 0.870 | 0.558 | 0.140 | 0.863 | 0.888 / 0.687 / 0.883 | 26.0 |
| arranger-v1 plain | 20.60 | 0.707 | 0.990 | 0.689 | 0.999 | 0.892 | 0.503 | 0.179 | 0.987 | 0.975 / 0.997 / 1.000 | 49.5 |
| arranger-v2b plain | 18.72 | 0.699 | 0.978 | 0.676 | 0.999 | 0.894 | 0.483 | 0.190 | 1.026 | 0.984 / 0.996 / 1.000 | 48.3 |

Intervention rate (masked): arranger-v1 0.222, arranger-v2b 0.210.

Paired deltas (arranger-v2b − arranger-v1), 95% CI:

| Mode | Note_i F1 | Note F1 | Mel F1 | Harmony | D |
|---|---|---|---|---|---|
| arranger | -0.008 [-0.012, -0.005] | -0.012 [-0.016, -0.008] | -0.013 [-0.018, -0.007] | +0.000 [-0.000, +0.001] | -1.880 [-2.253, -1.531] |
| arranger_masked | +0.005 [-0.002, +0.012] | +0.002 [-0.004, +0.010] | +0.010 [-0.007, +0.027] | -0.003 [-0.005, -0.002] | +0.000 [+0.000, +0.000] |
