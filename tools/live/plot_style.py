"""House style shared by the record figure (plot_metrics.py) and the live window (live_plot.py): one definition.

No matplotlib import here, so each caller picks its own backend (Agg for files, TkAgg for the live window)."""

INK, MUTED, GRID, SPINE = "#404040", "#5F6368", "#E6E8EA", "#D0D3D6"
COLOURS = ["#0072B2", "#E69F00", "#009E73"]          # Okabe-Ito blue / orange / bluish green, fixed series order
STYLES = ["-", "--", ":"]                            # a 4th+ series repeats the hues with another dash
MIN_COLOUR = "#CC79A7"                               # Okabe-Ito reddish purple: the running minimum is not d_12
PHASE_SPAN = {1: "#8A8F94", 3: "#C9A66B"}
PHASE_NAME = {1: "takeoff", 3: "land"}
FOOTER = "Sim only (iron rule 9): not a drone result."


def series_colour(i, name):
    """Colour of the i-th series of a plot: the running minimum always gets MIN_COLOUR."""
    return MIN_COLOUR if name.endswith("_running") else COLOURS[i % 3]


def series_style(i):
    return STYLES[(i // 3) % 3]


def ref_value(meta, name):
    """A reference line's value from a metrics.csv header: the `refs=ref_2r:1.1;…` string (metrics_core's parser)
    or a plain `name=value` meta line. None when the header has neither."""
    import metrics_core as M                          # numpy only; imported here so this module stays dependency-free
    refs = meta.get("refs")
    if isinstance(refs, dict) and name in refs:
        return float(refs[name])
    parsed = M.meta_refs(meta)
    if name in parsed:
        return parsed[name]
    try:
        return float(meta.get(name))
    except (TypeError, ValueError):
        return None
