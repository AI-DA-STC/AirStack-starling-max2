# MOTIVE — operating the mocap PC (calibration, rigid bodies, streaming)

> **Who this is for:** anyone sitting at the Windows **Motive PC** in the hangar
> (`192.168.9.124` as of 2026-08-28 — the hangar assigns IPs by switch port, so
> re-check against [CONFIG.md](CONFIG.md) each session). No robotics background needed.
> You need this doc when **cameras got moved or bumped, rigid bodies change, or
> tracking looks wrong**. For the laptop-side receiver (`./mocap.sh`), see
> [MOCAP.md](MOCAP.md) — this doc is everything *upstream* of that.

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

---

## 1 · THE GOLDEN RULE — the origin IS the map

**The mocap origin and ground plane define every coordinate the drone flies to.**
Every `hover_positions` entry, every goal, every geofence limit in the config yamls
([CONFIG.md](CONFIG.md) ground-side table) is a position *in the frame you set during
calibration*. There is no second reference — if you recalibrate, or nudge the
calibration square, the "same numbers" now mean different places in the room.
A 30 cm origin shift moves the takeoff spot, every waypoint, AND the fence by 30 cm.

So after **ANY** recalibration or ground-plane change, before anyone flies:

1. Re-run the **frame hand-check** ([RUNBOOK.md](RUNBOOK.md) §B step 6): carry the
   drone North → `position[0]`↑, East → `[1]`↑, lift up → `[2]`↓ (PX4 counts down as
   positive).
2. Put the drone on the floor and check its reported height reads **z ≈ 0.05 m**
   (0.03–0.07 m is fine — that's the markers sitting above the floor). See §5.

Two minutes of checking versus a drone that confidently flies to the wrong place.

## 2 · Calibration, in plain terms

Calibration teaches the cameras where they are relative to each other and where
"the floor" and "forward" are. Motive's calibration pane walks you through it;
the human steps are:

1. **Mask stray reflections.** With the volume empty (no drone, no stray markers),
   run the masking step — it blanks out shiny spots (metal fittings, screens,
   another camera's LED ring) so they can't masquerade as markers later. If a
   camera view is speckled with white dots when nothing is in the volume, mask first.
2. **Wand the volume.** Wave the calibration wand through the space the drone will
   use — slowly, covering the whole volume *including low near the floor and up
   high*, until every camera has collected plenty of samples. Thin coverage in a
   corner = poor tracking in that corner later.
3. **Apply and check quality.** Motive reports a residual/quality figure per camera
   when it computes the result. If it flags a camera as poor, re-wand — don't accept
   a bad calibration and hope.
4. **Set the ground plane.** Place the **calibration square** flat on the floor at
   the spot you want as the origin `(0, 0, 0)`, oriented the way you want the axes,
   and apply the ground-plane step. This single action fixes the origin, the floor
   height, and the axis directions — it is the moment the Golden Rule is made.

**Our axis convention** (photos: [`pictures/mocap_axis_1.png`](pictures/mocap_axis_1.png),
[`pictures/mocap_axis_2.png`](pictures/mocap_axis_2.png)):

| Axis | Calibration-square arm | Means |
|---|---|---|
| **x** | red | "East" |
| **y** | green | "North" |
| **z** | (up out of the floor) | up |

Match the square's red arm to what we call East before applying. If you set it
differently, the frame hand-check (§1) will catch it — that's what it's for.

**When to recalibrate:** a camera was bumped/moved/remounted, markers "swim" or
jump when the drone is still, residuals have crept up, or the floor-z check (§5)
reads wrong. **Don't** recalibrate casually — every recalibration re-triggers the
§1 checks.

## 3 · Rigid bodies (the thing Motive actually tracks)

A "rigid body" is Motive's name for one tracked object: a marker pattern it
recognises as a single thing. Rules that have each cost someone an afternoon:

- **Markers must be ASYMMETRIC.** 4–5 markers, no two spacings alike. A symmetric
  pattern (square, evenly spaced line) looks identical rotated 180° — Motive will
  happily flip the drone's orientation mid-flight. (MILESTONES M2 step 1.)
- **Create the body with the drone facing +X.** Place the drone in the volume with
  its forward axis along the red/x/"East" axis, *then* select its markers and create
  the rigid body. Motive defines "this body's forward" from that moment. A body
  created at an angle has a permanent yaw offset — invisible at rest, a fly-away
  in flight.
- **Name it exactly `drone_1`** — lowercase, underscore. The name becomes the ROS
  topic letter-for-letter (`/drone_1/pose`); `drone1` or `Drone_1` silently
  publishes to a topic nothing listens to.
- **Don't rename or add bodies mid-session.** Every receiver reads the body list
  once at startup. After any body change: restart `./mocap.sh` on the laptop — and
  never rename while the old `natnet_ros2` driver runs (it can crash on the next
  frame). Old bodies from other projects (`cf1`…`cf10`) showing up is harmless.

## 4 · Data Streaming pane checklist

Reference photo of ours set correctly:
[`pictures/check_motive_ip_address.jpg`](pictures/check_motive_ip_address.jpg).
In the streaming pane, confirm:

- [ ] **Broadcast Frame Data: ON** (streaming enabled at all)
- [ ] **Up Axis: Z** — Motive defaults to Y; the classic frame bug
- [ ] **Local Interface = the Motive PC's hangar-LAN IP** (the `192.168.9.x` one —
      read it off this row, it's the authoritative Motive IP for CONFIG.md)
- [ ] **Rigid Bodies: ON** (checked in the streamed-data list)

**About the Multicast/Broadcast selector:** whatever the GUI shows, our rig
effectively **broadcasts** — a hidden profile flag
(`BroadcastInsteadOfMulticast="true"`) overrides the GUI. That's fine and you don't
need to fight it: our `./mocap.sh` bridge hears broadcast (it's the whole reason it
exists). Full story: [MOCAP.md](MOCAP.md) §3.

**Frame rate:** currently **50 Hz** (lives in Motive's camera settings, not this
pane, and drifts when profiles change). Changing it is fine — the whole pipeline
follows Motive's rate — but **update [CONFIG.md](CONFIG.md)** so the next person
running `ros2 topic hz` expects the right number.

## 5 · Verify from the laptop — after ANY Motive change

Never walk away from the Motive PC on faith. On the **laptop** (with `./mocap.sh`
running):

```bash
./mocap.sh check                    # 6-second wire test — is pose data arriving at all?
```

Then in the robot container ([RUNBOOK.md](RUNBOOK.md) §B for how to get one):

```bash
ros2 topic hz   /drone_1/pose       # want Motive's rate — 50 Hz as of 2026-08-28
ros2 topic echo /drone_1/pose --once   # with the drone ON THE FLOOR
```

**Floor sanity:** that echo's `z` must read **≈ 0.03–0.07 m** (marker height above
the floor). Near zero and steady = origin and ground plane are sane. Anything else →
§6 last row. If you calibrated, finish with the full §1 hand-check.

## 6 · Troubleshooting (Motive-side symptoms)

| Symptom | Cause & fix |
|---|---|
| `./mocap.sh check` says nothing on the wire | Streaming disabled (Broadcast Frame Data off), wrong **Local Interface** selected, or the Motive PC is off the hangar LAN — re-do §4, confirm the PC's IP matches [CONFIG.md](CONFIG.md) (it drifts). |
| Body tracks fine in Motive, but no `/drone_1/pose` on the laptop | Name mismatch (must be exactly `drone_1`), or the bridge started before the body existed — fix the name and **restart `./mocap.sh`** (body list is read once at startup). |
| z reads wrong with the drone on the floor | Ground plane / origin problem. **STOP — do not fly.** Recalibrate (§2), re-set the ground plane with the square, then §1's hand-check + floor check. |
| Markers jitter or the body flips orientation | Stray reflections (re-mask, §2 step 1), thin wanding coverage in that spot, or a symmetric marker pattern (§3 — rebuild the body asymmetric). |
| Everything Motive-side looks right, still no data | The problem is downstream — switch to [MOCAP.md](MOCAP.md) §5 (laptop/bridge troubleshooting). |
