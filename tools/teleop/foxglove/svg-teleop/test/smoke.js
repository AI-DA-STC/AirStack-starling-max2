"use strict";
// Smoke test of the SVG Teleop panel: loads ../dist/extension.js under a small DOM stub, a fake Foxglove panel
// context and a fake clock, then checks the publish log and the rendered text. Run: node test/smoke.js
const assert = require("assert");
const path = require("path");
const fixtures = require("./fixtures.json");
const ext = require(path.join(__dirname, "..", "dist", "extension.js"));
const { TABLES } = ext;

const RELAY_LINE = "Keys not reaching the drone — start the relay: tools/sim.sh relay";
const CLICK = "Click here to fly — drone holds";
const CHECKING = "Checking for another source…";
const DRIVE_OK = "frame=body pending=none heading_deg=10.0 heading_age_s=0.01 guard=ok input=ok";
const ROOM_OK = "frame=world pending=none heading_deg=10.0 heading_age_s=0.01 guard=ok input=ok";
const ROOM_IDLE = "frame=world pending=none heading_deg=10.0 heading_age_s=0.01 guard=ok input=none";
const realSetImmediate = setImmediate;

// ─── DOM stub (events bubble, as they do in Studio's document) ─────────────────
function makeNode(tag, doc) {
  const node = {
    tagName: tag, children: [], listeners: {}, style: {}, hidden: false, title: "", value: "", disabled: false,
    parentNode: null, _text: "", className: "", tabIndex: -1, ownerDocument: doc,
    appendChild(ch) { if (ch.parentNode) ch.parentNode.removeChild(ch); ch.parentNode = node; node.children.push(ch); return ch; },
    removeChild(ch) { const i = node.children.indexOf(ch); if (i >= 0) node.children.splice(i, 1); ch.parentNode = null; return ch; },
    contains(n) { for (let x = n; x; x = x.parentNode) if (x === node) return true; return false; },
    addEventListener(t, fn) { (node.listeners[t] ??= []).push(fn); },
    removeEventListener(t, fn) { node.listeners[t] = (node.listeners[t] ?? []).filter((f) => f !== fn); },
    focus() { doc.activeElement = node; },
    get textContent() { return node._text + node.children.map((c) => c.textContent).join(""); },
    set textContent(v) { for (const c of node.children) c.parentNode = null; node.children = []; node._text = String(v); },
  };
  return node;
}
function* walk(n) { yield n; for (const c of n.children) yield* walk(c); }

function makeEvent(target, props) {
  const ev = { target, repeat: false, prevented: false, stopped: false, ctrlKey: false, metaKey: false, altKey: false,
    preventDefault() { ev.prevented = true; }, stopPropagation() { ev.stopped = true; }, ...props };
  return ev;
}
function dispatch(node, type, props) {
  const ev = makeEvent(node, props);
  for (let n = node; n; n = n.parentNode) {
    for (const fn of [...(n.listeners[type] ?? [])]) fn(ev);
    if (ev.stopped) break;
  }
  return ev;
}

// ─── fake clock: every timer in the panel runs on this ─────────────────────────
function makeClock() {
  let t = 1_700_000_000_000, nextId = 1;
  const timers = new Map();
  const add = (fn, ms, every) => { const id = nextId++; timers.set(id, { id, fn, due: t + ms, every }); return id; };
  return {
    now: () => t,
    setInterval: (fn, ms) => add(fn, ms, ms),
    clearInterval: (id) => { timers.delete(id); },
    setTimeout: (fn, ms) => add(fn, ms, null),
    clearTimeout: (id) => { timers.delete(id); },
    live: () => timers.size,
    advance(ms) {
      const end = t + ms;
      for (;;) {
        const next = [...timers.values()].filter((x) => x.due <= end).sort((a, b) => a.due - b.due || a.id - b.id)[0];
        if (!next) break;
        t = next.due;
        if (next.every) next.due += next.every; else timers.delete(next.id);
        next.fn();
      }
      t = end;
    },
  };
}

// ─── one panel under a fake context ────────────────────────────────────────────
function setup(initialState = {}, before = () => {}) {
  const clock = makeClock();
  Object.assign(ext.__clock, { now: clock.now, setInterval: clock.setInterval, clearInterval: clock.clearInterval,
    setTimeout: clock.setTimeout, clearTimeout: clock.clearTimeout });
  const win = { listeners: {}, addEventListener(t, fn) { (win.listeners[t] ??= []).push(fn); },
    removeEventListener(t, fn) { win.listeners[t] = (win.listeners[t] ?? []).filter((f) => f !== fn); } };
  const doc = { defaultView: win, activeElement: null, hidden: false, visibilityState: "visible", listeners: {},
    createElement: (tag) => makeNode(tag, doc),
    addEventListener(t, fn) { (doc.listeners[t] ??= []).push(fn); },
    removeEventListener(t, fn) { doc.listeners[t] = (doc.listeners[t] ?? []).filter((f) => f !== fn); } };
  const root = makeNode("div", doc);
  const h = {
    clock, win, doc, root, published: [], publishAttempts: 0, advertised: [], unadvertised: [], subs: [], subLog: [],
    calls: [], saved: null, settings: null, watched: [], doneCount: 0, renderCount: 0, relayLine: null,
    publishThrows: () => false,
    params: { teleop_controller: "dragonrise_usb", deadzone: 0.15, max_speed_mps: 2.0 },
    getParams: "answer", setReply: { results: [{ successful: true, reason: "" }] }, setMode: "answer",
    events: [],
  };
  const ctx = {
    initialState, panelElement: root,
    saveState: (s) => { h.saved = s; },
    watch: (f) => h.watched.push(f),
    subscribe: (subs) => { h.subs = subs.map((s) => s.topic); h.subLog.push({ t: clock.now(), topics: h.subs.slice() }); },
    unsubscribeAll: () => { h.subs = []; h.events.push("unsubscribeAll"); },
    advertise: (topic, schema, options) => { h.advertised.push({ topic, schema, options }); },
    unadvertise: (topic) => { h.unadvertised.push(topic); h.events.push("unadvertise " + topic); },
    publish: (topic, message) => {
      h.publishAttempts++;
      if (h.publishThrows()) throw new Error("no link");
      h.published.push({ topic, message, t: clock.now() });
      h.events.push("publish " + topic);
    },
    updatePanelSettingsEditor: (ed) => { h.settings = ed; },
    callService: (service, req) => {
      h.calls.push({ service, req, t: clock.now() });
      if (service.endsWith("/get_parameters")) {
        if (h.getParams === "reject") return Promise.reject(new Error("service not found"));
        if (h.getParams === "never") return new Promise(() => {});
        return Promise.resolve({ values: req.names.map((n) => (typeof h.params[n] === "string"
          ? { type: 4, string_value: h.params[n] } : h.params[n] === undefined ? { type: 0 } : { type: 3, double_value: h.params[n] })) });
      }
      if (h.setMode === "never") return new Promise(() => {});
      if (h.setMode === "reject") return Promise.reject(new Error("service not found"));
      return Promise.resolve(h.setReply);
    },
  };
  h.ctx = ctx;
  before(h);                         // what the fake data source answers from the first moment
  let initPanel = null;
  ext.activate({ registerPanel: (def) => { assert.strictEqual(def.name, "SVG Teleop"); initPanel = def.initPanel; } });
  h.cleanup = initPanel(ctx);

  h.deliver = (events) => { let done = 0; ctx.onRender({ currentFrame: events }, () => { done++; }); assert.strictEqual(done, 1, "onRender must call done once"); h.doneCount++; };
  h.status = (line, topic = "/teleop_frame/status") => h.deliver([{ topic, message: { data: line }, receiveTime: { sec: 1, nsec: 0 }, schemaName: "std_msgs/msg/String" }]);
  h.joy = (topic = "/joy") => h.deliver([{ topic, message: { axes: [], buttons: [] }, receiveTime: { sec: 1, nsec: 0 } }]);
  let sinceFeed = 0;
  // Advance the clock in 10 ms steps, letting promises settle; the relay (if set) reports at 5 Hz.
  h.tick = async (ms) => {
    for (let left = ms; left > 0; left -= 10) {
      clock.advance(10);
      sinceFeed += 10;
      if (h.relayLine !== null && sinceFeed >= 200) { sinceFeed = 0; h.status(h.relayLine, h.relayTopic); }
      await new Promise(realSetImmediate);
    }
  };
  h.text = () => root.textContent;
  h.part = (cls) => { for (const n of walk(root)) if (n.className.split(/\s+/).includes(cls)) return n; throw new Error("no ." + cls); };
  h.select = () => { for (const n of walk(root)) if (n.tagName === "select") return n; throw new Error("no select"); };
  h.frameStyle = () => h.part("st-frame").style.border;
  h.down = (props) => dispatch(root, "pointerdown", { button: 0, ...props });
  h.key = (key, props) => dispatch(root, "keydown", { key, ...props });
  h.up = (key, props) => dispatch(root, "keyup", { key, ...props });
  h.joyLog = () => h.published.filter((p) => /joy$/.test(p.topic));
  h.lastAxes = () => { const l = h.joyLog(); return l[l.length - 1].message.axes; };
  h.fireWin = (t) => { for (const fn of [...(win.listeners[t] ?? [])]) fn({}); };
  h.fireDoc = (t) => { for (const fn of [...(doc.listeners[t] ?? [])]) fn({}); };
  h.setCalls = () => h.calls.filter((c) => c.service.endsWith("/set_parameters"));
  h.getCalls = () => h.calls.filter((c) => c.service.endsWith("/get_parameters"));
  return h;
}

// Click, wait out the source check, keep the relay reporting a healthy line: the strip reads FLYING.
async function fly(h, line = DRIVE_OK) {
  h.relayLine = line;
  await h.tick(10);
  h.down();
  await h.tick(1300);
  assert.ok(h.text().includes("FLYING"), "expected FLYING, got: " + h.text());
}
const isZeros = (m) => m.axes.every((v) => v === 0) && m.axes.length === TABLES.n_axes && m.buttons.length === TABLES.n_buttons;
const fixtureAxis = (held, scale, profile) => fixtures.axes.find((c) => JSON.stringify(c.held) === JSON.stringify(held)
  && c.scale === scale && c.profile === profile && c.deadzone === 0.15 && !c.space).axes;
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);
const MULTI = { drones: ["drone_1", "drone_2"], joyTopicTemplate: "/{name}/joy", statusTopicTemplate: "/{name}/teleop_frame/status",
  teleopNsTemplate: "/{name}/safe_teleop", relayNsTemplate: "/{name}/teleop_frame" };

const cases = [];
const test = (name, fn) => cases.push([name, fn]);

// ─── the named cases (plan, task 4) ────────────────────────────────────────────
test("not armed at start: no /joy published, text \"Click here to fly — drone holds\"", async () => {
  const h = setup();
  assert.ok(h.text().includes(RELAY_LINE), "before any status the relay line shows: " + h.text());
  assert.ok(!h.text().includes(TABLES.lines.relay_lost[0]), "the Tk window's relay line must not show");
  h.relayLine = DRIVE_OK;
  await h.tick(3000);
  assert.strictEqual(h.joyLog().length, 0);
  assert.ok(h.text().includes(CLICK));
  assert.ok(!h.text().includes("FLYING"));
  assert.match(h.frameStyle(), /dashed/);
  assert.strictEqual(h.root.tabIndex, 0);
  assert.ok(h.watched.includes("currentFrame") && h.watched.includes("topics"));
  assert.strictEqual(h.advertised[0].topic, "/joy");
  assert.strictEqual(h.advertised[0].schema, "sensor_msgs/msg/Joy");
  assert.ok(h.advertised[0].options.datatypes.has("sensor_msgs/msg/Joy"), "the schema is declared with the advertise call");
  assert.deepStrictEqual(h.subs, ["/teleop_frame/status"]);
});

test("pointerdown arms: publishes at 20 Hz with zero axes, then \"FLYING drone_1\"", async () => {
  const h = setup();
  h.relayLine = DRIVE_OK;
  await h.tick(300);
  h.down();
  assert.strictEqual(h.doc.activeElement, h.root);
  assert.ok(h.text().includes(CHECKING), h.text());
  assert.ok(h.subs.includes("/joy"), "listens on the joy topic during the check");
  await h.tick(900);
  assert.strictEqual(h.joyLog().length, 0, "nothing goes out during the check");
  await h.tick(110);
  assert.ok(!h.subs.includes("/joy"), "stops listening once armed");
  const before = h.joyLog().length;
  assert.ok(before >= 1);
  await h.tick(1000);
  const n = h.joyLog().length - before;
  assert.strictEqual(n, 20, "20 Hz");
  for (const p of h.joyLog()) assert.ok(isZeros(p.message));
  assert.ok(h.text().includes("FLYING drone_1"), h.text());
  assert.match(h.frameStyle(), /solid/);
  const last = h.joyLog().at(-1);
  assert.strictEqual(last.topic, "/joy");
  assert.strictEqual(last.message.header.stamp.sec, Math.floor(last.t / 1000));
  assert.strictEqual(last.message.header.stamp.nsec, (last.t % 1000) * 1e6);
});

test("↑ held: forward axis equals fixture value for scale 0.5", async () => {
  const h = setup();
  await fly(h);
  const ev = h.key("ArrowUp");
  assert.ok(ev.prevented && ev.stopped);
  await h.tick(100);
  const want = fixtureAxis(["up"], 0.5, "dragonrise_usb");
  h.lastAxes().forEach((v, i) => near(v, want[i]));
  assert.ok(h.part("st-held").textContent.includes("holding: ↑"), h.text());
  assert.ok(h.text().includes("50 % = 1.0 m/s"), h.text());
  const rel = h.up("ArrowUp");
  assert.ok(rel.prevented && rel.stopped);
  await h.tick(100);
  assert.ok(isZeros(h.joyLog().at(-1).message), "release returns to zero");
  h.key("W");
  await h.tick(100);
  near(h.lastAxes()[TABLES.profiles.dragonrise_usb.climb_axis], 0.575);
  h.up("w");
  await h.tick(100);
  assert.ok(isZeros(h.joyLog().at(-1).message), "W and w are one key");
});

test("focus leaving the root disarms and sends five zeros", async () => {
  const h = setup();
  await fly(h);
  h.key("ArrowUp");
  await h.tick(100);
  const n = h.joyLog().length;
  dispatch(h.root, "focusout", { relatedTarget: makeNode("div", h.doc) });
  const after = h.joyLog().slice(n);
  assert.strictEqual(after.length, 5, "five, synchronously");
  for (const p of after) assert.ok(isZeros(p.message));
  await h.tick(1000);
  assert.strictEqual(h.joyLog().length, n + 5, "the timer stopped");
  assert.ok(h.text().includes(CLICK));
  assert.match(h.frameStyle(), /dashed/);
  const n2 = h.joyLog().length;
  dispatch(h.root, "focusout", { relatedTarget: null });
  assert.strictEqual(h.joyLog().length, n2, "an idle strip sends nothing");
});

test("window blur disarms and sends five zeros; hidden document does the same", async () => {
  const h = setup();
  await fly(h);
  h.key("a");
  await h.tick(100);
  let n = h.joyLog().length;
  h.fireWin("blur");
  assert.strictEqual(h.joyLog().length, n + 5);
  for (const p of h.joyLog().slice(n)) assert.ok(isZeros(p.message));
  await h.tick(600);
  h.down();
  await h.tick(1100);
  assert.ok(h.text().includes("FLYING"));
  h.fireDoc("visibilitychange");
  assert.ok(h.text().includes("FLYING"), "a visible document stays armed");
  n = h.joyLog().length;
  h.doc.hidden = true; h.doc.visibilityState = "hidden";
  h.fireDoc("visibilitychange");
  assert.strictEqual(h.joyLog().length, n + 5);
  assert.ok(!h.text().includes("FLYING"));
});

test("refocusing the window does not re-arm", async () => {
  const h = setup();
  await fly(h);
  h.fireWin("blur");
  const n = h.joyLog().length;
  h.fireWin("focus");
  dispatch(h.root, "focus", {});
  dispatch(h.root, "focusin", {});
  const ev = h.key("ArrowUp");
  assert.ok(!ev.prevented, "keys pass through while not armed");
  await h.tick(2000);
  assert.strictEqual(h.joyLog().length, n);
  assert.ok(h.text().includes(CLICK));
  assert.ok(!h.text().includes("FLYING"));
});

test("lost keyup does not stick after re-click", async () => {
  const h = setup();
  await fly(h);
  h.key("ArrowUp");
  await h.tick(100);
  h.fireWin("blur");                 // the keyup goes to another window
  await h.tick(600);
  h.down();
  await h.tick(1100);
  assert.ok(h.text().includes("FLYING"));
  assert.ok(isZeros(h.joyLog().at(-1).message));
  const ev = h.key("ArrowUp", { repeat: true });  // auto-repeat of the key still physically down
  assert.ok(ev.prevented, "a repeat is handled so Studio never sees it");
  await h.tick(100);
  assert.ok(isZeros(h.joyLog().at(-1).message), "a repeat does not count as a press");
});

test("panel cleanup sends five zeros and unadvertises", async () => {
  const h = setup();
  await fly(h);
  h.key("d");
  await h.tick(100);
  const n = h.joyLog().length;
  h.cleanup();
  assert.strictEqual(h.joyLog().length, n + 5);
  for (const p of h.joyLog().slice(n)) assert.ok(isZeros(p.message));
  assert.deepStrictEqual(h.unadvertised, ["/joy"]);
  assert.ok(h.events.lastIndexOf("publish /joy") < h.events.indexOf("unadvertise /joy"), "zeros first");
  assert.strictEqual(h.clock.live(), 0, "every timer cleared");
  for (const o of [h.root, h.win, h.doc]) for (const t of Object.keys(o.listeners)) assert.strictEqual(o.listeners[t].length, 0, "listener left: " + t);
  h.relayLine = null;
  await h.tick(3000);
  assert.strictEqual(h.joyLog().length, n + 5);
  const c = h.calls.length;
  await h.tick(5000);
  assert.strictEqual(h.calls.length, c);
  h.cleanup();                       // a second call is harmless
  assert.strictEqual(h.joyLog().length, n + 5);
});

test("space lets every key go and shows STOP; a later flight key clears STOP", async () => {
  const h = setup();
  await fly(h);
  h.key("ArrowUp");
  h.key("w");
  await h.tick(100);
  assert.ok(!isZeros(h.joyLog().at(-1).message));
  const ev = h.key(" ");
  assert.ok(ev.prevented && ev.stopped);
  assert.strictEqual(h.part("st-held").textContent, "STOP");
  await h.tick(100);
  assert.ok(isZeros(h.joyLog().at(-1).message));
  h.key("ArrowLeft");
  assert.strictEqual(h.part("st-held").textContent, "holding: ←");
  await h.tick(100);
  near(h.lastAxes()[TABLES.profiles.dragonrise_usb.left_axis], 0.575);
  h.up("ArrowLeft");
  h.key(" ");
  await h.tick(1250);               // stop_shown_s, plus up to one 5 Hz re-render
  assert.strictEqual(h.part("st-held").textContent, "hold (no key)", "STOP shows for stop_shown_s");
});

test("F while held asks once with event.repeat ignored; target comes from flipTarget", async () => {
  const h = setup();
  await fly(h);
  const ev = h.key("f");
  assert.ok(ev.prevented && ev.stopped);
  for (let i = 0; i < 4; i++) h.key("f", { repeat: true });
  await h.tick(50);
  assert.strictEqual(h.setCalls().length, 1);
  const c = h.setCalls()[0];
  assert.strictEqual(c.service, "/teleop_frame/set_parameters");
  assert.deepStrictEqual(c.req, { parameters: [{ name: "stick_frame", value: { type: 4, string_value: ext.__core.flipTarget(ext.__core.parseStatus(DRIVE_OK)) } }] });
  assert.strictEqual(c.req.parameters[0].value.string_value, "world");
  h.up("f");
  h.relayLine = "frame=body pending=world heading_deg=10.0 heading_age_s=0.01 guard=ok input=ok";
  await h.tick(250);
  h.key("F");                        // a second press while the flip waits cancels it
  await h.tick(50);
  assert.strictEqual(h.setCalls().length, 2);
  assert.strictEqual(h.setCalls()[1].req.parameters[0].value.string_value, "body");
  // An unanswered request is dropped after 2 s, shows the red line, and F works again.
  h.up("F");
  h.setMode = "never";
  h.key("f");
  h.up("f");
  h.key("f");
  h.up("f");
  await h.tick(1900);
  assert.strictEqual(h.setCalls().length, 3, "one request open at a time");
  await h.tick(150);
  assert.ok(h.text().includes(RELAY_LINE), h.text());
  assert.ok(!h.text().includes("FLYING"));
  h.setMode = "answer";
  await h.tick(2200);               // the failure stays shown 2 s, plus up to one 5 Hz re-render
  assert.ok(h.text().includes("FLYING"), "the red line clears");
  h.key("f");
  await h.tick(50);
  assert.strictEqual(h.setCalls().length, 4);
  // The relay refusing is not a dead link, and is said in words.
  h.up("f");
  h.setReply = { results: [{ successful: false, reason: "invalid" }] };
  h.key("f");
  await h.tick(50);
  assert.ok(h.part("st-notice").textContent.length > 0);
  assert.ok(h.text().includes("FLYING"));
});

test("no FLYING while the relay is silent (status older than 2 s: red strip line)", async () => {
  const h = setup();
  await fly(h);
  h.relayLine = null;
  await h.tick(1800);
  assert.ok(h.text().includes("FLYING"), "still fresh at 1.8 s");
  await h.tick(400);
  assert.ok(!h.text().includes("FLYING"), h.text());
  assert.ok(h.text().includes(RELAY_LINE));
  assert.strictEqual(h.part("st-line1").style.color, TABLES.lines.relay_lost[2]);
  assert.match(h.frameStyle(), /dashed/);
  assert.ok(!h.text().includes("F →"));
  const n = h.setCalls().length;
  h.key("f");
  await h.tick(50);
  assert.strictEqual(h.setCalls().length, n, "nothing to flip");
  h.up("f");
  h.status(DRIVE_OK);
  assert.ok(h.text().includes("FLYING"), "a fresh line brings it back without a click");
});

test("no FLYING with input=none (grey lines, no F in the footer)", async () => {
  const h = setup();
  h.relayLine = ROOM_IDLE;
  await h.tick(10);
  h.down();
  await h.tick(1300);
  assert.ok(h.joyLog().length > 0, "armed and publishing");
  assert.ok(!h.text().includes("FLYING"), h.text());
  assert.ok(h.text().includes(TABLES.lines.room_idle[0]));
  assert.strictEqual(h.part("st-line1").style.color, TABLES.lines.room_idle[2]);
  assert.ok(!h.text().includes("F →"), h.text());
  assert.match(h.frameStyle(), /dashed/);
  h.key("f");
  await h.tick(50);
  assert.strictEqual(h.setCalls().length, 0);
  h.relayLine = ROOM_OK;
  await h.tick(250);
  assert.ok(h.text().includes("FLYING"));
  assert.ok(h.text().includes("F → drive mode"), h.text());
});

test("publish failure shows the red line and keeps the panel alive", async () => {
  const h = setup();
  await fly(h);
  h.publishThrows = () => true;
  await h.tick(200);
  assert.ok(h.text().includes(RELAY_LINE), h.text());
  assert.ok(!h.text().includes("FLYING"));
  h.key("ArrowUp");                  // keys still work, nothing throws out of the handlers
  h.publishThrows = () => false;
  await h.tick(2200);
  assert.ok(h.text().includes("FLYING"), "recovers: " + h.text());
  // One failure in the middle of the five zeros cannot stop the rest or escape.
  let i = 0;
  const attempts = h.publishAttempts;
  h.publishThrows = () => ++i === 2;
  h.fireWin("blur");
  assert.strictEqual(h.publishAttempts - attempts, 5);
  assert.ok(h.text().includes(RELAY_LINE));
  // A panel with every call failing still cleans up.
  h.publishThrows = () => true;
  h.cleanup();
  assert.strictEqual(h.clock.live(), 0);
});

test("another source on the topic refuses to arm and names the topic; re-click re-checks", async () => {
  const h = setup();
  h.relayLine = DRIVE_OK;
  await h.tick(10);
  h.down();
  await h.tick(300);
  h.joy();
  const refusal = "Another source is publishing /joy (the keyboard window or a pad). Close it first.";
  assert.ok(h.text().includes(refusal), h.text());
  assert.strictEqual(h.part("st-notice").style.color, TABLES.lines.relay_lost[2]);
  assert.ok(!h.subs.includes("/joy"), "stops listening");
  await h.tick(2000);
  assert.strictEqual(h.joyLog().length, 0, "stays disarmed");
  assert.ok(h.text().includes(CLICK));
  h.down();
  assert.ok(h.text().includes(CHECKING));
  assert.ok(!h.text().includes(refusal), "a click clears the old refusal");
  await h.tick(300);
  h.joy();
  assert.ok(h.text().includes(refusal), "still there: refused again");
  h.down();
  await h.tick(1100);
  assert.ok(h.text().includes("FLYING drone_1"), "the source closed: armed");
});

test("own trailing zeros do not trip the check (listen starts 0.5 s after the last disarm)", async () => {
  const h = setup();
  await fly(h);
  const t0 = h.clock.now();
  h.fireWin("blur");
  h.subLog.length = 0;
  await h.tick(100);
  h.down();
  assert.ok(h.text().includes(CHECKING));
  assert.ok(!h.subs.includes("/joy"), "not listening yet");
  await h.tick(100);
  h.joy();                           // the bridge echoes our own zero
  await h.tick(200);
  h.joy();
  assert.ok(!h.text().includes("Another source"), h.text());
  await h.tick(150);
  const firstListen = h.subLog.find((s) => s.topics.includes("/joy"));
  assert.ok(firstListen.t - t0 >= 500, "listen started at +" + (firstListen.t - t0) + " ms");
  assert.ok(firstListen.t - t0 < 520);
  await h.tick(900);
  assert.ok(!h.text().includes("FLYING"), "1 s of listening is not over at +1.45 s");
  await h.tick(100);
  assert.ok(h.text().includes("FLYING"), h.text());
});

test("selector: choosing drone_2 disarms with zeros on the old topic, re-targets all templates, unadvertises the old topic", async () => {
  const h = setup(MULTI);
  h.relayTopic = "/drone_1/teleop_frame/status";
  await fly(h);
  assert.deepStrictEqual(h.subs, ["/drone_1/teleop_frame/status"]);
  h.key("ArrowUp");
  await h.tick(100);
  const n = h.joyLog().length;
  h.relayLine = null;
  const sel = h.select();
  assert.strictEqual(sel.disabled, false);
  sel.value = "drone_2";
  dispatch(sel, "change", {});
  const zeros = h.joyLog().slice(n);
  assert.strictEqual(zeros.length, 5);
  for (const p of zeros) { assert.strictEqual(p.topic, "/drone_1/joy"); assert.ok(isZeros(p.message)); }
  assert.deepStrictEqual(h.unadvertised, ["/drone_1/joy"]);
  assert.strictEqual(h.advertised.at(-1).topic, "/drone_2/joy");
  assert.deepStrictEqual(h.subs, ["/drone_2/teleop_frame/status"]);
  assert.strictEqual(h.saved.selected, "drone_2");
  await h.tick(50);
  assert.strictEqual(h.getCalls().at(-1).service, "/drone_2/safe_teleop/get_parameters");
  assert.ok(h.text().includes(CLICK), "waits for a click");
  assert.ok(h.text().includes(RELAY_LINE), "the old drone's status does not carry over");
  h.status(DRIVE_OK, "/drone_1/teleop_frame/status");
  assert.ok(h.text().includes(RELAY_LINE), "the old topic is ignored");
  h.relayTopic = "/drone_2/teleop_frame/status";
  h.relayLine = DRIVE_OK;
  await h.tick(600);
  h.down();
  await h.tick(1100);
  assert.ok(h.text().includes("FLYING drone_2"), h.text());
  assert.strictEqual(h.joyLog().at(-1).topic, "/drone_2/joy");
  h.key("f");
  await h.tick(50);
  assert.strictEqual(h.setCalls().at(-1).service, "/drone_2/teleop_frame/set_parameters");
});

test("one drone: selector greyed", async () => {
  const h = setup();
  const sel = h.select();
  assert.strictEqual(sel.disabled, true);
  assert.strictEqual(sel.value, "drone_1");
  assert.strictEqual(sel.children.length, 1);
  assert.ok(!setup(MULTI).select().disabled);
});

test("no BODY, WORLD or CMU anywhere in the rendered text across all states", async () => {
  const seen = [];
  const snap = (h) => { for (const n of walk(h.root)) seen.push(n._text, n.title); };
  const words = /body|world|cmu/i;
  let h = setup();
  snap(h);
  h.down(); snap(h);
  await h.tick(300); h.joy(); snap(h);
  h = setup();
  for (const line of [DRIVE_OK, ROOM_OK, ROOM_IDLE,
    "frame=body pending=world heading_deg=1.0 heading_age_s=0.01 guard=ok input=ok",
    "frame=world pending=body heading_deg=1.0 heading_age_s=0.01 guard=ok input=ok",
    "frame=body pending=none heading_deg=nan heading_age_s=nan guard=stale input=ok",
    "frame=body pending=none heading_deg=1.0 heading_age_s=0.01 guard=jump input=ok",
    "garbage"]) {
    h.status(line); snap(h);
    h.relayLine = line;
    await h.tick(10);
  }
  await fly(h); snap(h);
  h.key("ArrowUp"); snap(h);
  h.key("f"); await h.tick(50); snap(h);
  h.up("f");
  h.key(" "); snap(h);
  h.publishThrows = () => true; await h.tick(100); snap(h);
  h.publishThrows = () => false;
  h.setReply = { results: [{ successful: false, reason: "stick_frame world BODY CMU" }] };
  await h.tick(2100);
  h.key("f"); await h.tick(50); snap(h);
  h.fireWin("blur"); snap(h);
  h = setup({}, (x) => { x.getParams = "reject"; }); await h.tick(2100); snap(h);
  h = setup({}, (x) => { x.params.teleop_controller = "ps5_usb"; }); await h.tick(50); snap(h); h.down(); snap(h);
  const bad = seen.filter((s) => words.test(s));
  assert.deepStrictEqual(bad, []);
});

// ─── behaviour the review focus names ──────────────────────────────────────────
test("key aliases: arrow keys and space go through the real event names", async () => {
  const h = setup();
  await fly(h);
  const d = TABLES.profiles.dragonrise_usb;
  for (const [key, axis, sign] of [["ArrowUp", d.forward_axis, 1], ["ArrowDown", d.forward_axis, -1], ["ArrowLeft", d.left_axis, 1], ["ArrowRight", d.left_axis, -1],
    ["w", d.climb_axis, 1], ["s", d.climb_axis, -1], ["a", d.yaw_axis, 1], ["d", d.yaw_axis, -1]]) {
    h.key(key);
    await h.tick(60);
    near(h.lastAxes()[axis], sign * 0.575);
    h.up(key);
    await h.tick(60);
    assert.ok(isZeros(h.joyLog().at(-1).message), key + " returns to zero");
  }
  h.key("3");
  assert.ok(h.text().includes("100 % = 2.0 m/s"), h.text());
  h.key("1");
  assert.ok(h.text().includes("25 % = 0.5 m/s"), h.text());
});

test("only the flying keys are handled: Tab, others and shortcuts with Ctrl pass through", async () => {
  const h = setup();
  await fly(h);
  for (const key of ["Tab", "q", "Escape", "F5", "4"]) {
    const ev = h.key(key);
    assert.ok(!ev.prevented && !ev.stopped, key);
  }
  for (const props of [{ ctrlKey: true }, { metaKey: true }, { altKey: true }]) {
    const ev = h.key("s", props);
    assert.ok(!ev.prevented && !ev.stopped, JSON.stringify(props));
  }
  await h.tick(60);
  assert.ok(isZeros(h.joyLog().at(-1).message), "Ctrl+S is not a descend");
  for (const key of ["ArrowUp", "w", " ", "f", "1", "2", "3"]) {
    const ev = h.key(key);
    assert.ok(ev.prevented && ev.stopped, key);
    h.up(key);
  }
  h.key("w");
  h.up("w", { ctrlKey: true });      // a modifier pressed mid-hold does not leave the key stuck
  await h.tick(60);
  assert.ok(isZeros(h.joyLog().at(-1).message));
});

test("the selector never arms; touching it disarms; Tab onto it disarms", async () => {
  const h = setup(MULTI);
  h.relayTopic = "/drone_1/teleop_frame/status";
  h.relayLine = DRIVE_OK;
  await h.tick(10);
  dispatch(h.select(), "pointerdown", { button: 0 });
  assert.ok(!h.text().includes(CHECKING));
  await h.tick(1200);
  assert.strictEqual(h.joyLog().length, 0);
  h.down();
  await h.tick(1100);
  assert.ok(h.text().includes("FLYING"));
  let n = h.joyLog().length;
  dispatch(h.select(), "pointerdown", { button: 0 });
  assert.strictEqual(h.joyLog().length, n + 5);
  assert.ok(!h.text().includes("FLYING"));
  await h.tick(600);
  h.down();
  await h.tick(1100);
  n = h.joyLog().length;
  dispatch(h.root, "focusout", { relatedTarget: h.select() });
  assert.strictEqual(h.joyLog().length, n + 5, "keys on the selector would change its value");
  await h.tick(600);
  h.down();
  await h.tick(1100);
  dispatch(h.root, "focusout", { relatedTarget: h.root });
  assert.ok(h.text().includes("FLYING"), "focus staying on the root is not leaving");
});

test("a check in progress is cancelled by every way out, with nothing published", async () => {
  for (const out of [(h) => h.fireWin("blur"), (h) => dispatch(h.root, "focusout", { relatedTarget: null }),
    (h) => { h.doc.hidden = true; h.fireDoc("visibilitychange"); }]) {
    const h = setup();
    h.relayLine = DRIVE_OK;
    await h.tick(10);
    h.down();
    await h.tick(300);
    out(h);
    assert.ok(!h.subs.includes("/joy"));
    assert.ok(h.text().includes(CLICK));
    await h.tick(2000);
    assert.strictEqual(h.joyLog().length, 0);
    assert.ok(!h.text().includes("FLYING"));
  }
  const h = setup();
  h.down();
  await h.tick(300);
  h.cleanup();
  assert.strictEqual(h.joyLog().length, 0, "an idle cleanup sends no zeros");
  assert.strictEqual(h.clock.live(), 0);
});

test("safe_teleop: dead zone and layout from get_parameters; not found yet in the footer; unknown controller refuses", async () => {
  // not answering: defaults and the footer line, and flying still works
  let h = setup({}, (x) => { x.getParams = "reject"; });
  await h.tick(50);
  assert.ok(h.part("st-footer").textContent.includes("safe_teleop not found yet"), h.text());
  assert.ok(!h.text().includes("m/s"));
  h.relayLine = DRIVE_OK;
  await h.tick(10);
  h.down();
  await h.tick(1100);
  h.key("ArrowUp");
  await h.tick(60);
  near(h.lastAxes()[TABLES.profiles.dragonrise_usb.forward_axis], 0.5 * (1 - TABLES.deadzone) + TABLES.deadzone);

  // answering: the live layout, dead zone and speed, re-read every 2 s
  h = setup({}, (x) => { x.params = { teleop_controller: "xbox_usb", deadzone: 0.3, max_speed_mps: 4.0 }; });
  await fly(h);
  assert.ok(!h.text().includes("safe_teleop not found yet"), h.text());
  h.key("ArrowUp");
  await h.tick(60);
  near(h.lastAxes()[TABLES.profiles.xbox_usb.forward_axis], 0.3 + 0.5 * 0.7);
  assert.ok(h.text().includes("50 % = 2.0 m/s"), h.text());
  const n = h.getCalls().length;
  assert.deepStrictEqual(h.getCalls()[0].req, { names: ["teleop_controller", "deadzone", "max_speed_mps"] });
  h.params.max_speed_mps = 6.0;
  await h.tick(2100);
  assert.ok(h.getCalls().length > n);
  assert.ok(h.text().includes("50 % = 3.0 m/s"), h.text());

  // answered before, now silent: that is a service failure, so the red line
  h.getParams = "reject";
  await h.tick(2100);
  assert.ok(h.text().includes(RELAY_LINE), h.text());
  assert.ok(!h.text().includes("FLYING"));
  assert.ok(h.part("st-footer").textContent.includes("safe_teleop not found yet"));
  h.getParams = "answer";
  await h.tick(2100);
  assert.ok(h.text().includes("FLYING"), h.text());

  // unknown controller: refuses, says which
  h = setup({}, (x) => { x.params.teleop_controller = "ps5_usb"; });
  h.relayLine = DRIVE_OK;
  await h.tick(50);
  h.down();
  await h.tick(1500);
  assert.strictEqual(h.joyLog().length, 0);
  assert.ok(h.part("st-notice").textContent.includes("ps5_usb"), h.text());
  assert.ok(!h.text().includes("FLYING"));

  // the controller changes to an unknown one while flying: zeros, disarmed
  h = setup();
  await fly(h);
  const m = h.joyLog().length;
  h.params.teleop_controller = "ps5_usb";
  await h.tick(2100);
  const after = h.joyLog().slice(m).filter((p) => isZeros(p.message));
  assert.ok(after.length >= 5);
  assert.ok(!h.text().includes("FLYING"));
  const k = h.joyLog().length;
  await h.tick(500);
  assert.strictEqual(h.joyLog().length, k);

  // a read that never answers is dropped, the next one goes out
  h = setup({}, (x) => { x.getParams = "never"; });
  await h.tick(50);
  const c = h.getCalls().length;
  await h.tick(4100);
  assert.ok(h.getCalls().length > c, "dropped and asked again");
});

test("heading lost: the drone holds, so no FLYING", async () => {
  const h = setup();
  await fly(h);
  h.relayLine = "frame=body pending=none heading_deg=nan heading_age_s=nan guard=stale input=ok";
  await h.tick(250);
  assert.ok(h.text().includes(TABLES.lines.heading_lost[0]));
  assert.ok(!h.text().includes("FLYING"));
  assert.match(h.frameStyle(), /dashed/);
  assert.ok(h.joyLog().length > 0);
});

test("the topic list going empty is a dead link: the red line at once", async () => {
  const h = setup();
  await fly(h);
  let done = 0;
  h.ctx.onRender({ topics: [{ name: "/joy" }] }, () => { done++; });
  assert.ok(h.text().includes("FLYING"));
  h.ctx.onRender({ topics: [] }, () => { done++; });
  assert.ok(!h.text().includes("FLYING"));
  assert.ok(h.text().includes(RELAY_LINE));
  h.ctx.onRender({ topics: [{ name: "/joy" }] }, () => { done++; });
  assert.ok(h.text().includes("FLYING"));
  assert.strictEqual(done, 3);
});

test("settings: saved templates and drones, settings editor changes re-target and disarm", async () => {
  const h = setup({ drones: ["drone_3"], selected: "gone", joyTopicTemplate: "/{name}/joy" });
  assert.strictEqual(h.select().value, "drone_3", "a saved drone no longer listed falls back to the first");
  assert.strictEqual(h.advertised[0].topic, "/drone_3/joy");
  h.relayLine = DRIVE_OK;
  await fly(h);
  assert.ok(h.text().includes("FLYING drone_3"));
  assert.ok(h.settings, "uses updatePanelSettingsEditor as the basestation panel does");
  const n = h.joyLog().length;
  h.settings.actionHandler({ action: "update", payload: { path: ["strip", "joyTopicTemplate"], value: "/x/{name}/joy" } });
  assert.strictEqual(h.joyLog().length, n + 5);
  assert.strictEqual(h.joyLog().at(-1).topic, "/drone_3/joy");
  assert.deepStrictEqual(h.unadvertised, ["/drone_3/joy"]);
  assert.strictEqual(h.advertised.at(-1).topic, "/x/drone_3/joy");
  assert.strictEqual(h.saved.joyTopicTemplate, "/x/{name}/joy");
  h.settings.actionHandler({ action: "update", payload: { path: ["strip", "drones"], value: "drone_3, drone_4" } });
  assert.deepStrictEqual(h.saved.drones, ["drone_3", "drone_4"]);
  assert.strictEqual(h.select().disabled, false);
  assert.strictEqual(h.select().children.length, 2);
  h.settings.actionHandler({ action: "update", payload: { path: ["strip", "drones"], value: " , " } });
  assert.deepStrictEqual(h.saved.drones, ["drone_1"], "an empty list falls back to the default");
});

test("a data source without publish, advertise or services: the panel stays up and says so", async () => {
  const clock = makeClock();
  Object.assign(ext.__clock, { now: clock.now, setInterval: clock.setInterval, clearInterval: clock.clearInterval, setTimeout: clock.setTimeout, clearTimeout: clock.clearTimeout });
  const doc = { defaultView: null, activeElement: null, hidden: false, createElement: (t) => makeNode(t, doc), addEventListener() {}, removeEventListener() {} };
  const root = makeNode("div", doc);
  const subs = [];
  const ctx = { initialState: undefined, panelElement: root, saveState() {}, watch() {}, subscribe: (s) => subs.push(s) };
  let initPanel;
  ext.activate({ registerPanel: (def) => { initPanel = def.initPanel; } });
  const clean = initPanel(ctx);
  assert.ok(root.textContent.includes("safe_teleop not found yet"));
  dispatch(root, "pointerdown", { button: 0 });
  clock.advance(1100);
  assert.ok(root.textContent.includes(RELAY_LINE));
  assert.ok(!root.textContent.includes("FLYING"));
  clean();
  assert.strictEqual(clock.live(), 0);
});

test("a right click does not arm; onRender with nothing new still calls done", async () => {
  const h = setup();
  h.down({ button: 2 });
  assert.ok(!h.text().includes(CHECKING));
  let done = 0;
  h.ctx.onRender({}, () => { done++; });
  assert.strictEqual(done, 1);
  h.deliver([{ topic: "/teleop_frame/status", message: {} }]);
  assert.ok(h.text().includes(RELAY_LINE), "a malformed status is no status");
});

(async () => {
  const failed = [];
  for (const [name, fn] of cases) {
    try {
      await fn();
      console.log("  ok   " + name);
    } catch (e) {
      failed.push(name);
      console.log("  FAIL " + name + "\n       " + String(e && e.message).split("\n")[0]);
    }
  }
  if (failed.length) {
    console.log(`smoke FAILED ${failed.length} of ${cases.length}`);
    process.exit(1);
  }
  console.log(`smoke ok ${cases.length} cases`);
})();
