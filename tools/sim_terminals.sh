#!/usr/bin/env bash
# Open ONE Terminator window with four tabs — Isaac Sim, Interfaces, Commander,
# Cockpit — each already inside the right container with its commands printed.
# The no-tmux way to run RUNBOOK §A. Brings the containers up first if needed.
#
#   tools/sim_terminals.sh            # open the window
#   tools/sim_terminals.sh --no-launch  # only (re)write the Terminator layout
#
# How: writes a layout named `airstack-sim` into ~/.config/terminator/config
# (replacing an older copy) and runs `terminator -l airstack-sim`. Each tab
# runs tools/sim_tab.sh <role>; with Terminator's exit_action=hold a tab whose
# shell exits stays open instead of closing the window.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cfg="${HOME}/.config/terminator/config"
launch=true
[ "${1:-}" = "--no-launch" ] && launch=false

if $launch && ! docker ps --format '{{.Names}}' | grep -qx isaac-sim; then
    echo "containers not running — ./airstack.sh up"
    (cd "$repo/AirStack" && ./airstack.sh up)
fi

python3 - "$cfg" "$repo" <<'PY'
import re, sys, pathlib
cfg, repo = pathlib.Path(sys.argv[1]), sys.argv[2]
tab = f"bash {repo}/tools/sim_tab.sh"
roles = [("Isaac Sim", "isaac"), ("Interfaces", "interfaces"),
         ("Commander", "commander"), ("Cockpit", "cockpit")]
block = ["  [[airstack-sim]]",
         "    [[[window0]]]", "      type = Window", '      parent = ""',
         "      title = AirStack sim session", "      size = 1700, 1000",
         "    [[[notebook0]]]", "      type = Notebook", "      parent = window0",
         "      labels = " + ", ".join(label for label, _ in roles),
         "      active_page = 0"]
for i, (label, role) in enumerate(roles):
    block += [f"    [[[tab_{role}]]]", "      type = Terminal", "      parent = notebook0",
              f"      order = {i}", "      profile = default",
              f"      command = {tab} {role}"]
text = cfg.read_text() if cfg.exists() else ""
lines = text.splitlines()
# drop an existing airstack-sim layout (until the next [[name]] / [section])
out, skip = [], False
for line in lines:
    if line.strip() == "[[airstack-sim]]":
        skip = True; continue
    if skip and re.match(r"^(\[\[[^\[]|\[[^\[])", line.strip()):
        skip = False
    if not skip:
        out.append(line)
if "[layouts]" not in [l.strip() for l in out]:
    out += ["[layouts]"]
idx = [l.strip() for l in out].index("[layouts]") + 1
out[idx:idx] = block
cfg.parent.mkdir(parents=True, exist_ok=True)
cfg.write_text("\n".join(out).rstrip("\n") + "\n")
print(f"layout 'airstack-sim' written to {cfg}")
PY

if $launch; then
    nohup terminator -l airstack-sim >/dev/null 2>&1 &
    echo "Terminator window opening: tabs Isaac Sim · Interfaces · Commander · Cockpit"
fi
