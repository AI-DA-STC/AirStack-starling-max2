# CLAUDE.md — AirStack Starling Max 2 (indoor OptiTrack mocap flight stack)

AirStack ground-control workspace flying a ModalAI Starling Max 2 indoors under OptiTrack mocap (no GPS/VIO for nav).

**Read first:** [CLAUDE_NOTES.md](CLAUDE_NOTES.md) §0, then [MILESTONES.md](MILESTONES.md) §3/§3c.

| Doc | Use it for |
|---|---|
| [RUNBOOK.md](RUNBOOK.md) | running a session |
| [CONFIG.md](CONFIG.md) | live values (IPs, params, credentials) |
| [MOCAP.md](MOCAP.md) | laptop-side mocap bridge |
| [MOTIVE.md](MOTIVE.md) | Motive PC setup |
| [DRONE_SETUP.md](DRONE_SETUP.md) | drone provisioning |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | symptom → fix index |
| [BACKLOG.md](BACKLOG.md) | deferred designs |
| [PREFLIGHT.md](PREFLIGHT.md) | safety card |

## Iron rules
1. RC takeover = flip to MANUAL or KILL only — Position/Altitude still obey the commander's setpoints.
2. Confirm **DISARMED in QGC** after every landing — the commander's log is optimistic.
3. Commander stuck non-IDLE after a takeover → call `land` once to reset it.
4. Never run `test/functional_*.py` with the real stack up — they publish fake odometry on live topics.
5. Software is BLIND to PX4 arming state (v1.14 px4_msgs mismatch) — fly with QGC visible.

**Two clones:** `~/AirStack-starling-max2` (live, docker-mounted) vs `~/Documents/GitHub/AirStack-starling-max2` (git mirror) — workflow currently INVERTED, check `git log` in both before editing. **Never push** — the user pushes via GitHub Desktop.
