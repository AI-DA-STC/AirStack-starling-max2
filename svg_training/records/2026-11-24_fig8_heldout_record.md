Observed in flight logs: real drones, 24 November 2026 rosbag (figure eight, two drones); tier 1's drone model replayed on the CPU, not refitted; no simulator run, no training result

# 2026-11-24_fig8_heldout record

Result: **INFO** (no gates). Ledger row: added with the results.

## Purpose

Check tier 1's drone model (the fitted PX4 response, `params/real_exploratory_v0.toml`, response delay 0.1482 s) against
a flight it never saw and at speeds it was never fitted at: the 24 Nov figure-eight mission, both drones, from the
commander's `start` to its `hold` (about 36.9–131.3 s in the survey's time,
[flight-log survey](../docs/notes/2026-11-24_flight_logs_survey.md)). The setpoint PX4 received is replayed through the
model and compared with each real drone's own velocity estimate, separately where the safety filter listed the drone
and where it did not. Information only: no parameter changes (STANDARDS §5 rule 10: the run of record of the `real`
set waits on the planned-pushes flight NEAR-962).

## Pre-registered reading (written and committed before any replay of the real bag)

Before this section was committed the bag was opened only to list its topics and to check that the fields exist
(setpoint speed reaches 3.0 m/s; the logged acceleration field is finite). No replay was run.

**Status.** INFO only. No gate, no PASS or FAIL, no verdict on the model. Nothing under `params/` changes, whatever the
numbers. A reading outside the 12 Nov range is a reason to put faster pushes into the NEAR-962 flight plan, not a refit.

**Primary method** (`scripts/fig8_check.py`, which reuses `scripts/bag_check.py`'s reader, setpoint rules, baselines and
shift search, so the numbers sit beside the 12 Nov check like for like):
- window per drone: first `/svg/commander_status` with last command `start` to the first after it with `hold`, on
  bag_check's time zero (first setpoint or local-position message; 0.39 s after the bag's first message);
- setpoint (position, speed) held onto a 0.01 s grid; acceleration feed-forward derived from the held speed setpoint
  (as the model was fitted and as the 12 Nov check ran); the `[px4]` table as written; started once from the measured
  position and speed at the window start and flown across the whole window (one open-loop window of about 94 s);
- horizontal only (x east, y north): the model has no fitted vertical channel; estimate error (L1.7) off, so the replay
  is deterministic (its velocity sigma, 0.022 m/s from T63, is small against the errors expected here);
- each measured sample is labelled from the latest `/svg/cbf_active` message (comma-separated names, exact name match):
  "filter on" when the drone's own name is listed, "filter off" when not, unknown when no message in the last 0.25 s.
  The setpoint is the commander's output after the filter in both classes, so the split reads PX4's response to
  filter-shaped setpoints, not the filter itself.

**Metrics and their reading words.** Per drone and per subset (all, filter on, filter off):

| Metric | 12 Nov check's range (from its record) |
|---|---|
| model velocity RMS, x axis, y axis, and both axes together (bag_check's convention) | 0.029–0.120 m/s (pooled 0.029 drone_1, 0.093 drone_2; worst leg 0.120) |
| best extra shift of the model, searched over [−0.10, 0.30] s (best-fit lag beyond the model's own delay) | −0.10 (drone_2, at the search edge) to +0.06 s (drone_1) |
| RMS after that shift (residual after lag) | 0.028–0.085 m/s |
| model RMS divided by the setpoint-speed baseline RMS | 0.78–1.03 (0.029/0.037, 0.093/0.090) |

Each number gets exactly one of: "inside the 12 Nov check's range" (low ≤ x ≤ high) or "outside the 12 Nov check's range
(above / below)". No other judgement word.

**Caveats stated in advance.**
- Speed: the model was fitted at up to 0.5 m/s (13 Nov) and the 12 Nov check flew up to 0.5 m/s; this flight's setpoint
  reaches 3.0 m/s and the drones about 2.7 m/s. Every number here is outside the fit range; an absolute RMS that grows
  with speed is expected and is not by itself a model fault.
- The 12 Nov record has no per-axis numbers; per-axis RMS is set against its both-axes range (same scale: both-axes RMS
  is the root of the mean of the two axes' squares).
- One 94 s open-loop window against 12 Nov's 3–6 s legs, each started from rest.
- The 12 Nov drone_2 best shift sat on the search edge (−0.10 s). A best shift on either edge here is reported as "at the
  search edge"; the same search over [−0.30, 0.80] s is given as information.
- The measured speed is PX4's estimate, logged on the laptop after the WiFi (bag log time), as on 12 Nov.

**Information-only variants, named now:** the logged acceleration field instead of the derived one (what PX4 received);
the setpoint joined by straight lines (as the S1 fit); the model restarted every 5 s from the measured state (1 s
run-in, unscored), like bag_check's short legs; the share of time the model sits on its acceleration limit (1.72 m/s²)
or speed cap (3.0 m/s); the measured horizontal acceleration (95th percentile). They move no reading word.

## Results

Not yet run.
