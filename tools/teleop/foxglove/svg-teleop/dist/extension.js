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


// Every timer and every reading of the time in the panel goes through here, so test/smoke.js can drive them.
const CLOCK = {
  now: () => Date.now(),
  setInterval: (fn, ms) => setInterval(fn, ms),
  clearInterval: (id) => clearInterval(id),
  setTimeout: (fn, ms) => setTimeout(fn, ms),
  clearTimeout: (id) => clearTimeout(id),
};

// ---- the panel: flies only while clicked, zeros on every way out (spec 5.3-5.6) ----
const RATE_MS = 50;                  // 20 Hz, as the Tk window
const RENDER_MS = 200;               // re-reads the status age with no frame arriving
const POLL_MS = 2000;                // /safe_teleop/get_parameters
const FLIP_ANSWER_MS = 2000;         // an unanswered F request is dropped after this
const READ_ANSWER_MS = 5000;         // the same for a safe_teleop read: slower under sim lag, as the Tk window's LIVE_READ_ANSWER_S
const ECHO_FRESH_MS = 1000;          // our own /joy must have come back this recently for the strip to say FLYING
const SENT_STAMPS_KEPT = 200;        // 10 s of messages at 20 Hz: echoes held across a render stall still read as ours
const FOREIGN_STAMPS_TO_REFUSE = 2;  // a live source gives many; one replayed message never trips it
const STATUS_FRESH_MS = 2000;        // the relay reports at 5 Hz; older than this it is gone
const FAILURE_SHOWN_MS = 2000;       // a publish or service failure keeps the red line up this long
const LISTEN_AFTER_DISARM_MS = 500;  // our own trailing zeros are gone by then
const LISTEN_MS = 1000;
const ZEROS_ON_DISARM = 5;
const DEFAULT_PROFILE = "dragonrise_usb";
const RELAY_LINE = "Keys not reaching the drone — start the relay: tools/sim.sh relay";
const CLICK_LINE = "Click here to fly — drone holds";
const CHECK_LINE = "Checking for another source…";
const NOT_FOUND_LINE = "safe_teleop not found yet";
const NO_ECHO_LINE = "Your keys are not coming back from the bridge.";
const GREEN = TABLES.lines.drive[2], GREY = TABLES.lines.room_idle[2], RED = TABLES.lines.relay_lost[2];
const HELD_GLYPHS = [["up", "↑"], ["down", "↓"], ["left", "←"], ["right", "→"], ["w", "W"], ["s", "S"], ["a", "A"], ["d", "D"]];
const PARAM_INTEGER = 2, PARAM_DOUBLE = 3, PARAM_STRING = 4;
const DEFAULTS = {
  drones: ["drone_1"],
  joyTopicTemplate: "/joy",
  statusTopicTemplate: "/teleop_frame/status",
  teleopNsTemplate: "/safe_teleop",
  relayNsTemplate: "/teleop_frame",
};
const TEMPLATE_KEYS = ["joyTopicTemplate", "statusTopicTemplate", "teleopNsTemplate", "relayNsTemplate"];
const JOY_SCHEMA = "sensor_msgs/msg/Joy";
// Declared with the advertise call: the bridge needs the definition to encode a client publish (spec 4).
const JOY_DATATYPES = new Map([
  [JOY_SCHEMA, { definitions: [
    { name: "header", type: "std_msgs/msg/Header", isComplex: true, isArray: false },
    { name: "axes", type: "float32", isComplex: false, isArray: true },
    { name: "buttons", type: "int32", isComplex: false, isArray: true },
  ] }],
  ["std_msgs/msg/Header", { definitions: [
    { name: "stamp", type: "time", isComplex: false, isArray: false },
    { name: "frame_id", type: "string", isComplex: false, isArray: false },
  ] }],
]);

function dronesFrom(value) {
  const raw = Array.isArray(value) ? value : typeof value === "string" ? value.split(",") : [];
  const names = raw.map((n) => String(n).trim()).filter((n) => n);
  return names.length ? names : DEFAULTS.drones.slice();
}

function loadConfig(saved) {
  const cfg = { drones: dronesFrom(saved.drones) };
  for (const k of TEMPLATE_KEYS) cfg[k] = typeof saved[k] === "string" && saved[k] ? saved[k] : DEFAULTS[k];
  return cfg;
}

function paramNumber(pv) {
  const t = Number(pv?.type);
  const v = t === PARAM_DOUBLE ? Number(pv.double_value) : t === PARAM_INTEGER ? Number(pv.integer_value) : NaN;
  return Number.isFinite(v) ? v : null;
}
function paramString(pv) { return Number(pv?.type) === PARAM_STRING ? String(pv.string_value ?? "") : ""; }

function activate(extensionContext) {
  extensionContext.registerPanel({
    name: "SVG Teleop",
    initPanel: (panelContext) => {
      const root = panelContext.panelElement;
      const doc = root.ownerDocument ?? document;
      const win = doc.defaultView ?? (typeof window !== "undefined" ? window : null);

      // ── state ──────────────────────────────────────────────────────────
      const saved = panelContext.initialState ?? {};
      const cfg = loadConfig(saved);
      let selected = cfg.drones.includes(saved.selected) ? saved.selected : cfg.drones[0];
      let names = targets();
      const keys = new KeyState(DEFAULT_PROFILE, TABLES.deadzone);
      let closed = false;
      let armed = false;             // set only at the end of a check that a pointerdown started
      let check = null;              // { listening, timer, foreign } while a click waits for the source check
      let publishTimer = null;
      let lastDisarmAt = -Infinity;
      let armedAt = -Infinity, echoAt = -Infinity;
      const sentStamps = new Set();  // the stamps we published lately: what tells our echo from another source
      let lastKeyEventAt = -Infinity;  // shared by all keys: only the last-pressed key auto-repeats
      let advertised = false;
      let refusal = "";
      let status = null, statusAt = -Infinity;
      let failedAt = -Infinity;      // the last publish or service failure
      let topicsEmpty = false, topicsSeen = false;
      let safeTeleop = { answered: false, lost: false, unknown: "", maxSpeed: null };
      let generation = 0;            // answers from before a drone change are ignored
      let pollOpen = false, flipOpen = false;
      let flipNote = "", flipNoteAt = -Infinity;
      const timeouts = new Set();

      function targets() {
        const t = {};
        for (const k of TEMPLATE_KEYS) t[k] = fillTemplate(cfg[k], selected);
        return { drone: selected, joy: t.joyTopicTemplate, status: t.statusTopicTemplate, teleopNs: t.teleopNsTemplate, relayNs: t.relayNsTemplate };
      }

      function noteFailure() { failedAt = CLOCK.now(); }

      // Nothing the panel does may throw into Studio's event dispatch or stop a timer.
      function safe(fn) {
        return (...args) => {
          try {
            return fn(...args);
          } catch (err) {
            noteFailure();
            console.warn("SVG Teleop:", err);
            return undefined;
          }
        };
      }

      function later(ms, fn) {
        const id = CLOCK.setTimeout(safe(() => { timeouts.delete(id); fn(); }), ms);
        timeouts.add(id);
        return id;
      }
      function cancel(id) { CLOCK.clearTimeout(id); timeouts.delete(id); }

      // ── publishing ─────────────────────────────────────────────────────
      function advertiseJoy() {
        if (typeof panelContext.advertise !== "function") return;
        try {
          panelContext.advertise(names.joy, JOY_SCHEMA, { datatypes: JOY_DATATYPES });
          advertised = true;
        } catch (err) {
          noteFailure();
        }
      }
      function unadvertiseJoy() {
        if (!advertised) return;
        advertised = false;
        try {
          if (typeof panelContext.unadvertise === "function") panelContext.unadvertise(names.joy);
        } catch (err) {
          noteFailure();
        }
      }
      function publishJoy(axes) {
        try {
          const t = CLOCK.now();
          const nanos = Math.trunc(t % 1000) * 1e6;
          const sec = Math.floor(t / 1000);
          sentStamps.add(`${sec}:${nanos}`);
          if (sentStamps.size > SENT_STAMPS_KEPT) sentStamps.delete(sentStamps.values().next().value);
          panelContext.publish(names.joy, {
            header: { stamp: { sec, nsec: nanos, nanosec: nanos }, frame_id: "" },
            axes,
            buttons: keys.buttons(),
          });
        } catch (err) {
          noteFailure();
        }
      }
      function zeroAxes() { return new Array(TABLES.n_axes).fill(0.0); }

      function stampKey(message) {
        const stamp = message?.header?.stamp;
        return stamp ? `${stamp.sec}:${stamp.nsec ?? stamp.nanosec}` : null;
      }
      // A message on the joy topic while armed proves the publish reached the bridge only if it is one of ours.
      function noteEcho(message) {
        if (sentStamps.has(stampKey(message))) echoAt = CLOCK.now();
      }
      // During the check our own stamps never count, and a replay of someone's last message is a single stamp.
      function noteDuringCheck(message) {
        const key = stampKey(message);
        if (key === null || sentStamps.has(key)) return;
        check.foreign.add(key);
        if (check.foreign.size >= FOREIGN_STAMPS_TO_REFUSE) refuseSource();
      }

      function applySubscriptions() {
        const subs = [{ topic: names.status }];
        if (check?.listening || armed) subs.push({ topic: names.joy });
        panelContext.subscribe(subs);
      }

      // ── arming: pointerdown → source check → armed or refused ──────────
      function cancelCheck() {
        if (!check) return;
        const wasListening = check.listening;
        cancel(check.timer);
        check = null;
        if (wasListening) applySubscriptions();
      }
      function startCheck() {
        const wait = Math.max(0, lastDisarmAt + LISTEN_AFTER_DISARM_MS - CLOCK.now());
        check = { listening: false, timer: null, foreign: new Set() };
        if (wait > 0) check.timer = later(wait, beginListening);
        else beginListening();
      }
      function beginListening() {
        check.listening = true;
        check.timer = later(LISTEN_MS, finishCheck);
        applySubscriptions();
        render();
      }
      function finishCheck() {
        check = null;
        armed = true;
        armedAt = CLOCK.now();
        echoAt = -Infinity;
        sentStamps.clear();
        applySubscriptions();        // stays on the joy topic: the echo is how FLYING knows the publish arrives
        keys.allUp();
        publishTimer = CLOCK.setInterval(safe(publishTick), RATE_MS);
        publishJoy(keys.axes());
        render();
      }
      function publishTick() {
        // A keyup can get lost with focus and visibility intact (a dropped remote desktop): no disarm trigger fires.
        if (keys.held().length && CLOCK.now() - lastKeyEventAt >= TABLES.hold_silence_s * 1000) keys.allUp();
        publishJoy(keys.axes());
      }
      function refuseSource() {
        cancelCheck();
        unadvertiseJoy();   // a refused strip publishes nothing: the keyboard window must not warn about it
        refusal = `Another source is publishing ${names.joy} (the keyboard window or a pad). Close it first.`;
      }
      // Every way out comes through here. An idle strip publishes nothing: another source may own the topic.
      function disarm() {
        cancelCheck();
        keys.allUp();
        if (!armed) return;
        armed = false;
        CLOCK.clearInterval(publishTimer);
        publishTimer = null;
        for (let i = 0; i < ZEROS_ON_DISARM; i++) publishJoy(zeroAxes());
        lastDisarmAt = CLOCK.now();
        applySubscriptions();
      }

      // ── services ───────────────────────────────────────────────────────
      function callWithTimeout(service, request, answerMs) {
        return new Promise((resolve, reject) => {
          const timer = later(answerMs, () => reject(new Error(`no reply within ${answerMs} ms`)));
          Promise.resolve()
            .then(() => panelContext.callService(service, request))
            .then((res) => { cancel(timer); resolve(res); }, (err) => { cancel(timer); reject(err); });
        });
      }
      function servicesAvailable() { return typeof panelContext.callService === "function"; }

      function pollSafeTeleop() {
        if (closed || pollOpen || !servicesAvailable()) return;
        pollOpen = true;
        const asked = generation;
        const answered = (fn) => safe((arg) => {
          if (closed || asked !== generation) return;
          pollOpen = false;
          fn(arg);
          render();
        });
        callWithTimeout(`${names.teleopNs}/get_parameters`, { names: ["teleop_controller", "deadzone", "max_speed_mps"] }, READ_ANSWER_MS)
          .then(answered(applySafeTeleop), answered(() => { safeTeleop.lost = safeTeleop.answered; }));
      }
      function applySafeTeleop(res) {
        const vals = res?.values;
        if (!Array.isArray(vals)) { safeTeleop.lost = safeTeleop.answered; return; }
        safeTeleop.answered = true;
        safeTeleop.lost = false;
        const controller = paramString(vals[0]);
        if (controller && has(TABLES.profiles, controller)) {
          safeTeleop.unknown = "";
          keys.profile = TABLES.profiles[controller];
        } else if (controller) {     // the Tk window refuses a layout it cannot send; so does the strip
          safeTeleop.unknown = controller;
          disarm();
        }
        keys.deadzone = paramNumber(vals[1]) ?? keys.deadzone;
        const maxSpeed = paramNumber(vals[2]);
        if (maxSpeed !== null && maxSpeed > 0) safeTeleop.maxSpeed = maxSpeed;
      }

      function requestFlip() {
        const target = flipTarget(usableStatus(CLOCK.now()));
        if (target === null || flipOpen) return;   // the footer offers F only when there is something to flip
        if (!servicesAvailable()) { noteFailure(); return; }
        flipOpen = true;
        const asked = generation;
        const answered = (fn) => safe((arg) => {
          if (closed || asked !== generation) return;
          flipOpen = false;
          fn(arg);
          render();
        });
        callWithTimeout(`${names.relayNs}/set_parameters`, {
          parameters: [{ name: "stick_frame", value: { type: PARAM_STRING, string_value: target } }],
        }, FLIP_ANSWER_MS).then(answered((res) => {
          if (res?.results?.[0]?.successful === false) {
            flipNote = "The relay did not accept the mode change.";
            flipNoteAt = CLOCK.now();
          }
        }), answered(noteFailure));
      }

      // ── what the strip knows ───────────────────────────────────────────
      // The relay's last line while the link looks alive, otherwise null: the one input to the words.
      function usableStatus(now) {
        const linkDown = topicsEmpty || safeTeleop.lost || now - failedAt < FAILURE_SHOWN_MS;
        return !linkDown && status !== null && now - statusAt <= STATUS_FRESH_MS ? status : null;
      }
      function flyingNow(usable, now) {
        return armed && now - echoAt <= ECHO_FRESH_MS
          && flipTarget(usable) !== null && usable.input === "ok" && (usable.guard ?? "ok") === "ok";
      }
      function echoLost(now) {
        return armed && now - armedAt > ECHO_FRESH_MS && now - echoAt > ECHO_FRESH_MS;
      }
      function stripLines(usable) {
        const h = headerLines(usable, usable !== null);
        return h[0] === TABLES.lines.relay_lost[0] ? [RELAY_LINE, h[1], h[2]] : h;
      }

      // ── DOM ────────────────────────────────────────────────────────────
      const el = (tag, cls, css) => {
        const n = doc.createElement(tag);
        if (cls) n.className = cls;
        if (css) Object.assign(n.style, css);
        return n;
      };
      root.tabIndex = 0;
      Object.assign(root.style, { outline: "none", height: "100%", cursor: "pointer", userSelect: "none" });
      const frame = el("div", "st-frame", { boxSizing: "border-box", height: "100%", display: "flex", alignItems: "center", gap: "12px",
        padding: "6px 10px", background: "#ffffff", color: "#111827", fontFamily: "sans-serif", fontSize: "13px" });
      const lines = el("div", "st-lines", { flex: "1", minWidth: "0" });
      const lineOne = el("div", "", { fontWeight: "bold", fontSize: "14px" });
      const modeEl = el("span", "st-line1");
      const armEl = el("span", "st-arm");
      lineOne.appendChild(modeEl);
      lineOne.appendChild(armEl);
      const sentenceEl = el("div", "st-sentence");
      const noticeEl = el("div", "st-notice", { color: RED, fontWeight: "bold" });
      const footerEl = el("div", "st-footer", { fontFamily: "monospace", fontSize: "12px", marginTop: "2px" });
      const footerKeys = el("span", "st-keys");
      const heldEl = el("span", "st-held");
      const speedEl = el("span", "st-speed");
      const footerNote = el("span", "st-note");
      const sep = () => { const s = el("span"); s.textContent = "  ·  "; return s; };
      for (const n of [footerKeys, sep(), heldEl, sep(), speedEl, footerNote]) footerEl.appendChild(n);
      for (const n of [lineOne, sentenceEl, noticeEl, footerEl]) lines.appendChild(n);
      const selector = el("select", "st-selector");
      frame.appendChild(lines);
      frame.appendChild(selector);
      root.appendChild(frame);

      let selectorKey = null;
      function renderSelector() {
        const key = cfg.drones.join("\u0000");
        if (key !== selectorKey) {
          selectorKey = key;
          selector.textContent = "";
          for (const name of cfg.drones) {
            const o = el("option");
            o.value = name;
            o.textContent = name;
            selector.appendChild(o);
          }
        }
        selector.value = selected;
        selector.disabled = cfg.drones.length < 2;
        selector.style.opacity = selector.disabled ? "0.5" : "1";
      }

      const setText = (n, t) => { if (n.textContent !== t) n.textContent = t; };

      function render() {
        if (closed) return;
        const now = CLOCK.now();
        const usable = usableStatus(now);
        const [bold, sentence, colour] = stripLines(usable);
        const flying = flyingNow(usable, now);
        setText(modeEl, bold);
        modeEl.style.color = colour;
        setText(armEl, flying ? ` · FLYING ${selected}` : check ? ` · ${CHECK_LINE}` : armed ? " · armed, not proven yet" : ` · ${CLICK_LINE}`);
        armEl.style.color = flying ? GREEN : GREY;
        setText(sentenceEl, sentence);
        frame.style.border = flying ? `3px solid ${GREEN}` : `3px dashed ${GREY}`;

        const notice = safeTeleop.unknown
          ? `Refusing to fly: safe_teleop runs controller '${safeTeleop.unknown}', and this strip has no layout for it.`
          : refusal || (echoLost(now) ? NO_ECHO_LINE : "") || (now - flipNoteAt < FAILURE_SHOWN_MS ? flipNote : "");
        setText(noticeEl, notice);
        noticeEl.hidden = !notice;

        setText(footerKeys, footerLine(usable));
        const held = new Set(keys.held());
        const glyphs = HELD_GLYPHS.filter(([k]) => held.has(k)).map(([, g]) => g);
        const stop = keys.statusText(now / 1000).startsWith("STOP");
        setText(heldEl, stop ? "STOP" : glyphs.length ? `holding: ${glyphs.join(", ")}` : "hold (no key)");
        const pct = `${Math.round(keys.scale * 100)} %`;
        const speed = safeTeleop.maxSpeed === null ? "" : ` = ${(keys.scale * safeTeleop.maxSpeed).toFixed(1)} m/s`;
        setText(speedEl, pct + speed);
        setText(footerNote, !safeTeleop.answered || safeTeleop.lost ? `  ·  ${NOT_FOUND_LINE}` : "");
      }

      // ── events ─────────────────────────────────────────────────────────
      const handled = (k) => has(TABLES.keys, k) || has(SCALE_KEYS, k) || k === "space" || k === "f";

      const onPointerDown = safe((ev) => {
        if (ev.button !== undefined && ev.button !== 0) return;
        if (!selector.disabled && selector.contains(ev.target)) {   // going for the selector is attention leaving the keys
          disarm();
          render();
          return;
        }
        root.focus();
        if (armed || check) return;
        refusal = "";
        if (!safeTeleop.unknown) {
          if (!advertised) advertiseJoy();   // at the first click: an idle strip must not look like a /joy publisher
          startCheck();
        }
        render();
      });
      // Capture phase, on the document: a panel elsewhere can keep focus from moving, not this from firing.
      const onDocPointerDown = safe((ev) => {
        if (root.contains(ev.target)) return;
        disarm();
        render();
      });
      const onKeyDown = safe((ev) => {
        if (!armed && !check) {
          // Focused but disarmed (Alt-Tab back, or a refusal): Studio's hotkeys must not see Space or the arrows.
          const a = doc.activeElement;
          if (a && root.contains(a)) {
            const k = normKey(ev.key);
            if (!((ev.ctrlKey || ev.metaKey || ev.altKey) && k !== "space") && handled(k)) {
              ev.preventDefault();
              ev.stopPropagation();
            }
          }
          return;                                     // never flies; an unfocused strip passes everything through
        }
        lastKeyEventAt = CLOCK.now();                 // repeats too: they are how a held key stays held
        const k = normKey(ev.key);
        if ((ev.ctrlKey || ev.metaKey || ev.altKey) && k !== "space") return;   // Space stops, whatever else is down
        if (!handled(k)) return;                      // Tab is never handled: it moves focus out, which disarms
        ev.preventDefault();
        ev.stopPropagation();
        if (!armed || ev.repeat) return;              // a key already down at arming stays ignored until pressed again
        if (k === "f") requestFlip();
        else keys.press(k, CLOCK.now() / 1000);
        render();
      });
      const onKeyUp = safe((ev) => {
        if (!armed && !check) return;
        lastKeyEventAt = CLOCK.now();
        const k = normKey(ev.key);
        if (!handled(k)) return;
        ev.preventDefault();
        ev.stopPropagation();
        keys.release(k);
        render();
      });
      const onFocusOut = safe((ev) => {
        if (ev.relatedTarget === root) return;        // only the root flies: the selector inside it counts as leaving
        disarm();
        render();
      });
      const onWindowBlur = safe(() => { disarm(); render(); });
      const onVisibility = safe(() => {
        if (doc.hidden || doc.visibilityState === "hidden") { disarm(); render(); }
      });
      const onSelectorChange = safe(() => {
        if (selector.value === selected) return;
        selected = selector.value;
        reconfigure();
      });

      // A new drone or new settings: zeros to the old topic, then every template points at the new one.
      function reconfigure() {
        if (!cfg.drones.includes(selected)) selected = cfg.drones[0];
        const next = targets();
        disarm();
        if (Object.keys(next).some((k) => next[k] !== names[k])) {
          if (next.joy !== names.joy || next.drone !== names.drone) unadvertiseJoy();
          names = next;
          generation++;
          pollOpen = flipOpen = false;
          status = null;
          statusAt = -Infinity;
          failedAt = -Infinity;
          refusal = flipNote = "";
          safeTeleop = { answered: false, lost: false, unknown: "", maxSpeed: null };
          keys.profile = TABLES.profiles[DEFAULT_PROFILE];
          keys.deadzone = TABLES.deadzone;
          applySubscriptions();
          pollSafeTeleop();
        }
        persist();
        renderSelector();
        updateSettings();
        render();
      }

      function persist() {
        if (typeof panelContext.saveState === "function") panelContext.saveState({ ...cfg, selected });
      }

      function updateSettings() {
        if (typeof panelContext.updatePanelSettingsEditor !== "function") return;
        const str = (label, value, help) => ({ label, input: "string", value, help });
        panelContext.updatePanelSettingsEditor({
          actionHandler: safe((action) => {
            if (action.action !== "update") return;
            const key = action.payload.path[action.payload.path.length - 1];
            if (key === "drones") cfg.drones = dronesFrom(action.payload.value);
            else if (TEMPLATE_KEYS.includes(key)) cfg[key] = String(action.payload.value ?? "") || DEFAULTS[key];
            else return;
            reconfigure();
          }),
          nodes: {
            strip: {
              label: "SVG Teleop",
              fields: {
                drones: str("Drones", cfg.drones.join(", "), "Comma-separated names. The selector on the strip lists them."),
                joyTopicTemplate: str("Joy topic", cfg.joyTopicTemplate, "{name} is the selected drone, e.g. /{name}/joy"),
                statusTopicTemplate: str("Relay status topic", cfg.statusTopicTemplate, "e.g. /{name}/teleop_frame/status"),
                teleopNsTemplate: str("safe_teleop namespace", cfg.teleopNsTemplate, "e.g. /{name}/safe_teleop"),
                relayNsTemplate: str("Relay namespace", cfg.relayNsTemplate, "e.g. /{name}/teleop_frame"),
              },
            },
          },
        });
      }

      panelContext.onRender = (renderState, done) => {
        try {
          if (!closed) {
            if (renderState.topics) {
              topicsSeen = topicsSeen || renderState.topics.length > 0;
              topicsEmpty = topicsSeen && renderState.topics.length === 0;
            }
            for (const evt of renderState.currentFrame ?? []) {
              if (evt.topic === names.status && typeof evt.message?.data === "string") {
                status = parseStatus(evt.message.data);
                statusAt = CLOCK.now();    // wall clock: receiveTime is sim time on this bridge
              } else if (evt.topic === names.joy) {
                if (check?.listening) noteDuringCheck(evt.message);
                else if (armed) noteEcho(evt.message);
              }
            }
            render();
          }
        } catch (err) {
          noteFailure();
          console.warn("SVG Teleop:", err);
        } finally {
          done();
        }
      };

      root.addEventListener("pointerdown", onPointerDown);
      root.addEventListener("keydown", onKeyDown);
      root.addEventListener("keyup", onKeyUp);
      root.addEventListener("focusout", onFocusOut);
      selector.addEventListener("change", onSelectorChange);
      if (win) win.addEventListener("blur", onWindowBlur);
      doc.addEventListener("visibilitychange", onVisibility);
      doc.addEventListener("pointerdown", onDocPointerDown, true);

      const renderTimer = CLOCK.setInterval(safe(render), RENDER_MS);
      const pollTimer = CLOCK.setInterval(safe(pollSafeTeleop), POLL_MS);

      if (typeof panelContext.watch === "function") {
        panelContext.watch("currentFrame");
        panelContext.watch("topics");
      }
      safe(applySubscriptions)();
      pollSafeTeleop();
      renderSelector();
      updateSettings();
      render();

      return () => {
        if (closed) return;
        safe(disarm)();
        closed = true;
        unadvertiseJoy();
        CLOCK.clearInterval(renderTimer);
        CLOCK.clearInterval(pollTimer);
        for (const id of timeouts) CLOCK.clearTimeout(id);
        timeouts.clear();
        root.removeEventListener("pointerdown", onPointerDown);
        root.removeEventListener("keydown", onKeyDown);
        root.removeEventListener("keyup", onKeyUp);
        root.removeEventListener("focusout", onFocusOut);
        selector.removeEventListener("change", onSelectorChange);
        if (win) win.removeEventListener("blur", onWindowBlur);
        doc.removeEventListener("visibilitychange", onVisibility);
        doc.removeEventListener("pointerdown", onDocPointerDown, true);
        safe(() => {
          if (typeof panelContext.unsubscribeAll === "function") panelContext.unsubscribeAll();
          else panelContext.subscribe([]);
        })();
        root.removeChild(frame);
      };
    },
  });
}

module.exports = { activate, TABLES, __clock: CLOCK, __core: { KeyState, stickFor, parseStatus, headerLines, footerLine, flipTarget, fillTemplate } };
})();
