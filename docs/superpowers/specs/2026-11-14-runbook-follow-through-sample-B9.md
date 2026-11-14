### B9 — Fly one real drone with the gamepad

> **WORLD: REAL DRONE.** One Starling (`drone_2`), hand-flown with a Logitech F310 pad, motion-capture positioning (mocap). No Isaac Sim. [PREFLIGHT.md](PREFLIGHT.md) gates the takeoff.
> **Panic:** `hold` (pane 4, or the panel's Hold All), then `land`. Anything scary: KILL (ch8), then `land` once with the drone on the floor. `hold` on a hand-flown drone is not flown (NEAR-832).
> Until DISARMED, press Ctrl-C in pane 4 only.

**`drone_1` instead:** step 3 runs `tools/real.sh teleop drone_1`; paste the lines it prints, ping `10.40.2.11`, read `drone_1` for `drone_2` in every check.
It flies with a watcher on its front-right motor at every takeoff ([hazard 6](projects/HTX-R2.md#before-the-next-real-flight)).

Drone powered and booted. Laptop or its IP changed since the last session: re-provision ([DRONE_SETUP.md](DRONE_SETUP.md) §4).
Then REBOOT the drone, never `systemctl restart voxl-px4` (iron rule 7).

**1 · Laptop · no sim, mocap ports clear, the drone answers**
```bash
docker ps | grep isaac
ss -ulpn | grep -E ':(1510|1511)' || echo "ports clear"
ping -c2 10.40.2.10
```
Must see: nothing from `docker ps`, then `ports clear`, then ping replies.
If not: ports → `./mocap.sh stop`, re-check. No reply → IPs drift: [CONFIG.md](CONFIG.md) table.

**2 · Laptop · robot container up**
```bash
cd ~/AirStack-starling-max2/AirStack
./airstack.sh up robot-desktop
```
**3 · Laptop · pad check, then the config.** Pad plugged in, back switch on **X**, MODE light **off**. Move each stick when asked.
```bash
cd ~/AirStack-starling-max2 && tools/real.sh teleop drone_2
```
Must see: `PAD CHECK: PASS — do not press MODE from now on`, then the takeoff point and the pane lines. Never press MODE after this.

**4 · Laptop, new terminal · QGroundControl**
```bash
~/QGroundControl-x86_64.AppImage
```
Must see: `drone_2` in QGroundControl. Keep it visible. If not: the GCS IP on the drone (`voxl-mavlink-server.conf`, [CONFIG.md](CONFIG.md)) must be this laptop.

**5 · Laptop, new terminal · mocap.** Rigid body `drone_2` must exist in Motive before this starts ([MOCAP.md](MOCAP.md)).
```bash
cd ~/AirStack-starling-max2 && MOCAP_BODIES="drone_2" ./mocap.sh
```
Leave running.

**6 · Laptop · into the container**
```bash
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh connect robot
```
Must see: tmux "bringup", prompt `root@…#`.

**7 · Pane 1 · the drone link**
```bash
MicroXRCEAgent udp4 -p 8888 -v4
```
Must see: `session established`. Leave running.
If not: a stale laptop IP on the drone means no session. Re-provision it ([DRONE_SETUP.md](DRONE_SETUP.md) §4), then reboot.

**8 · Pane 4 · link alive**
```bash
ros2 topic hz /drone_2/fmu/out/vehicle_status
```
Must see: a steady rate. Ctrl-C after the reading. If not: is pane 1 running? ([TROUBLESHOOTING.md](TROUBLESHOOTING.md), "`/fmu/*` topics look dead")

**9 · Pane 4 · pose alive**
```bash
ros2 topic hz /drone_2/pose
```
Must see: a steady rate, about 240 Hz. Ctrl-C after the reading. If not: `./mocap.sh check` on the laptop names the culprit.

**10 · Pane 2 · interfaces**
```bash
ros2 launch svg_ground_control real_interfaces.launch.py drones:=drone_2 target_systems:=2
```
Must see: the startup line says `target_system=2`. Leave running. If not: do not fly (iron rule 5).

**11 · Pane 5 · the pad, before the commander**
```bash
ros2 launch svg_ground_control teleop.launch.py config:=/tmp/svg_real/teleop_real_drone_2.yaml
```
Must see: a `pad:` line once a second; move each stick, the numbers must follow. No `REFUSING TO COMMAND`. Leave it running until DISARMED.
If not: [TROUBLESHOOTING.md](TROUBLESHOOTING.md), "Gamepad sticks do nothing" and "`safe_teleop` prints `pad: NO /joy` forever".

**12 · Pane 3 · the commander**
```bash
ros2 launch svg_ground_control ground_control.launch.py config:=/tmp/svg_real/teleop_real_drone_2.yaml use_mocap:=true use_foxglove_studio:=true
```
Must see: Foxglove Studio opens, already pointed at the bridge. Leave running.

**13 · Pane 4 · odometry flowing**
```bash
ros2 topic hz /drone_2/odometry_conversion/odometry
```
Must see: a steady rate. Ctrl-C after the reading. If not: takeoff will be refused. [TROUBLESHOOTING.md](TROUBLESHOOTING.md), "Takeoff refused".

**14 · Pane 4 · commander status**
```bash
ros2 topic echo /svg/commander_status --once
```
Must see: `drone_2`, `"state": "IDLE"`, `"odom_fresh": true`. If not IDLE: `land` once, drone on the floor ([TROUBLESHOOTING.md](TROUBLESHOOTING.md), "Takeoff refused").

**15 · Pane 4 · pad alive**
```bash
ros2 topic hz /svg/drone_2/teleop_command
```
Must see: about 20 Hz. Ctrl-C after the reading. If not: the pad pane stopped ([TROUBLESHOOTING.md](TROUBLESHOOTING.md), "Sticks ignored after `start`").

**16 · Floor · go / no-go**
Every box on [PREFLIGHT.md](PREFLIGHT.md).
This session adds: `drone_2` stands ON the takeoff point step 3 printed (x -0.5, y 0.0 in `teleop_real_ours.yaml`), nose toward +x.

**What to expect**

| When | You see |
|---|---|
| `takeoff` | A STRAIGHT LINE from where the drone stands to the takeoff point (z 0.5): standing on the point, a climb. The fence does not act during the climb or the landing |
| Hover | The drone hovers on the point. The Basestation's Teleop · Sticks card: `STICKS PARKED` (press Start) |
| `start` | Pane 3: `drone_2: sticks live, holding [...] until moved`. The card reads `STICKS LIVE → drone_2` |
| Flight | The teleop fence (x and y −1.5 to 1.5 m, z 0.3 to 1.8 m) is meant to brake the drone at its walls. The −y wall was seen in one flight. The +x wall and the top are not flown |
| Speed | The cap is 0.5 m/s. It caps the command, not the drone |

**Stop table.** The [PREFLIGHT.md](PREFLIGHT.md) emergency table comes first.

| What you see | Do this | Record |
|---|---|---|
| Doubt, or the drone drifts with the sticks released | `hold` (pane 4 or the panel's Hold All), then `land`. After `hold` the sticks stay dead until `start` | not flown (`hold`: NEAR-832) |
| You need it down | `land` (pane 4, or the panel's Safety Stop, two clicks) | iron rule 2 |
| A motor of `drone_1` does not spin with the others at takeoff (`drone_1` variant) | KILL, then `land` once | hazard 6, [#34](record/LEDGER.md) |
| Sticks do nothing after `start` | pane 4: `ros2 topic hz /svg/drone_2/teleop_command`. Silent = the pad pane stopped, and no warning appears: `land`. Card says `press Start`: call `start` | [#36](record/LEDGER.md) |
| Pad unplugged in flight | do not replug it in flight. `land`. The code holds the drone where it is (a stale pad = zero command) | not flown |
| Near the top or the +x wall of the teleop fence | let go of the sticks. Still moving: `hold`, then `land` | not flown |
| Anything scary | KILL (ch8), then `land` once with the drone on the floor | iron rule 3 |
| Landed, but QGroundControl still says ARMED | after about 10 s: KILL or arm switch (ch5) down. Nobody walks in | iron rule 2 |

**17 · Pane 4 · takeoff.** Everyone stays outside the net from takeoff until QGroundControl says DISARMED.
```bash
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger
```
Must see, pane 3: `holding takeoff position`. Only then `start`. If not: [TROUBLESHOOTING.md](TROUBLESHOOTING.md), "Takeoff refused".

**18 · Pane 4 · start**
```bash
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger
```
Must see, pane 3: `drone_2: sticks live`. Wait for it before touching the sticks. If not: stop table, "Sticks do nothing after `start`".

**19 · Pad · fly.** First turn: slow and low, thumb on KILL.

| Control | What it does |
|---|---|
| Right stick | moves the drone in ROOM axes, not relative to its nose: up = +x, left = +y |
| Left stick | up and down = climb and descend · left and right = turn |
| LB | press once to lock climb and turn, press again to unlock. The right stick still works. Pane 5 shows `LOCKED` |
| Sticks released | the drone holds where it is |

**20 · Pane 4 · land**
```bash
ros2 service call /swarm_commander/land std_srvs/srv/Trigger
```
Must see: QGroundControl shows DISARMED before anyone walks in. If not: still ARMED after about 10 s → KILL or arm switch (ch5) down (iron rule 2).

**Shutdown.** Only after QGroundControl says DISARMED: Ctrl-C panes 3, 5, 2, 1 and the mocap terminal.

**21 · Laptop, drone on USB-C · stack down, drone off**
```bash
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh down
adb shell shutdown now
```
Then wait about 10 s, and unplug USB and the battery.
