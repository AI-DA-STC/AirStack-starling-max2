# Live plot window instead of a Foxglove test layout — design (2026-10-30)

**Why.** The owner never saw the live plots in runs #21 and #22. The in-container Foxglove Studio is signed in to a Foxglove account, so it keeps layouts in the account and clears its local layout folder on every start; `tools/sim.sh setup` installed the test layout into that folder, so it was gone at each run start. A second layout is also unintuitive: it has to be selected for a test and deselected before a real flight, where its missing Battery & Power panel matters. The owner chose a separate plot window opened and closed by the test driver (2026-10-30), reversing TEST_STANDARD rule 3's "live in one Foxglove" (his 2026-10-29 request).

## Decisions

1. **`tools/live/live_plot.py`** draws the test's first `plots.json` plot live in its own window (matplotlib TkAgg on the laptop): the same series, colours and reference lines as the record's Figure 1, with the latest closest distance and the running minimum in the title.
2. **Data source:** the run's `metrics.csv` in the robot container, followed by `docker exec <robot> tail -n +1 -F --pid=<metrics node pid>`, so the tail ends when the node stops. The node flushes once a second, so the window lags by at most about a second. One CSV parser: `metrics_core.CsvLineParser`, also used by `read_metrics_csv`.
3. **Lifecycle:** `sim.sh test` opens the window after the metrics node's liveness check and before pause 1, only in window mode with a `DISPLAY`; `metrics_stop` closes it first thing, so every exit path (normal, wiring failure, Ctrl-C) closes it. The window never affects the verdict: a failure to open is a warning in `run.log`.
4. **Foxglove stays optional.** The metrics node still publishes `/svg/test/*` and `layout.json` is still generated and checked. `setup` copies the plain layout to `/root/svg_test_<name>_layout.json` in the robot container for an optional one-time import; `doctor` reports that file and no longer claims a layout is installed.
5. **Style:** the figure constants move to `tools/live/plot_style.py`, imported by `plot_metrics.py` and `live_plot.py` (no style defined twice; `plot_metrics` keeps forcing Agg, `live_plot` picks TkAgg itself).

## Non-goals

No change to the gates, the record, the CSV or the metrics node. No change under `AirStack/`. The basestation layout is untouched.

## Done when

`sim.sh test` in window mode opens the window before pause 1 and closes it after pause 2; a headless run opens none; the window shows run #22's CSV identically to its record figure; unit tests cover the parser, the model, the lifecycle and the headless/no-display skip; TEST_STANDARD, tools/README and CLAUDE.md say "live plot window".
