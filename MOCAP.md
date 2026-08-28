# MOCAP — how the drone knows where it is (and how to run it)

> **Who this is for:** anyone in the AI.R / STC lab, no robotics background needed.
> The short version: indoors there is no GPS, so ceiling cameras act as "indoor GPS".
> This doc explains how that camera data reaches the drone, why we built our own
> receiver (`./mocap.sh`), and how to run and troubleshoot it.
> First verified working at the AI.R STC hangar **2026-08-27** (re-verified 08-28).

---

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
Motive PC  (192.168.9.x — computes poses, streams them onto the wired LAN)
      │  ("NatNet" — OptiTrack's streaming protocol — UDP port 1511, at Motive's rate)
      ▼
Ground-control LAPTOP — ./mocap.sh bridge          ← this repo, this doc
      │  (ROS 2 topic — a named data channel:  /drone_1/pose)
      ▼
AirStack robot container — mocap_bridge.py
      │  (PX4 topic:  /drone_1/fmu/in/vehicle_visual_odometry)
      ▼
Drone's flight controller (PX4 EKF2 — the autopilot's sensor-fusion estimator)
      →  stable indoor flight
```

Everything below the laptop row is unchanged CMU AirStack (their
[`experiment.md`](AirStack/robot/ros_ws/src/svg_ground_control/experiment.md) §B4b
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
[`patches/0003-libmotioncapture-natnet-4.2-modeldef-segfault.patch`](patches/0003-libmotioncapture-natnet-4.2-modeldef-segfault.patch)
(worth contributing upstream). `./mocap.sh setup` applies this patch automatically.

Finally, the open receiver publishes all bodies bundled into one topic (`/poses`),
while the AirStack pipeline expects one topic per drone (`/drone_1/pose`). A ~40-line
relay ([`mocap/pose_relay.py`](mocap/pose_relay.py)) converts between the two.
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
| — (not covered) | If Motive assets are added/renamed mid-session: restart the bridge (and never rename while `natnet_ros2` runs — it can crash on the next frame). |

`natnet_ros2` stays in the tree untouched — it is still the right tool on a rig
whose Motive genuinely multicasts, and its command channel remains a handy probe.

## 5 · Troubleshooting

| Symptom | Do this |
|---|---|
| `/drone_1/pose` missing or 0 Hz | Is `./mocap.sh` running on the laptop (`./mocap.sh status`)? Then `./mocap.sh check` and read its verdict. |
| `check` says "nothing on the wire" | Motive PC on? Streaming enabled in Motive's Data Streaming pane? Laptop cable in the mocap LAN, IP on `192.168.9.x` (`ip -4 -brief addr`)? Can you `ping` the Motive PC ([CONFIG.md](CONFIG.md) has the current IP)? Note: ping working does NOT prove pose data flows — that's exactly what `check` is for. |
| `check` shows packets but bridge publishes nothing | A leftover process may be eating the port: `ss -ulpn \| grep 1511`, then `./mocap.sh stop` and restart. Also confirm the body name in Motive matches `MOCAP_BODIES` (default `drone_1`) letter-for-letter. |
| Rate differs from CONFIG.md's value | Motive's capture rate was changed — fine, but update [CONFIG.md](CONFIG.md) so the next person expects the right number. |
| Bridge worked, then poses froze | Restart the bridge (`Ctrl+C`, rerun). If it recurs, run `check` while frozen: packets still arriving → software side; none → Motive/network side. |
| Renamed/added a rigid body in Motive | Restart the bridge — the body list is read once at startup. |
| Setup fails building | Make sure no conda env is active (the script strips miniconda automatically, but exotic Python setups can still interfere); needs ROS 2 Jazzy at `/opt/ros/jazzy`. |

## 6 · What exactly is where (technical appendix)

| Piece | Location | Role |
|---|---|---|
| `mocap.sh` | repo root | setup / run / check / stop / status |
| `mocap/motion_capture.yaml` | this repo | Motive PC IP + stream settings (edit here, commit) |
| `mocap/pose_relay.py` | this repo | `/poses` (NamedPoseArray) → per-body `/<name>/pose` (PoseStamped, frame `world`) |
| `mocap/fastdds.xml` | this repo | UDP-only DDS profile — same one the robot container uses, so laptop↔container topics interoperate (shared-memory off) |
| `mocap/probe.py` | this repo | the raw-UDP test behind `./mocap.sh check` |
| `patches/0003-…-modeldef-segfault.patch` | this repo | our NatNet 4.2 fix to libmotioncapture |
| built receiver | `~/mocap_ws` (created by `setup`; override with `MOCAP_WS=…`) | `motion_capture_tracking` @ commit `64d3af2` + patch, built against system ROS Jazzy |

Bridge environment (set automatically by `mocap.sh`): `ROS_DOMAIN_ID=1` (the
lab-wide domain, see CONFIG.md), discovery range SUBNET, Fast DDS profile as above.
The robot container runs with host networking, which is why a laptop-side publisher
is indistinguishable from an in-container one.

Data-format notes: `/drone_1/pose` is `geometry_msgs/PoseStamped` in frame
`world`, published reliable/volatile at Motive's rate; `/poses` (bundled, all
bodies) uses sensor-data QoS. Downstream, `svg_ground_control/mocap_bridge.py`
consumes `/{name}/pose` per its `swarm_real.yaml` `mocap_topic_template` — no
changes needed there.
