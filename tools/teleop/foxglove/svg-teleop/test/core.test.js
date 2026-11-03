"use strict";
// Strip logic equals keymap.py: every fixture case, plus fillTemplate (no Python twin). Run: node test/core.test.js
const assert = require("assert");
const path = require("path");
const fixtures = require("./fixtures.json");
const C = require(path.join(__dirname, "..", "dist", "extension.js")).__core;
assert.ok(C, "module.exports.__core missing");
const { KeyState, stickFor, parseStatus, headerLines, footerLine, flipTarget, fillTemplate } = C;
let n = 0;

for (const c of fixtures.axes) {
  const ks = new KeyState(c.profile, c.deadzone);
  ks.setScale(c.scale);
  for (const k of c.held) ks.press(k);
  if (c.space) ks.press("space", 100);
  const got = ks.axes();
  assert.strictEqual(got.length, c.axes.length);
  c.axes.forEach((v, i) => assert.ok(Math.abs(got[i] - v) < 1e-9, `axes ${JSON.stringify(c)} [${i}] ${got[i]} != ${v}`));
  assert.strictEqual(ks.buttons().length, 15);
  if (c.space) assert.deepStrictEqual(ks.held(), []);
  n++;
}

for (const c of fixtures.status) {
  const st = c.line === null ? null : parseStatus(c.line);
  const h = headerLines(st, c.seen);
  assert.deepStrictEqual(Array.from(h), c.header, JSON.stringify(c));
  assert.strictEqual(footerLine(st), c.footer, JSON.stringify(c));
  assert.strictEqual(flipTarget(st), c.flip, JSON.stringify(c));
  n++;
}

// parseStatus: nan headings, garbled tokens
const p = parseStatus("frame=body heading_deg=oops heading_age_s=1.5 junk x=");
assert.ok(Number.isNaN(p.heading_deg));
assert.strictEqual(p.heading_age_s, 1.5);
assert.strictEqual(p.frame, "body");
assert.strictEqual(p.x, "");
assert.ok(!("junk" in p));
n++;

// KeyState behaviour that has no fixture
const k = new KeyState("dragonrise_usb", 0.15);
k.press("w"); k.press("s");
assert.strictEqual(k.axes()[1], 0);                 // opposite keys cancel
k.release("w"); k.release("s");
assert.deepStrictEqual(k.held(), []);
k.press("up");
assert.strictEqual(k.statusText(10, 2), "pitch: forward  ·  50 % of top speed = 1.0 m/s");
assert.strictEqual(k.statusText(10), "pitch: forward  ·  50 % of top speed");
k.press("space", 20);
assert.ok(k.statusText(20.5).startsWith("STOP"));
assert.ok(k.statusText(21.5).startsWith("hold (no key)"));
k.press("up"); assert.ok(k.statusText(30).startsWith("pitch"));   // a flight key ends STOP
k.allUp(); assert.deepStrictEqual(k.held(), []);
k.press("zzz"); assert.deepStrictEqual(k.held(), []);              // unknown keys ignored
k.press("3"); assert.ok(k.statusText(40).includes("100 %"));
assert.strictEqual(stickFor(0, 0.15), 0);
assert.ok(Math.abs(stickFor(-0.5, 0.15) + 0.575) < 1e-12);
n++;

// fillTemplate
assert.strictEqual(fillTemplate("/{name}/joy", "drone_1"), "/drone_1/joy");
assert.strictEqual(fillTemplate("/joy", "drone_1"), "/joy");
assert.strictEqual(fillTemplate("/{name}/a/{name}", "d2"), "/d2/a/d2");
assert.strictEqual(fillTemplate("/{other}", "d"), "/{other}");
n++;

console.log(`core ok ${n} cases`);
