RECORD · SIM — the NEAR-786 hover and 1 m step results table, moved here from HTX-R1 S5 to keep that page inside its budget. Sim-only (iron rule 9).

# Sim notes — hover and 1 m step, runs #3, #17, #18, #19 (NEAR-786)

**NEAR-786: Re-run hover and 1 m step test on the updated sim drone.** This test checks that one drone still hovers, moves 1 m and settles cleanly after the rebuild. It tests the control loop only, so the camera and cuVSLAM are off and the world makes no difference. The gates are set as a sanity bar, not a flight requirement ([thresholds](../../tools/README.md#thresholds)).

| | gate | #3 (19 Oct, old asset, 0.6 m/s, wall time) | #17 (28 Oct, n=1) | #18 (28 Oct, n=3) | #19 (29 Oct, n=3) |
|---|---|---|---|---|---|
| hover thrust | 0.12–0.20 (real 0.165) | 0.155 | 0.153 | 0.153 | 0.153 |
| PX4 s per wall s | — | — | 1.336 (est., overlay scale) | 1.324 | 1.333 |
| x overshoot, m | < 0.15 | 0.002 | 0.054 | 0.085 | 0.095 |
| x settle, s | < 3.0 | 2.75 | 2.49 | 2.47 | 2.47 |
| z overshoot, m | < 0.15 | 0.001 | 0.001 | 0.033 | 0.020 |
| z settle, s | < 3.0 | 0.75 | 2.16 | 2.50 | 2.42 |
| landed, DISARMED ×3 | yes | — | yes | yes | yes |
| verdict | | superseded | driver FAIL ×3, re-analysed PASS; drone_1 ulog lost | PASS | PASS |

Figure 2 and its reading stay on [HTX-R1](../projects/HTX-R1.md).
