INTERNAL · survey of the real-flight logs the owner added on 24 Nov 2026, against the planned-pushes flight (NEAR-962) that STE task L1.3 needs for its run of record · [S1_RESULTS, what the owner needs to do next](../S1_RESULTS.md#what-the-owner-needs-to-do-next)

# Flight logs of 24 Nov 2026: survey

Read-only survey (an agent's reading of the bags with a pure-Python mcap reader; one spot check by the lead: the second
bag's duration 152.9 s). The logs are owner data in `~/AirStack-starling-max2/svg_training/flight_logs/` (untracked,
1.5 GB, not in git). Real flight; not the training simulator.

## Starling bags (`starlingmax2/bags/`)

| Bag | What it holds | Use for L1.3 |
|---|---|---|
| `svg_20261124_072821` (370 s) | no flight: both drones disarmed on the ground (max height 0.07 m); commander had `figure_eight` loaded, never started; no setpoints | none |
| `svg_20261124_073433` (153 s) | both drones flew the `figure_eight` mission, about 118 s airborne each, max height 3.6 / 3.3 m; offboard trajectory setpoints at 20 Hz; commander status: `scenario_speed_mps` 2.0, CBF safety radius 0.55 m, `max_speed_mps` 3.0, teleop cap 0.5; safety filter acted about 56 % of the mission; one continuous 97 s leg, setpoint speed median about 1.8 m/s (0.9–3.0), measured horizontal peaks 2.69 / 2.35 m/s; position logged at 100–120 Hz | held-out check of high-speed tracking only: no from-rest pushes, no holds, the filter reshaped the commands |
| `svg_20261112_094546`, `hover_step_20261029_074525` | the 12 Nov flight used by S1, and an earlier hover-step bag | already known; not re-surveyed |

Against the planned-pushes list (S1_RESULTS items 1–7): setpoint and position rates met (2); both drones flown (5);
missing the stick-command topics `/svg/drone_N/teleop_command` (1), from-rest pushes with 3–5 s holds (3), single-axis
steps at 0.75 and 1.0 m/s (4), the config file name, laptop time-sync state, PX4 build and `MPC_XY_VEL_MAX` (6), and a
filter-off flight for one drone (7).

**Verdict:** L1.3's run of record still waits on the planned-pushes flight (NEAR-962). For that flight, in its own bag:
one drone flown alone with the safety filter on (owner, R33: no filter-off flight; with the other drone disarmed on the ground the filter has no pair to act on); single-axis pushes from rest at 0.25, 0.5, 0.75 and 1.0 m/s, held 3–4 s (some
5 s), 3 s rest; record the stick-command topics; write down the config file, PX4 build, `MPC_XY_VEL_MAX` and the ledger
number.

## Crazyflie logs (`crazyflie/flight_logs_2026-11-24/flight_logs/`)

40 `guard_show` flights, 6–24 Nov 2026, each with `report.txt`, `report.json`, a bag and a trace. The latest
(`20261124_144732_guard_show`, 4 defenders, 3 attackers, `rules:=pressure`) reports per-drone tracking error about
0.06 m mean and 0.25–0.32 m max, a best-fit lag of 0.10–0.12 s, and closest pairs 0.41–0.49 m. Material for the
Crazyflie route (`ste_learning/CRAZYFLIE_ROUTE.md`), not for the Starling fit.
