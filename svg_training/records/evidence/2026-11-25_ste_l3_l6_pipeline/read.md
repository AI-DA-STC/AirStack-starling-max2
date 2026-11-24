Simulator: tier 1 training simulator; pipeline check, not for flight. Observed in the training simulator. Label: INFO. Draft until two independent reviewers have checked it (R22).

Every read is of these two trained policies (one seed each; the intervals cover the sampling of the starts only).

## Per route

| Route | Word | Why |
|---|---|---|
| velocity | **PIPELINE WORKS** | every required task as section 3 lists it |
| skills | **PIPELINE WORKS** | every required task as section 3 lists it |

## Separate reads

- Attribution, velocity: **read**; pooled row, pool + mask minus pool only: +0.005 [+0.001, +0.009], above (cells in read.json)
- Attribution, skills: **read**; pooled row, pool + mask minus pool only: +0.002 [-0.003, +0.007], not distinguishable (cells in read.json)
- Held-command arm: **read**

## Comparison (INFO)

**read**

### Guard team

velocity minus skills, Guard team, these two trained policies (one seed each; the intervals cover the sampling of the starts only); K = 6 opponent cells, 1000 starts.

| Policy | Worst cell (not z_up_info) | Rate [95 %] | Pooled row [95 %] | Against the best single choice |
|---|---|---|---|---|
| velocity | strike_straight | 0.903 [0.883, 0.920] | 0.963 [0.957, 0.970] | +0.076 [+0.062, +0.090] v guard_mark_edge: above |
| skills | strike_straight | 0.813 [0.788, 0.836] | 0.895 [0.883, 0.907] | +0.008 [+0.001, +0.014] v guard_mark_edge: above |

Worst cells, velocity against skills: **above**.

| Opponent | velocity minus skills, paired [95 %] | Word |
|---|---|---|
| strike_straight | +0.090 [+0.063, +0.117] | above |
| strike_flank | +0.094 [+0.074, +0.114] | above |
| strike_high (vertical response not fitted in tier 1) | +0.088 [+0.064, +0.112] | above |
| strike_low (vertical response not fitted in tier 1) | +0.115 [+0.091, +0.139] | above |
| strike_sacrifice | +0.019 [+0.005, +0.033] | above |
| strike_converge | +0.004 [-0.007, +0.015] | not distinguishable |

Pooled row, velocity minus skills: +0.068 [+0.055, +0.082], **above**

Choice share of the skills policy over all decisions, per opponent (described, not worded; by decision index in read.json):

- strike_straight: guard_parked_centre 0.00, guard_parked_ring 0.00, guard_mark_edge 0.70, guard_mirror 0.17, guard_field 0.12
- strike_flank: guard_parked_centre 0.00, guard_parked_ring 0.00, guard_mark_edge 0.69, guard_mirror 0.17, guard_field 0.14
- strike_high: guard_parked_centre 0.00, guard_parked_ring 0.00, guard_mark_edge 0.76, guard_mirror 0.14, guard_field 0.10
- strike_low: guard_parked_centre 0.00, guard_parked_ring 0.00, guard_mark_edge 0.55, guard_mirror 0.33, guard_field 0.12
- strike_sacrifice: guard_parked_centre 0.00, guard_parked_ring 0.00, guard_mark_edge 0.64, guard_mirror 0.14, guard_field 0.22
- strike_converge: guard_parked_centre 0.01, guard_parked_ring 0.23, guard_mark_edge 0.45, guard_mirror 0.12, guard_field 0.19

### Strike team

velocity minus skills, Strike team, these two trained policies (one seed each; the intervals cover the sampling of the starts only); K = 5 opponent cells, 1000 starts.

| Policy | Worst cell (not z_up_info) | Rate [95 %] | Pooled row [95 %] | Against the best single choice |
|---|---|---|---|---|
| velocity | guard_field | 0.079 [0.064, 0.097] | 0.373 [0.358, 0.388] | +0.030 [+0.009, +0.050] v strike_low: above |
| skills | guard_mark_edge | 0.176 [0.154, 0.201] | 0.376 [0.359, 0.393] | +0.033 [+0.021, +0.044] v strike_low: above |

Worst cells, velocity against skills: **below**.

| Opponent | velocity minus skills, paired [95 %] | Word |
|---|---|---|
| guard_field | -0.126 [-0.147, -0.105] | below |
| guard_mark_edge | +0.054 [+0.019, +0.089] | above |
| guard_parked_centre | +0.005 [-0.029, +0.039] | not distinguishable |
| guard_parked_ring | +0.002 [-0.032, +0.036] | not distinguishable |
| guard_mirror | +0.050 [+0.017, +0.083] | above |

Pooled row, velocity minus skills: -0.003 [-0.022, +0.016], **not distinguishable**

Choice share of the skills policy over all decisions, per opponent (described, not worded; by decision index in read.json):

- guard_parked_centre: strike_straight 0.00, strike_flank 0.49, strike_high 0.00, strike_low 0.51, strike_sacrifice 0.00, strike_converge 0.00
- guard_parked_ring: strike_straight 0.00, strike_flank 0.45, strike_high 0.00, strike_low 0.54, strike_sacrifice 0.00, strike_converge 0.00
- guard_mark_edge: strike_straight 0.02, strike_flank 0.44, strike_high 0.00, strike_low 0.53, strike_sacrifice 0.00, strike_converge 0.00
- guard_mirror: strike_straight 0.02, strike_flank 0.44, strike_high 0.00, strike_low 0.53, strike_sacrifice 0.00, strike_converge 0.00
- guard_field: strike_straight 0.01, strike_flank 0.43, strike_high 0.00, strike_low 0.54, strike_sacrifice 0.00, strike_converge 0.02

## What it cannot show

- one seed per route and side (no seed spread; the intervals are over the starts only)
- the 1.6 m tag only
- tier 1 training only (tier 2 only through the scripted smoke)
- no flight
- the estimate error off
- scripted opponents only (no self-play or league)
- no held-out opponent: every scored script was in the training pool, so adaptation to an unseen opponent is not tested
- the per-slot MLP and observation v0.1 of today (not the attention encoder or v0.3)
- a policy without memory or opponent identity (it can adapt only to what it observes)
- the skills route's closed-loop advantage (measured for the scripts by L4.1)
- a 550 M budget, not a budget of record

A second seed or any other read paid from the unallocated hours is labelled an added read; it never replaces a pre-registered one.
