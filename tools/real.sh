#!/usr/bin/env bash
# tools/real.sh — the REAL-drone gamepad front door: checks the Logitech F310 pad and prepares the teleop config for
# drone_1 or drone_2. It starts nothing. All logic: tools/teleop/real_teleop.sh (run it with no argument for usage).
exec "$(dirname "$(readlink -f "$0")")/teleop/real_teleop.sh" "$@"
