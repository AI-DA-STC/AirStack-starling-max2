"use strict";
(function () {

// KEYMAP:BEGIN
const TABLES = {"deadzone": 0.15, "debounce_s": 0.06, "default_scale": 0.5, "footer": {"base": "A / D turn · W / S up / down · Space STOP", "drive": " · F → drive mode", "room": " · F → room mode"}, "hold_silence_s": 1.0, "keys": {"a": ["yaw", 1.0], "d": ["yaw", -1.0], "down": ["forward", -1.0], "left": ["left", 1.0], "right": ["left", -1.0], "s": ["climb", -1.0], "up": ["forward", 1.0], "w": ["climb", 1.0]}, "lines": {"drive": ["Drive mode — ↑ is always where the nose points", "Like driving a car: turn with A / D, then ↑ goes that way.", "#0a7a3c"], "heading_lost": ["Heading lost — let go of the keys", "The drone holds until the heading is back and every key is up.", "#B00020"], "relay_lost": ["Keys not reaching the drone — close this window, then run tools/sim.sh keys", "", "#B00020"], "room": ["Room mode — ↑ is always the far wall", "Like moving a chess piece: ↑ is the far wall no matter where the nose points.", "#1d4ed8"], "room_idle": ["Room mode — ↑ is always the far wall", "Like moving a chess piece: ↑ is the far wall no matter where the nose points.", "#6b7280"], "switch_drive": ["Switching to drive mode — let go of the keys first", "Your ↑ still works the old way until every key is up.", "#b45309"], "switch_room": ["Switching to room mode — let go of the keys first", "Your ↑ still works the old way until every key is up.", "#b45309"]}, "n_axes": 8, "n_buttons": 15, "profiles": {"dragonrise_usb": {"climb_axis": 1, "forward_axis": 3, "left_axis": 2, "lock_button": 6, "yaw_axis": 0}, "xbox_usb": {"climb_axis": 1, "forward_axis": 4, "left_axis": 3, "lock_button": 4, "yaw_axis": 0}}, "scales": {"1": 0.25, "2": 0.5, "3": 1.0}, "stop_shown_s": 1.0, "words": {"climb:-1": "descend", "climb:1": "climb", "forward:-1": "pitch: back", "forward:1": "pitch: forward", "left:-1": "roll: slide right", "left:1": "roll: slide left", "yaw:-1": "turn (yaw) right", "yaw:1": "turn (yaw) left"}};
// KEYMAP:END

function activate(extensionContext) {
  extensionContext.registerPanel({
    name: "SVG Teleop",
    initPanel: (panelContext) => {
      return () => {};
    },
  });
}

module.exports = { activate, TABLES };
})();
