# CLAUDE.md — AirStack Starling Max 2 (indoor OptiTrack mocap flight stack)

AirStack ground-control workspace flying a ModalAI Starling Max 2 indoors under OptiTrack mocap (no GPS/VIO for nav).

**Read first:** [MILESTONES.md](MILESTONES.md) §3 (status table) / §3c (test ledger) — current state — then the table below.

| Doc | Use it for |
|---|---|
| [MILESTONES.md](MILESTONES.md) | current state: status table, test ledger, open issues |
| [RUNBOOK.md](RUNBOOK.md) | running a session |
| [CONFIG.md](CONFIG.md) | live values (IPs, params, credentials) |
| [MOCAP.md](MOCAP.md) | laptop-side mocap bridge |
| [DRONE_SETUP.md](DRONE_SETUP.md) | drone provisioning |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | symptom → fix index |
| [MILESTONES.md](MILESTONES.md) §8 | deferred designs (shelved commander fixes) |
| [PREFLIGHT.md](PREFLIGHT.md) | safety card |

Architecture pictures: `pictures/Starling_Airstack_architecture.png` (control flow),
`pictures/Flight_lab_architecture.png` (network topology). Network/router details live in
the companion repo [ground-control-network-setup](https://github.com/AI-DA-STC/ground-control-network-setup).

## Iron rules
1. RC takeover = flip to MANUAL or KILL only — Position/Altitude still obey the commander's setpoints.
2. Confirm **DISARMED in QGC** after every landing — the commander's log is optimistic.
3. Commander stuck non-IDLE after a takeover → call `land` once to reset it.
4. Never run `test/functional_*.py` with the real stack up — they publish fake odometry on live topics.
5. Software is BLIND to PX4 arming state (v1.14 px4_msgs mismatch) — fly with QGC visible.
6. Lab WiFi SSIDs (`motive`, `StarlingMax2`) are OPEN (no encryption) — never bridge the lab network to the internet.

**Two clones:** `~/AirStack-starling-max2` (live, docker-mounted) vs `~/Documents/GitHub/AirStack-starling-max2` (git mirror) — workflow currently INVERTED, check `git log` in both before editing. **Never push** — the user pushes via GitHub Desktop.

**Session history:** pre-2026-09 session-by-session narrative used to live in `CLAUDE_NOTES.md`
(retired 2026-09-08 — superseded by the docs above). Recover it with `git log --follow CLAUDE_NOTES.md`.
