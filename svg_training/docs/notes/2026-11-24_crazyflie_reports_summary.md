INTERNAL · result page of the Crazyflie flight-report summary for the STE track's Crazyflie route (CRAZYFLIE_ROUTE, task L0.14, fleet question P13) · read-only summary of the owner's reports; no flight, no training run

# Crazyflie flight reports summary (24 Nov 2026)

What this page is for: the numbers a Crazyflie drone model and a separation study could take from the owner's 40 logged
`guard_show` folders, with the source field of each. Nothing here was flown or run by this track; every number is
read from the owner's `report.json`, `meta.json`, `output.log` or `config/` files (read-only; nothing was copied,
moved or changed there). Next: [CRAZYFLIE_ROUTE](../../ste_learning/CRAZYFLIE_ROUTE.md) for what the route needs.
Terms: *Guard* and *Strike* are the two teams (the show's own parameter names are `defenders` and `attackers`);
*PID* and *Mellinger* are the two firmware controllers the show names in its start-up lines; *flown* = a flight in
which some drone had `drones.*.envelope.airborne_s` of at least 5 s.

> **Results in short** (sources in §2; limits in §4):
> 1. **Data:** 37 report.json read; 14 of the 37 never got a drone airborne for 5 s (aborted or failed at start),
>    leaving 23 flown flights and 159 drone-flights (91 Guard, 68 Strike) with tracking numbers.
> 2. **The best-fit lag splits with the controller, not with drone role** (a co-occurrence: controller, date, code revision and mocap rate 50 v 59 Hz changed together). `tracking.lag_s` median 0.58 s (Guard) and 0.56 s
>    (Strike) in the 63 PID drone-flights, 0.10 s and 0.08 s in the 62 Mellinger drone-flights; the 34 drone-flights of
>    6 Nov (controller not logged) fall in the same range (median 0.56 s). 21 PID/unlogged drone-flights (and 1 Mellinger, 22 in all) sit at 0.60 s, the top of the
>    values seen, so a search limit may be capping them. The tracking error p95 median falls from about 0.44 m to
>    0.14 m with it, while `tracking.residual.p95` stays about 0.08-0.10 m in both.
> 3. **Closest approaches were 0.34-0.90 m (median 0.40 m) per flown flight**, far under the 1.10 m filter distance
>    of the game and under the arena file's `separation.minimum` 0.80 m in 19 of 23 flights. Where `cmd_gap` was logged
>    (78 of 104 events), the commanded gap was already 0.45 m or more: the label "plan" fits all 78, "aircraft" none.
> 4. **Failure modes seen:** 8 crashed drone-flights in 8 of the 23 flown flights (3 also `tumbled`); 4 aborts of the
>    show for a drone "not following" its command (0.61-0.88 m for 0.8-0.9 s), all with PID or unlogged controller; one
>    abort for mocap lost on a drone; the largest tracking error, 2.12 m (`tracking.error.max`), was a Strike drone (cf10,
>    17 Nov 17:19, PID) with no crash flag, `battery_min` 2.74 V, in a flight aborted for "not following".

## 1. Method

- Script: `scripts/cf_reports_summary.py <folder>` (standard library and numpy; reads only; test
  `tests/test_cf_reports_summary.py` on a synthetic fixture). The tables below are its output on
  `svg_training/flight_logs/crazyflie/flight_logs_2026-11-24/flight_logs/`, with section headings renumbered.
- Show parameters (rules, defense, attack, defenders, attackers, strike_block, seed, paced) are the `-p name:=value`
  words of `meta.json` `cmdline`. The controller and speeds are the `controller` and `speeds` start-up lines of
  `output.log`; where those are absent (6 Nov flights), the column says `unlogged`. Exit status is `meta.json`
  `returncode` and `state`. Crashes and flags are `drones.<cf>.status.flags`. Aborts and results are the lines of
  `fleet.show_alarms`.
- Role: a name in the `defenders` parameter is Guard, in `attackers` is Strike. Statistics use drone-flights airborne 5 s
  or more; they are split by controller because §3 shows the lag differs by it. The second per-role table leaves out
  drone-flights with a `status.flags` entry.
- "Plan or aircraft" is a numeric rule on two fields of `fleet.closest_pair` / `fleet.close_pairs`: **plan** if
  `cmd_gap - gap` is at most the sum of the two drones' `tracking.error.p95` in that flight, **aircraft** if larger,
  **unknown** if `cmd_gap` is NaN (26 of 104 events). It compares numbers and says nothing about why they differ.
  What distance `gap` measures (3-D or not) and the threshold of `close_pairs` (largest `gap` listed is 0.50 m) are not
  stated in the reports.

## 2. Tables

### 2.1 Per flight

| start (local) | code | rules | defense | attack | G/S | strike_block | seed | paced | controller | speeds def/atk m/s | exit (state) | airborne s | crashes / flags | first ABORT or error | result line | closest pair m | close-pair events | downwash events |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-06 14:53 | eda5135 | pressure | shell | coordinated | 4/3 | - | 1 | true | unlogged | 1.00/1.00 | 130 (stopped) | 68 | cf11: crashed | *** ABORT (CONTAINMENT cf1: no mocap for 1.1 s) - landing all drones w | - | 0.64 | 0 | 0 |
| 2026-11-06 15:07 | eda5135 | pressure | shell | coordinated | 4/3 | - | 1 | true | unlogged | 1.00/1.00 | 1 (failed) | 0 | - | - | - | - | 0 | 0 |
| 2026-11-06 15:07 | eda5135 | pressure | shell | coordinated | 4/3 | - | 1 | true | unlogged | 1.00/1.00 | 1 (failed) | 0 | - | - | - | - | 0 | 0 |
| 2026-11-06 15:08 | eda5135 | pressure | shell | coordinated | 4/3 | - | 1 | true | unlogged | 1.00/1.00 | 130 (stopped) | 40 | - | *** ABORT (CONTAINMENT cf10: 0.64 m from where it was commanded for 0. | - | 0.39 | 5 | 0 |
| 2026-11-06 15:13 | 0046179 | pressure | shell | coordinated | 4/3 | - | 1 | true | unlogged | 1.00/1.00 | 0 (done) | 92 | - | - | ATTACK WINS -- 1 strike(s) (t+11.7s, strikes 1, do | 0.35 | 7 | 3 |
| 2026-11-06 15:19 | 15df7f6 | pressure | shell | coordinated | 4/3 | - | 1 | true | unlogged | 1.00/1.00 | 130 (stopped) | 18 | cf1: crashed,tumbled | *** ABORT (operator asked to land) - landing all drones where they are | - | 0.79 | 0 | 0 |
| 2026-11-06 15:27 | 15df7f6 | pressure | shell | coordinated | 4/3 | - | 1 | true | unlogged | 1.00/1.00 | 0 (done) | 116 | - | - | DEFENSE WINS -- no attacker left in play (t+12.4s, | 0.34 | 8 | 2 |
| 2026-11-17 15:28 | 637c534 | pressure | shell | coordinated | 4/3 | - | 1 | true | unlogged | - | -9 (stopped) | 0 | - | - | - | - | 0 | 0 |
| 2026-11-17 15:29 | 637c534 | pressure | shell | coordinated | 4/3 | - | 1 | true | unlogged | - | -9 (stopped) | 0 | - | - | - | - | 0 | 0 |
| 2026-11-17 15:40 | 637c534 | pressure | shell | coordinated | 4/3 | - | 1 | true | pid | 0.60/0.60 | 1 (failed) | 0 | - | - | - | - | 0 | 0 |
| 2026-11-17 15:49 | 637c534 | pressure | shell | coordinated | 4/3 | - | 1 | true | pid | 0.60/0.60 | 1 (failed) | 0 | - | - | - | - | 0 | 0 |
| 2026-11-17 15:57 | 637c534 | pressure | shell | coordinated | 4/3 | - | 1 | true | unlogged | - | -9 (stopped) | 0 | - | - | - | - | 0 | 0 |
| 2026-11-17 16:24 | 637c534 | pressure | shell | coordinated | 4/3 | - | 1 | true | pid | 0.60/0.60 | 130 (stopped) | 2 | - | *** ABORT (no fresh VIP pose at the start) - landing all drones where  | - | - | 0 | 0 |
| 2026-11-17 16:31 | 637c534 | pressure | shell | coordinated | 4/3 | - | 1 | true | pid | 0.60/0.60 | 0 (done) | 121 | cf4: crashed | - | ATTACK WINS -- 1 strike(s) (t+36.3s, strikes 1, do | 0.39 | 6 | 0 |
| 2026-11-17 16:54 | 637c534 | pressure | shell | coordinated | 4/3 | - | 1 | true | pid | 0.60/0.60 | 130 (stopped) | 3 | - | *** ABORT (no fresh VIP pose at the start) - landing all drones where  | - | - | 0 | 0 |
| 2026-11-17 17:19 | 637c534 | pressure | shell | coordinated | 4/3 | - | 1 | true | pid | 0.60/0.60 | 130 (stopped) | 44 | - | *** ABORT (CONTAINMENT cf10: 0.88 m from where it was commanded for 0. | - | 0.50 | 1 | 0 |
| 2026-11-17 17:25 | 637c534 | pressure | shell | coordinated | 4/3 | - | 1 | true | pid | 0.60/0.60 | 0 (done) | 83 | - | - | ATTACK WINS -- no defender left in play (t+8.6s, s | 0.40 | 5 | 0 |
| 2026-11-17 17:31 | 637c534 | pressure | shell | coordinated | 4/3 | - | 3 | true | pid | 1.00/1.00 | 1 (failed) | 0 | - | - | - | - | 0 | 0 |
| 2026-11-17 17:33 | 637c534 | pressure | shell | coordinated | 4/3 | - | 3 | true | pid | 1.00/1.00 | 0 (done) | 63 | - | - | ATTACK WINS -- 1 strike(s) (t+13.7s, strikes 1, do | 0.39 | 8 | 0 |
| 2026-11-17 17:35 | 637c534 | pressure | hunter | coordinated | 4/3 | - | 3 | true | pid | 1.00/1.00 | 0 (done) | 52 | - | - | ATTACK WINS -- no defender left in play (t+6.7s, s | 0.39 | 5 | 1 |
| 2026-11-17 17:38 | 637c534 | pressure | shell | coordinated | 4/3 | - | 69 | true | pid | 1.00/1.00 | 1 (failed) | 0 | - | - | - | - | 0 | 0 |
| 2026-11-17 17:39 | 637c534 | pressure | shell | coordinated | 4/3 | - | 69 | true | pid | 1.00/1.00 | 0 (done) | 38 | cf2: crashed | - | ATTACK WINS -- no defender left in play (t+11.2s,  | 0.37 | 7 | 3 |
| 2026-11-17 18:00 | 637c534 | pressure | shell | coordinated | 4/3 | - | 42 | true | pid | 1.00/1.00 | 130 (stopped) | 48 | - | *** ABORT (CONTAINMENT cf10: 0.66 m from where it was commanded for 0. | - | 0.75 | 0 | 0 |
| 2026-11-17 18:02 | 637c534 | pressure | shell | coordinated | 4/3 | - | 42 | true | pid | 1.00/1.00 | 130 (stopped) | 43 | - | *** ABORT (CONTAINMENT cf11: 0.61 m from where it was commanded for 0. | - | 0.36 | 5 | 0 |
| 2026-11-23 13:38 | 3c8a468 | pressure | shell | coordinated | 4/3 | - | 42 | true | pid | 1.00/1.00 | 1 (failed) | 0 | - | - | - | - | 0 | 0 |
| 2026-11-23 13:39 | 3c8a468 | pressure | shell | coordinated | 4/3 | - | 42 | true | pid | 1.00/1.00 | 0 (done) | 98 | - | - | ATTACK WINS -- 1 strike(s) (t+8.5s, strikes 1, dow | 0.40 | 6 | 1 |
| 2026-11-23 13:57 | 3c8a468 | pressure | shell | coordinated | 4/3 | - | 42 | true | mellinger | 1.00/1.00 | 0 (done) | 88 | cf10: crashed,tumbled | - | ATTACK WINS -- 1 strike(s) (t+14.5s, strikes 1, do | 0.39 | 4 | 0 |
| 2026-11-23 14:08 | 3c8a468 | pressure | hunter | coordinated | 4/3 | - | 42 | true | mellinger | 1.00/1.00 | 130 (stopped) | 11 | cf2: crashed,tumbled | *** ABORT (Ctrl-C) - landing all drones where they are *** | - | 0.90 | 0 | 0 |
| 2026-11-23 14:13 | 3c8a468 | pressure | shell | wolfpack | 4/3 | - | 42 | true | mellinger | 1.00/1.00 | 0 (done) | 104 | - | - | ATTACK WINS -- 1 strike(s) (t+8.8s, strikes 1, dow | 0.36 | 7 | 0 |
| 2026-11-23 14:41 | 3c8a468 | pressure | shell | coordinated | 4/3 | - | 42 | true | mellinger | 1.00/1.00 | 1 (failed) | 0 | - | - | - | - | 0 | 0 |
| 2026-11-23 14:41 | 3c8a468 | pressure | shell | coordinated | 4/3 | - | 42 | true | mellinger | 1.00/1.00 | 0 (done) | 106 | - | - | DEFENSE WINS -- no attacker left in play (t+17.0s, | 0.39 | 7 | 0 |
| 2026-11-23 15:22 | 3c8a468 | pressure | shell | coordinated | 4/3 | 0.8 | 42 | true | mellinger | - | 254 (stopped) | 0 | - | 2026-11-23T15:22:43.290 Traceback (most recent call last): | - | - | 0 | 0 |
| 2026-11-23 16:38 | 3c8a468 | pressure | shell | coordinated | 4/3 | 0.8 | 42 | true | mellinger | 1.00/1.00 | 130 (stopped) | 20 | - | *** ABORT (VIP pose lost for 2.0 s) - landing all drones where they ar | - | 0.89 | 0 | 0 |
| 2026-11-23 16:42 | 3c8a468 | pressure | shell | coordinated | 4/3 | 0.8 | 42 | true | mellinger | 1.00/1.00 | 130 (stopped) | 56 | - | *** ABORT (Ctrl-C) - landing all drones where they are *** | - | 0.87 | 0 | 0 |
| 2026-11-23 16:45 | 3c8a468 | pressure | shell | coordinated | 4/3 | 0.8 | 42 | true | mellinger | 1.00/1.00 | 130 (stopped) | 36 | cf10: crashed | *** ABORT (Ctrl-C) - landing all drones where they are *** | - | 0.80 | 0 | 0 |
| 2026-11-23 16:49 | 3c8a468 | pressure | shell | coordinated | 4/3 | 0.8 | 42 | true | mellinger | 1.00/1.00 | 0 (done) | 80 | - | - | DEFENSE WINS -- no attacker left in play (t+15.3s, | 0.40 | 8 | 0 |
| 2026-11-24 14:47 | aa4c3c8 | pressure | shell | coordinated | 4/3 | 0.8 | 42 | true | mellinger | 1.00/1.00 | 0 (done) | 98 | cf4: crashed | - | DEFENSE WINS -- no attacker left in play (t+16.6s, | 0.41 | 8 | 0 |

G/S = number of names in `defenders` / `attackers` (the show's own parameter names; Guard / Strike here). airborne s = the largest `drones.*.envelope.airborne_s`. controller and speeds = the show's start-up lines in output.log ('unlogged' = no such line, 6 Nov flights) or the `controller` parameter; they are the show's settings, read from the log, not from report.json.

### 2.2 config/crazyflies.yaml firmware settings (uncommented lines)

- {"controller": "1", "enHighLevel": "1", "estimator": "2", "extPosStdDev": "1e-3", "extQuatStdDev": "0.5e-1"}: 37 flights, folders dated 2026-11-06, 2026-11-17, 2026-11-23, 2026-11-24

### 2.3 Per role: all drone-flights airborne >= 5 s

| role / controller | drone-flights | err mean (weighted) m | err p95 median / max m | err max, max m | lag s median [min-max] | lag < 0.3 / >= 0.3 | resid p95 median / max m | cmd Hz median [min-max] | mocap Hz median | mocap drops median / max | battery start median V | battery min, lowest V | battery end median V |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| guard / mellinger | 35 | 0.053 | 0.144 / 0.210 | 0.320 | 0.10 [0.00-0.60] | 34 / 1 | 0.096 / 0.137 | 16.7 [16.0-19.9] | 59.0 | 4 / 10 | 4.05 | 3.27 | 3.83 |
| strike / mellinger | 27 | 0.044 | 0.128 / 0.204 | 0.369 | 0.08 [0.00-0.14] | 27 / 0 | 0.088 / 0.138 | 16.7 [16.0-19.9] | 59.0 | 4 / 10 | 4.11 | 3.39 | 3.90 |
| guard / pid | 36 | 0.133 | 0.442 / 0.731 | 0.959 | 0.58 [0.54-0.60] | 0 / 36 | 0.083 / 0.228 | 16.6 [16.3-20.0] | 50.0 | 4 / 20 | 4.06 | 3.22 | 3.89 |
| strike / pid | 27 | 0.174 | 0.433 / 1.877 | 2.121 | 0.56 [0.00-0.60] | 1 / 26 | 0.082 / 1.877 | 19.9 [16.3-20.0] | 50.0 | 4 / 20 | 3.94 | 2.74 | 3.75 |
| guard / unlogged | 20 | 0.128 | 0.452 / 0.560 | 0.657 | 0.56 [0.00-0.60] | 4 / 16 | 0.083 / 0.114 | 16.7 [15.5-19.8] | 50.0 | 4 / 9 | 3.93 | 3.30 | 3.77 |
| strike / unlogged | 14 | 0.141 | 0.507 / 0.568 | 0.671 | 0.55 [0.00-0.60] | 2 / 12 | 0.086 / 0.099 | 16.4 [15.6-19.7] | 50.0 | 4 / 9 | 3.94 | 3.19 | 3.73 |

### 2.4 Per role: same, leaving out drone-flights with a `status.flags` entry (crashed, tumbled)

| role / controller | drone-flights | err mean (weighted) m | err p95 median / max m | err max, max m | lag s median [min-max] | lag < 0.3 / >= 0.3 | resid p95 median / max m | cmd Hz median [min-max] | mocap Hz median | mocap drops median / max | battery start median V | battery min, lowest V | battery end median V |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| guard / mellinger | 34 | 0.052 | 0.144 / 0.210 | 0.320 | 0.10 [0.00-0.60] | 33 / 1 | 0.095 / 0.137 | 16.6 [16.0-19.9] | 59.0 | 4 / 10 | 4.04 | 3.27 | 3.83 |
| strike / mellinger | 25 | 0.044 | 0.128 / 0.204 | 0.369 | 0.10 [0.00-0.14] | 25 / 0 | 0.088 / 0.138 | 16.7 [16.0-19.9] | 59.0 | 4 / 10 | 4.11 | 3.39 | 3.90 |
| guard / pid | 34 | 0.133 | 0.442 / 0.731 | 0.959 | 0.58 [0.54-0.60] | 0 / 34 | 0.083 / 0.228 | 16.6 [16.3-20.0] | 50.0 | 4 / 20 | 4.06 | 3.22 | 3.89 |
| strike / pid | 27 | 0.174 | 0.433 / 1.877 | 2.121 | 0.56 [0.00-0.60] | 1 / 26 | 0.082 / 1.877 | 19.9 [16.3-20.0] | 50.0 | 4 / 20 | 3.94 | 2.74 | 3.75 |
| guard / unlogged | 19 | 0.128 | 0.463 / 0.560 | 0.657 | 0.56 [0.00-0.60] | 3 / 16 | 0.083 / 0.114 | 16.9 [15.5-19.8] | 50.0 | 4 / 9 | 3.94 | 3.30 | 3.79 |
| strike / unlogged | 13 | 0.149 | 0.508 / 0.568 | 0.671 | 0.56 [0.00-0.60] | 1 / 12 | 0.086 / 0.095 | 16.4 [15.6-19.7] | 50.0 | 4 / 9 | 3.94 | 3.19 | 3.74 |

Field sources: `tracking` = `drones.<cf>.tracking.error.{mean,p95,max}` (commanded position vs mocap at the same instant);
`lag` = `tracking.lag_s` (the delay that best lines them up); `resid` = `tracking.residual.p95`; `cmd Hz` =
`commands.hz`; `mocap` = `mocap.hz` and `mocap.dropouts`; battery = `status.battery_{start,min,end}`; pairs = `fleet.closest_pair`
and `fleet.close_pairs` (`gap`, `cmd_gap`, `dz`).

### 2.5 Closest pairs (fleet.closest_pair and fleet.close_pairs of flown flights)

| pair kind | events | gap m min / median / p95 | cmd_gap m min / median | cmd_gap - gap, median / p95 m | label plan | label aircraft | label unknown (no cmd_gap) |
|---|---|---|---|---|---|---|---|
| guard-guard | 32 | 0.36 / 0.44 / 0.49 | 0.46 / 0.51 | 0.09 / 0.26 | 24 | 0 | 8 |
| guard-strike | 40 | 0.34 / 0.44 / 0.49 | 0.45 / 0.49 | 0.08 / 0.32 | 27 | 0 | 13 |
| strike-strike | 32 | 0.35 / 0.45 / 0.88 | 0.45 / 0.49 | 0.06 / 0.30 | 27 | 0 | 5 |
| ALL | 104 | 0.34 / 0.44 / 0.74 | 0.45 / 0.50 | 0.07 / 0.31 | 78 | 0 | 26 |

Label rule (`classify_pair`): 'plan' if cmd_gap - gap <= the sum of the two drones' tracking.error.p95 in that flight, else 'aircraft'. It compares two reported numbers; it does not say why they differ.

#### Closest pair of each flown flight

| start | pair | gap m | cmd_gap m | dz m | label |
|---|---|---|---|---|---|
| 2026-11-06T14:53 | cf10/cf11 | 0.64 | 0.72 | +0.06 | plan |
| 2026-11-06T15:08 | cf10/cf11 | 0.39 | 0.45 | +0.00 | plan |
| 2026-11-06T15:13 | cf10/cf11 | 0.35 | 0.46 | -0.00 | plan |
| 2026-11-06T15:19 | cf11/cf12 | 0.79 | - | -0.01 | unknown |
| 2026-11-06T15:27 | cf2/cf12 | 0.34 | - | -0.01 | unknown |
| 2026-11-17T16:31 | cf2/cf12 | 0.39 | - | -0.00 | unknown |
| 2026-11-17T17:19 | cf11/cf12 | 0.50 | - | -0.01 | unknown |
| 2026-11-17T17:25 | cf10/cf11 | 0.40 | 0.45 | -0.01 | plan |
| 2026-11-17T17:33 | cf1/cf2 | 0.39 | 0.48 | -0.14 | plan |
| 2026-11-17T17:35 | cf1/cf4 | 0.39 | - | -0.03 | unknown |
| 2026-11-17T17:39 | cf1/cf4 | 0.37 | - | +0.15 | unknown |
| 2026-11-17T18:00 | cf11/cf12 | 0.75 | - | -0.02 | unknown |
| 2026-11-17T18:02 | cf2/cf4 | 0.36 | - | +0.10 | unknown |
| 2026-11-23T13:39 | cf11/cf12 | 0.40 | 0.46 | +0.02 | plan |
| 2026-11-23T13:57 | cf1/cf2 | 0.39 | 0.47 | +0.00 | plan |
| 2026-11-23T14:08 | cf11/cf12 | 0.90 | - | -0.00 | unknown |
| 2026-11-23T14:13 | cf1/cf3 | 0.36 | 0.53 | +0.01 | plan |
| 2026-11-23T14:41 | cf4/cf11 | 0.39 | 0.49 | +0.10 | plan |
| 2026-11-23T16:38 | cf11/cf12 | 0.89 | 0.91 | +0.00 | plan |
| 2026-11-23T16:42 | cf11/cf12 | 0.87 | 0.92 | -0.00 | plan |
| 2026-11-23T16:45 | cf11/cf12 | 0.80 | - | -0.02 | unknown |
| 2026-11-23T16:49 | cf1/cf3 | 0.40 | 0.46 | +0.08 | plan |
| 2026-11-24T14:47 | cf1/cf3 | 0.41 | 0.50 | +0.12 | plan |

## 3. What the numbers say

- **Flights.** Of 37 reports, 23 flown: 13 ended `exit 0 (done)`, 10 `exit 130 (stopped)` by an ABORT line or Ctrl-C.
  The 14 others are `exit 1`, `-9`, `254` or aborts within 2-3 s ("no fresh VIP pose at the start"; one Python traceback on
  23 Nov 15:22). Three more folders hold only `guard_trace.csv` (no report). Of the 13 finished, the result line reads
  `ATTACK WINS` in 9 and `DEFENSE WINS` in 4 (`fleet.show_alarms`). The conditions changed between flights (speeds
  0.6 / 1.0 m/s, controller, `strike_block` 0.8 from 23 Nov 15:22, three seeds, and `defense:=hunter` or
  `attack:=wolfpack` once each), so these are not win rates.
- **Controller and lag.** The 14 flown flights with `controller pid` or `unlogged` (6 Nov to 23 Nov 13:39) show
  `lag_s` of 0.3 s or more in 90 of 97 drone-flights (the 7 below 0.3 s are in three flights: 6 Nov 14:53 (3 drones), 6 Nov 15:19 (3) and 17 Nov 17:19 (1)); all 9 flown flights from 23 Nov 13:57 on (`controller mellinger`, "switched
  for this show, PID restored after") show 0.00-0.14 s for 61 of 62 drone-flights (one Guard drone-flight 0.60 s). The
  same `config/crazyflies.yaml` (`stabilizer.controller: 1`, the firmware default) was present in all 37; the switch is
  named by the show's start-up line and the `controller:=mellinger` parameter, not by that file. Other things changed
  at the same time or nearby (mocap rate median 59 Hz in the Mellinger flights against 50 Hz, the speeds line, the
  code revision), so this page does not say the controller alone is the cause.
- **Tracking error.** Guard, PID: mean (weighted by `tracking.samples`) 0.133 m, p95 median 0.442 m, max 0.959 m. Strike,
  PID: 0.174 m, 0.433 m, 2.121 m (the 2.12 m is one crashed drone). Guard, Mellinger: 0.053 m, 0.144 m, 0.320 m.
  Strike, Mellinger: 0.044 m, 0.128 m, 0.369 m. The residual after the best lag (`resid p95`) is about 0.08-0.10 m
  in every group: the error is likely mostly a delay in the PID flights (an inference from the lag fit and the residual, not measured directly).
- **Rates.** `commands.hz` median 16.6-19.9 (range 15.5-20.0), with `commands.stalls` median 2 per drone-flight, at most 47,
  longest `commands.longest_stall_s` 0.99 s. `mocap.hz` 50.0 (PID/unlogged) and 59.0 (Mellinger) median;
  `mocap.dropouts` median 4, at most 20 per drone-flight.
- **Battery.** `status.battery_start` median 3.93-4.11 V, `battery_min` as low as 2.74 V (a Strike drone-flight, PID;
  3.22 V lowest Guard), `battery_end` median 3.73-3.90 V.
- **Separation.** Per flown flight `fleet.closest_pair.gap` 0.34-0.90 m, median 0.40 m; 16 of 23 flights under
  0.50 m. Over the 104 events: gap min / median / p95 0.34 / 0.44 / 0.74 m; `cmd_gap` min / median 0.45 / 0.50 m;
  `cmd_gap - gap` median 0.07 m, p95 0.31 m. Pair kinds: Guard-Guard 32, Guard-Strike 40, Strike-Strike 32 events,
  all with a median gap near 0.44 m. The commanded gap was below the arena file's `separation.minimum` 0.80 m
  (`config/arena.yaml`; `tracking_margin` 0.10 m) in 73 of the 78 events with a `cmd_gap`. `mocap_jump_nearby` is false in all 104 events.
- **Downwash.** 10 events in `fleet.downwash.events` over the flown flights: `sink` median 0.20 m, max 0.35 m, horizontal
  `across` 0.15-0.86 m, `dz` 0.22-1.04 m (events listed; no firmware effort figures in most flights: "events from
  mocap only").
- **Aborts and crashes.** 4 aborts say "CONTAINMENT cf10 (3 times) / cf11: 0.61-0.88 m from where it was commanded for
  0.8-0.9 s -- not following" (6 Nov 15:08, 17 Nov 17:19, 18:00, 18:02); one "CONTAINMENT cf1: no mocap for 1.1 s"
  (6 Nov 14:53, with cf11 flagged crashed in the same flight); "VIP pose lost for 2.0 s" once. Crashed: cf11, cf1
  (also tumbled; `envelope.top_speed` 4.16 m/s in that flight), cf4 (17 Nov 16:31 and 24 Nov), cf2 (17 Nov and 23 Nov,
  the latter tumbled), cf10 (23 Nov 13:57 tumbled, 23 Nov 16:45). Strike and Guard names both appear.

## 4. What this gives the Crazyflie route

The PID and Mellinger columns below differ in controller, date, code revision and mocap rate together; read them as two
groups of flights, not as the controller's effect alone.

**Candidate numbers for a Crazyflie drone model** (all from the owner's flights; speeds below 1.2 m/s, `envelope.top_speed`
about 1.0-1.5 m/s in normal flights; no model was fitted here):

| Quantity | PID or unlogged flights | Mellinger flights | Source field |
|---|---|---|---|
| best-fit lag, median (range) | 0.56-0.58 s (0.54-0.60) | 0.08-0.10 s (0.00-0.14, one 0.60) | `tracking.lag_s` |
| tracking error mean, weighted | 0.13-0.17 m | 0.04-0.05 m | `tracking.error.mean`, `tracking.samples` |
| tracking error p95, median over drone-flights | 0.43-0.51 m | 0.13-0.14 m | `tracking.error.p95` |
| residual p95 after the lag, median | 0.08-0.09 m | 0.09-0.10 m | `tracking.residual.p95` |
| command rate, median | 16.4-19.9 Hz | 16.7 Hz | `commands.hz` |
| mocap rate | 50 Hz | 59 Hz | `mocap.hz` |

The route page's 0.56 s "logged Crazyflie" lag matches the PID flights here; the Mellinger flights show about a fifth of it.
A tier-1 delay cell for a Mellinger Crazyflie (about 0.1 s) would sit near the Starling's 0.148 s; the 0.48-0.56 s band
describes PID. The lag is a fitted delay between commanded and measured position under show motion (commanded
speeds up to 1.0 m/s), not a measured step response.

**Separation statistics:** the two teams' Crazyflies were flown to 0.34-0.50 m apart in 16 of 23 flights, mostly by
commands (`cmd_gap` 0.45 m and up), with no collision-avoidance floor at the Starling's 1.10 m. The route's
1.10 m filter distance was not flown here. A game at 1.10 m would need the planner's floors above these.

**Failure modes seen:** crashes (8 drone-flights, 3 tumbled); a drone not following its command for about 0.8 s
(4 aborts, PID or unlogged controller); mocap loss; command stalls up to 0.99 s; battery down to 2.74 V in one
drone-flight; `Received wrong latency id` and `High latency` warnings in the thousands per flight (`fleet.warnings`, counts
only). No mechanism is claimed for any of them.

**What this does not give:**
- no step pushes or system-identification inputs: a model fitted to these logs is a fit to show motion with
  the planner's own commands, with lag values that appear on a 0.02 s grid (read from the reported values; the reports do not state the grid) whose top end (0.60 s) is reached by 22 drone-flights;
- no controller gains: `config/crazyflies.yaml` names only `stabilizer.controller: 1` (PID), `estimator: 2` (Kalman),
  `extPosStdDev` 1e-3 and `extQuatStdDev` 0.05; the Mellinger setting comes from the show's log line, with no gains
  recorded;
- one drone type in one room (a mocap room with the DJI as VIP), a 4-vs-3 team in every flight, seeds 1, 3, 42 and 69;
- no downwash effort figures in most flights, and no Starling-side data;
- the flights changed several settings at once, so effects of the controller, speed, code revision or
  `strike_block` are not separated. The three trace-only folders and `guard_trace.csv`/`bag/` were not read (the `bag/`
  folders are the largest; a rate or latency study would start there).

## 5. Reproduce

```
cd svg_training
python scripts/cf_reports_summary.py ~/AirStack-starling-max2/svg_training/flight_logs/crazyflie/flight_logs_2026-11-24/flight_logs
unset PYTHONPATH; CUDA_VISIBLE_DEVICES="" PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python -m pytest -q -p no:cacheprovider tests/test_cf_reports_summary.py
```

Reviewed by: none yet (draft). Per ruling R22 a result on a reader page needs two reviewers; this is an internal note.
