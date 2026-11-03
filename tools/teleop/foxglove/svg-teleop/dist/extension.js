"use strict";
(function () {

// KEYMAP:BEGIN
const TABLES = {"deadzone": 0.15, "debounce_s": 0.06, "default_scale": 0.5, "footer": {"base": "A / D turn · W / S up / down · Space STOP", "drive": " · F → drive mode", "room": " · F → room mode"}, "hold_silence_s": 1.0, "keys": {"a": ["yaw", 1.0], "d": ["yaw", -1.0], "down": ["forward", -1.0], "left": ["left", 1.0], "right": ["left", -1.0], "s": ["climb", -1.0], "up": ["forward", 1.0], "w": ["climb", 1.0]}, "lines": {"drive": ["Drive mode — ↑ is always where the nose points", "Like driving a car: turn with A / D, then ↑ goes that way.", "#0a7a3c"], "heading_lost": ["Heading lost — let go of the keys", "The drone holds until the heading is back and every key is up.", "#B00020"], "relay_lost": ["Keys not reaching the drone — close this window, then run tools/sim.sh keys", "", "#B00020"], "room": ["Room mode — ↑ is always the far wall", "Like moving a chess piece: ↑ is the far wall no matter where the nose points.", "#1d4ed8"], "room_idle": ["Room mode — ↑ is always the far wall", "Like moving a chess piece: ↑ is the far wall no matter where the nose points.", "#6b7280"], "switch_drive": ["Switching to drive mode — let go of the keys first", "Your ↑ still works the old way until every key is up.", "#b45309"], "switch_room": ["Switching to room mode — let go of the keys first", "Your ↑ still works the old way until every key is up.", "#b45309"]}, "n_axes": 8, "n_buttons": 15, "profiles": {"dragonrise_usb": {"climb_axis": 1, "forward_axis": 3, "left_axis": 2, "lock_button": 6, "yaw_axis": 0}, "xbox_usb": {"climb_axis": 1, "forward_axis": 4, "left_axis": 3, "lock_button": 4, "yaw_axis": 0}}, "scales": {"1": 0.25, "2": 0.5, "3": 1.0}, "stop_shown_s": 1.0, "words": {"climb:-1": "descend", "climb:1": "climb", "forward:-1": "pitch: back", "forward:1": "pitch: forward", "left:-1": "roll: slide right", "left:1": "roll: slide left", "yaw:-1": "turn (yaw) right", "yaw:1": "turn (yaw) left"}};
// KEYMAP:END

// ---- strip logic: a port of tools/teleop/keymap.py, proved equal by test/core.test.js against fixtures.json ----
const KEY_ALIASES = { arrowup: "up", arrowdown: "down", arrowleft: "left", arrowright: "right", " ": "space" };
const SCALE_KEYS = TABLES.scales;

function normKey(key) {
  const k = String(key).toLowerCase();
  return Object.prototype.hasOwnProperty.call(KEY_ALIASES, k) ? KEY_ALIASES[k] : k;
}
const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

function stickFor(frac, width) {
  if (frac === 0) return 0.0;
  return (frac > 0 ? 1.0 : -1.0) * (width + Math.abs(frac) * (1.0 - width));
}

class KeyState {
  constructor(profile = "dragonrise_usb", deadzone = TABLES.deadzone) {
    this.profile = TABLES.profiles[profile];
    if (!this.profile) throw new Error("unknown profile " + profile);
    this.scale = TABLES.default_scale;
    this.deadzone = deadzone;
    this._down = new Set();
    this.stopAt = null; // seconds of the last Space
  }
  setScale(k) { this.scale = k; }
  press(key, nowS) {
    const k = normKey(key);
    if (has(SCALE_KEYS, k)) { this.scale = SCALE_KEYS[k]; return; }
    if (k === "space") {
      this.allUp();
      this.stopAt = nowS === undefined ? Date.now() / 1000 : nowS;
      return;
    }
    if (has(TABLES.keys, k)) { this.stopAt = null; this._down.add(k); }
  }
  release(key) { this._down.delete(normKey(key)); }
  allUp() { this._down.clear(); }
  held() { return Array.from(this._down).sort(); }
  sticks() {
    const out = { forward: 0.0, left: 0.0, yaw: 0.0, climb: 0.0 };
    for (const k of this._down) {
      const [stick, sign] = TABLES.keys[k];
      out[stick] += sign;
    }
    for (const s of Object.keys(out)) out[s] = Math.max(-1.0, Math.min(1.0, out[s]));
    const h = Math.sqrt(out.forward ** 2 + out.left ** 2);
    if (h > 1.0) { out.forward /= h; out.left /= h; }
    for (const s of Object.keys(out)) out[s] *= this.scale;
    return out;
  }
  axes() {
    const a = new Array(TABLES.n_axes).fill(0.0);
    const st = this.sticks();
    for (const stick of Object.keys(st)) a[this.profile[stick + "_axis"]] = stickFor(st[stick], this.deadzone);
    return a;
  }
  buttons() { return new Array(TABLES.n_buttons).fill(0); }
  statusText(nowS, maxSpeed) {
    let words;
    if (this.stopAt !== null && nowS - this.stopAt < TABLES.stop_shown_s) {
      words = "STOP";
    } else {
      const st = this.sticks();
      const held = [];
      for (const s of Object.keys(st)) if (st[s]) held.push(TABLES.words[s + ":" + (st[s] > 0 ? 1 : -1)]);
      words = held.join(", ") || "hold (no key)";
    }
    let out = words + "  ·  " + Math.round(this.scale * 100) + " % of top speed";
    if (maxSpeed !== undefined && maxSpeed !== null) out += " = " + (this.scale * maxSpeed).toFixed(1) + " m/s";
    return out;
  }
}

const FLOAT_RE = /^[+-]?(?:(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?|inf|infinity|nan)$/i;
function parseStatus(line) {
  const out = Object.create(null);
  for (const tok of String(line).split(/\s+/)) {
    const i = tok.indexOf("=");
    if (i < 0) continue;
    const k = tok.slice(0, i);
    let v = tok.slice(i + 1);
    if (k === "heading_deg" || k === "heading_age_s") {
      v = FLOAT_RE.test(v) ? (/inf/i.test(v) ? (v[0] === "-" ? -Infinity : Infinity) : Number(v)) : NaN;
    }
    out[k] = v;
  }
  return out;
}

function headerLines(status, seen) {
  const L = TABLES.lines;
  if (!status || !seen || (status.frame !== "body" && status.frame !== "world")) return L.relay_lost.slice();
  if (status.input === "none") return L.room_idle.slice();
  if ((has(status, "guard") ? status.guard : "ok") !== "ok") return L.heading_lost.slice();
  const pending = has(status, "pending") ? status.pending : "none";
  if (pending !== "none") return (pending === "world" ? L.switch_room : L.switch_drive).slice();
  return (status.frame === "world" ? L.room : L.drive).slice();
}

function flipTarget(status) {
  if (!status || status.input === "none" || (status.frame !== "body" && status.frame !== "world")) return null;
  const pending = has(status, "pending") ? status.pending : "none";
  const effective = pending === "body" || pending === "world" ? pending : status.frame;
  return effective === "world" ? "body" : "world";
}

function footerLine(status) {
  const t = flipTarget(status);
  if (t === null) return TABLES.footer.base;
  return TABLES.footer.base + (t === "body" ? TABLES.footer.drive : TABLES.footer.room);
}

function fillTemplate(tpl, name) { return String(tpl).split("{name}").join(name); }


function activate(extensionContext) {
  extensionContext.registerPanel({
    name: "SVG Teleop",
    initPanel: (panelContext) => {
      return () => {};
    },
  });
}

module.exports = { activate, TABLES, __core: { KeyState, stickFor, parseStatus, headerLines, footerLine, flipTarget, fillTemplate } };
})();
