# MOCAP — how the drone knows where it is (and how to run it)

> **Who this is for:** anyone in the AI.R / STC lab, no robotics background needed.
> The short version: indoors there is no GPS, so ceiling cameras act as "indoor GPS".
> This doc covers the whole chain: the **Motive PC** that computes poses (calibration,
> rigid bodies, streaming setup) and the **laptop bridge** that gets them into AirStack
> (`./mocap.sh`) — why we built the bridge, and how to run, verify, and troubleshoot
> both sides.
> First verified working at the AI.R STC hangar **2026-08-27** (re-verified 08-28).

---

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

## 1 · Why motion capture, in plain terms

A drone outdoors uses GPS to know its position. Indoors, GPS does not reach — so the
drone would be flying blind. Our hangar solves this with **motion capture ("mocap")**:
eight OptiTrack infrared cameras on the ceiling watch small reflective balls
("markers") glued to the drone. A Windows PC running **Motive** (the OptiTrack
software) combines the eight camera views and computes the drone's exact position and
orientation many times per second (50 Hz at the moment — configurable up to 240 Hz),
to about a millimetre.

That position still has to travel from the Motive PC into the drone's flight
controller. The chain looks like this:

```
8 ceiling cameras
      │  (infrared images)
      ▼
Motive PC  (192.168.9.x — computes poses, streams them onto the wired LAN)   ← §6
      │  ("NatNet" — OptiTrack's streaming protocol — UDP port 1511, at Motive's rate)
      ▼
Ground-control LAPTOP — ./mocap.sh bridge          ← this repo, §2-§5
      │  (ROS 2 topic — a named data channel:  /drone_1/pose)
      ▼
AirStack robot container — mocap_bridge.py
      │  (PX4 topic:  /drone_1/fmu/in/vehicle_visual_odometry)
      ▼
Drone's flight controller (PX4 EKF2 — the autopilot's sensor-fusion estimator)
      →  stable indoor flight
```

Everything below the laptop row is unchanged CMU AirStack (their
[`experiment.md`](../AirStack/robot/ros_ws/src/svg_ground_control/experiment.md) §B4b
onward still applies). What this repo adds is the **laptop row**: our own receiver
that actually works with our hangar's Motive configuration.

## 2 · Quick start

One-time setup (needs internet, ~5 min — downloads and builds the receiver):

```bash
cd ~/AirStack-starling-max2        # this repo's root — or wherever you cloned it
./mocap.sh setup
```

Every session — run on the **laptop** (a normal terminal, NOT inside the docker
container):

```bash
./mocap.sh            # leave running; Ctrl+C stops it
```

Verify inside the robot container — if the stack isn't up yet:
`cd ~/AirStack-starling-max2/AirStack && ./airstack.sh up robot-desktop`, then
`./airstack.sh connect robot --command=bash` (details: [RUNBOOK.md](RUNBOOK.md) §B):

```bash
ros2 topic hz /drone_1/pose        # want Motive's rate — 50 Hz as of 2026-08-28
```

If that shows a steady rate matching Motive's, mocap is done — continue with the normal
[RUNBOOK](RUNBOOK.md) §B flow (interfaces, commander, RViz).

A second sanity check, especially after any calibration change at the Motive PC (§6.1):
with the drone **on the floor**,

```bash
ros2 topic echo /drone_1/pose --once
```

should show `z` ≈ **0.03–0.07 m** (the markers sitting above the floor). Near zero and
steady = the origin and ground plane are sane. Anything else → the "z reads wrong with
the drone on the floor" row in §5,
and don't fly until you've re-run §6.1's full hand-check.

Something wrong? First move is always:

```bash
./mocap.sh check      # 6-second network test, prints a plain-English verdict
```

It tells you whether pose data is reaching the laptop at all, at what rate, and in
which transmission mode — separating "network/Motive problem" from "software
problem" in one step. More tools: `./mocap.sh stop` (kill a bridge left running in
a lost terminal), `./mocap.sh status`.

Tracking more than one rigid body (names must match Motive exactly):

```bash
MOCAP_BODIES="drone_1 drone_2" ./mocap.sh
```

## 3 · Why we don't use the CMU receiver (the interesting part)

CMU's AirStack ships a receiver called `natnet_ros2`, built on OptiTrack's official
"NatNet SDK". It worked on CMU's rig. On ours it connects, lists the rigid bodies
(a "rigid body" is Motive's term for one tracked object — the marker pattern it
recognises as a single thing, e.g. `drone_1`) — and then publishes **nothing**,
forever, with no error. We debugged this on
2026-08-27; the cause is worth understanding because it looks like magic until you
see it.

**The radio analogy.** Motive can send pose data in two ways:

- **Multicast** — like a radio station on one specific frequency. Receivers must
  tune to exactly that frequency (the "group address" 239.255.42.99).
- **Broadcast** — like a PA system announcement to the whole building. Everyone
  on the network hears it, no tuning needed.

Our hangar's Motive is configured for **broadcast** (a profile setting,
`BroadcastInsteadOfMulticast="true"`). The official NatNet SDK **only knows how to
tune to the multicast frequency** — it is structurally deaf to broadcast. So
`natnet_ros2` sits tuned to a channel nobody is transmitting on, while the pose
data blasts past it on the PA system. Meanwhile the *setup conversation* with
Motive ("what bodies exist?", "what frame rate?") uses a separate direct channel
that works fine — which is why the driver *looks* connected and healthy in its
startup log. We proved this with a raw network capture: 301 packets in 6 s from the
Motive PC, every one addressed to `255.255.255.255` (broadcast), zero on the
multicast address.

**The fix** is a receiver that simply listens on the port without tuning to a
specific channel — it hears broadcast *and* multicast. That open-source receiver
exists (`motion_capture_tracking`, from the Crazyswarm project, IMRCLab), **but**
its stock version crashes against our Motive: our Motive speaks a newer dialect
(NatNet 4.2), and the receiver mis-reads the "table of contents" Motive sends at
startup and walks off the end of its memory. We patched it to use the length
labels NatNet 4.2 puts on every entry —
[`patches/0003-libmotioncapture-natnet-4.2-modeldef-segfault.patch`](../patches/0003-libmotioncapture-natnet-4.2-modeldef-segfault.patch)
(worth contributing upstream). `./mocap.sh setup` applies this patch automatically.

Finally, the open receiver publishes all bodies bundled into one topic (`/poses`),
while the AirStack pipeline expects one topic per drone (`/drone_1/pose`). A ~40-line
relay ([`mocap/pose_relay.py`](../mocap/pose_relay.py)) converts between the two.
Receiver + relay together are "the bridge" that `./mocap.sh` runs.

**Why not just switch Motive to multicast?** We tried (2026-08-27): the GUI already
*says* Multicast — a hidden profile flag overrides it, and editing the profile file
didn't take effect. Rather than keep fighting a Windows setting we don't fully
control, the bridge accepts the stream however Motive sends it. This is also more
robust: the same bridge works unchanged if Motive is ever switched to multicast,
and the underlying open parser is the same one our Crazyflie setup already trusts
(the closed SDK additionally has a known freeze-forever failure mode after a
network stall, documented in the CrazySwarm2 repo).

## 4 · Corrections to CMU's `experiment.md` (Part B4) for OUR rig

CMU's guide is the source of truth for everything else; these mocap specifics
differ on our setup (checked 2026-08-27):

| CMU's `experiment.md` says | On our rig |
|---|---|
| Launch `natnet_ros2` in the container (§B4) | **Don't** — it cannot receive our Motive's broadcast stream (§3). Run `./mocap.sh` on the laptop instead. Output topics are identical, so every later step is unchanged. |
| serverIP/clientIP "already defaulted to this rig" | Their rig. Ours: Motive `192.168.9.124`, laptop `192.168.9.107` — the launch-file defaults now carry these, but check [CONFIG.md](CONFIG.md) (DHCP drifts). |
| `ros2 topic hz /drone_1/pose` → ~180 Hz | Whatever Motive's capture rate is — **50 Hz** as of 2026-08-28 (it briefly ran at 240 Hz on 08-27 after a profile edit; the rate lives in Motive's camera settings and drifts when profiles change). |
| `pub_rigid_body:=true` "(now the default)" | True as documented — but note if it's ever `false` the driver publishes **nothing at all** (no `/…/pose`, no `/tf`) while still logging "Configured!/Activated!" happily. That cost us hours. |
| Motive body streams as `drone1` (implied by some notes) | The body is **`drone_1`** — underscore. Topic names copy Motive's body name letter-for-letter. |
| §B4b lists its two verify commands (`hz in/vehicle_visual_odometry`, `echo out/vehicle_odometry`) *before* the §B5 commander launch | They can only pass **after** `ground_control.launch.py … use_mocap:=true` is up — that launch is what starts `mocap_bridge`, the publisher of `in/vehicle_visual_odometry` (true on CMU's branch too, verified 2026-08-28). Only §B4b's EKF2 *params* are a genuine before-hand (one-time) prereq. |
| — (not covered) | If Motive assets are added/renamed mid-session: restart the bridge (and never rename while `natnet_ros2` runs — it can crash on the next frame). |

`natnet_ros2` stays in the tree untouched — it is still the right tool on a rig
whose Motive genuinely multicasts, and its command channel remains a handy probe.

## 5 · Troubleshooting

| Symptom | Do this |
|---|---|
| `/drone_1/pose` missing or 0 Hz | Is `./mocap.sh` running on the laptop (`./mocap.sh status`)? Then `./mocap.sh check` and read its verdict. |
| `check` says "nothing on the wire" | On the laptop: cable in the mocap LAN, IP on `192.168.9.x` (`ip -4 -brief addr`)? Can you `ping` the Motive PC ([CONFIG.md](CONFIG.md) has the current IP)? At the Motive PC: is it on, is streaming enabled (Broadcast Frame Data ON), and is **Local Interface** set to its hangar-LAN IP (§6.4)? Note: ping working does NOT prove pose data flows — that's exactly what `check` is for. |
| `check` shows packets but bridge publishes nothing (or: body tracks fine in Motive but no `/drone_1/pose` on the laptop) | A leftover process may be eating the port: `ss -ulpn \| grep 1511`, then `./mocap.sh stop` and restart. Also confirm the body name in Motive is exactly `drone_1` — lowercase, underscore, letter-for-letter (§6.3) — and that the bridge wasn't started *before* the body existed (restart `./mocap.sh` if so; the body list is read once at startup). |
| Rate differs from CONFIG.md's value | Motive's capture rate was changed — fine, but update [CONFIG.md](CONFIG.md) so the next person expects the right number. |
| Bridge worked, then poses froze | Restart the bridge (`Ctrl+C`, rerun). If it recurs, run `check` while frozen: packets still arriving → software side; none → Motive/network side. |
| Renamed/added a rigid body in Motive | Restart the bridge — the body list is read once at startup. |
| `z` reads wrong with the drone on the floor | Ground plane / origin problem. **STOP — do not fly.** Recalibrate (§6.2), re-set the ground plane with the square, then §6.1's hand-check + floor check. |
| Markers jitter or the body flips orientation | Stray reflections (re-mask, §6.2 step 1), thin wanding coverage in that spot, or a symmetric marker pattern (§6.3 — rebuild the body asymmetric). |
| Poses stop while the drone is FLYING | `land` or kill FIRST ([PREFLIGHT.md](PREFLIGHT.md)), debug after — EKF2 drifts within seconds without vision. |
| Setup fails building | Make sure no conda env is active (the script strips miniconda automatically, but exotic Python setups can still interfere); needs ROS 2 Jazzy at `/opt/ros/jazzy`. |

## 6 · At the Motive PC

The sections below are for whoever is sitting at the Windows **Motive PC** in the
hangar (`192.168.9.124` as of 2026-08-28 — the hangar assigns IPs by switch port, so
re-check against [CONFIG.md](CONFIG.md) each session). You need this material when
**cameras got moved or bumped, rigid bodies change, or tracking looks wrong**. It's
everything *upstream* of the laptop bridge covered in §1-§5.

### 6.1 · THE GOLDEN RULE — the origin IS the map

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
   (0.03–0.07 m is fine — that's the markers sitting above the floor), using the
   `ros2 topic echo /drone_1/pose --once` check in §2.

Two minutes of checking versus a drone that confidently flies to the wrong place.

### 6.2 · Calibration, in plain terms

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
   height, and the axis directions — it is the moment the Golden Rule (§6.1) is made.

**Our axis convention** (photos: [`pictures/mocap_axis_1.png`](../pictures/mocap_axis_1.png),
[`pictures/mocap_axis_2.png`](../pictures/mocap_axis_2.png)):

| Axis | Calibration-square arm | Means |
|---|---|---|
| **x** | red | "East" |
| **y** | green | "North" |
| **z** | (up out of the floor) | up |

Match the square's red arm to what we call East before applying. If you set it
differently, the frame hand-check (§6.1) will catch it — that's what it's for.

**When to recalibrate:** a camera was bumped/moved/remounted, markers "swim" or
jump when the drone is still, residuals have crept up, or the floor-z check (§2)
reads wrong. **Don't** recalibrate casually — every recalibration re-triggers the
§6.1 checks.

### 6.3 · Rigid bodies (the thing Motive actually tracks)

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

### 6.4 · Data Streaming pane checklist

Reference photo of ours set correctly:
[`pictures/check_motive_ip_address.jpg`](../pictures/check_motive_ip_address.jpg).
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
exists). Full story: §3.

**Frame rate:** currently **50 Hz** (lives in Motive's camera settings, not this
pane, and drifts when profiles change). Changing it is fine — the whole pipeline
follows Motive's rate — but **update [CONFIG.md](CONFIG.md)** so the next person
running `ros2 topic hz` expects the right number.

## 7 · What exactly is where (technical appendix)

| Piece | Location | Role |
|---|---|---|
| `mocap.sh` | repo root | setup / run / check / stop / status |
| `mocap/motion_capture.yaml` | this repo | Motive PC IP + stream settings (edit here, commit) |
| `mocap/pose_relay.py` | this repo | `/poses` (NamedPoseArray) → per-body `/<name>/pose` (PoseStamped, frame `world`) |
| `mocap/fastdds.xml` | this repo | UDP-only DDS profile — same one the robot container uses, so laptop↔container topics interoperate (shared-memory off) |
| `mocap/probe.py` | this repo | the raw-UDP test behind `./mocap.sh check` |
| `patches/0003-…-modeldef-segfault.patch` | this repo | our NatNet 4.2 fix to libmotioncapture |
| built receiver | `~/mocap_ws` (created by `setup`; override with `MOCAP_WS=…`) | `motion_capture_tracking` @ commit `64d3af2` + patch, built against system ROS Jazzy |

**About `~/mocap_ws`:** it is *generated build output*, not a source tree — any machine
recreates it from this repo with `./mocap.sh setup` (clone → patch → build). Don't hand-edit
it or version it; edit `mocap/` here and commit. The legacy `~/mocap_ws/start_mocap_bridge.sh`
from the original 08-27 debugging still works but is **not** identical to `./mocap.sh`: it
hardcodes extra bodies (`cf1`, `cf8`) and carries a stale copy of the config. Prefer
`./mocap.sh`; delete `~/mocap_ws` any time and re-run `setup` to get a clean rebuild.

Bridge environment (set automatically by `mocap.sh`): `ROS_DOMAIN_ID=1` (the
lab-wide domain, see CONFIG.md), discovery range SUBNET, Fast DDS profile as above.
The robot container runs with host networking, which is why a laptop-side publisher
is indistinguishable from an in-container one.

Data-format notes: `/drone_1/pose` is `geometry_msgs/PoseStamped` in frame
`world`, published reliable/volatile at Motive's rate; `/poses` (bundled, all
bodies) uses sensor-data QoS. Downstream, `svg_ground_control/mocap_bridge.py`
consumes `/{name}/pose` per its `swarm_real.yaml` `mocap_topic_template` — no
changes needed there.
