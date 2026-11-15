# Linear sync record — 2026-11-13, owner-decision closures

Workspace: nearlab. Project: HTX-R2 Starling Flight Bring-up (M2–M8).
Fresh verification after the closure update. No titles changed. No issues created. Nothing deleted. Verification added no duplicate comments or further issue mutations.

## Current titles and statuses

| Issue | Title | Status |
| --- | --- | --- |
| NEAR-831 | Change gains live from the panel in flight | Done |
| NEAR-833 | Check the yaw stick turns the drone the right way, slowly and low | Done |
| NEAR-834 | Gamepad fence test | Done |
| NEAR-835 | Release-to-hold test and coast distance | Done |

NEAR-831, NEAR-834 and NEAR-835 changed from In Progress to Done in this closure update. NEAR-833 was already Done and was left unchanged.

## Closure comments

All three comments below were added now by the closure update and freshly verified present exactly as requested. None was repeated during verification. Earlier flight-evidence comments remain unchanged.

### NEAR-834 — added now

2026-11-13. Closed by the owner on the result already recorded here: three approaches into the −y teleop wall at up to 0.66 m/s, at most 0.03 m past it. The +x wall and the top at 1.8 m were not flown. All walls run on the same code.

### NEAR-835 — added now

2026-11-13. Closed by the owner on the result already recorded here: from about 0.5 m/s the drone coasted 0.05 to 0.28 m and stopped within 0.9 to 1.6 s of release, then held within 0.15 m for 5 s. Unplugging the pad in flight was not flown.

### NEAR-831 — added now

2026-11-13. Closed by the owner on the result already recorded here: the CBF radius was changed from the panel in flight (0.55 → 0.90) and took effect. The other gains in the dropdown were not changed in flight.

## Milestone progress

Freshly retrieved displayed Linear progress; not simple completed-issue ratios.

| Milestone | Displayed progress |
| --- | --- |
| M4 · Goal flights with the braking fence | 38% |
| M5 · Gamepad flying on the real drone | 75% |

## Proposed, not created

No issues created for these findings. None is fixed by this sync. Owner decides.

1. The commander gives no warning when no pad is sending commands. It holds position as if the sticks were centred (first attempt, 16:34:59). Check before takeoff: `ros2 topic hz /svg/drone_2/teleop_command` must show about 20 Hz.
2. The drone overshoots the commanded speed: peak horizontal speed 0.66 m/s against the 0.5 m/s stick cap.
3. An issue for the hand-flown demonstration, "one drone hand-flown at a hovering drone, held off by the collision filter", if the owner wants it tracked (ledger row #37).
4. With the stick held, the collision filter keeps pushing the hovering drone toward the wall behind it (0.29 m left at the end, ledger row #37). Let go once it resists.
5. Teleop fence: the +x wall and the top at 1.8 m have not been flown.
6. Gamepad: unplugging the pad in flight has not been flown (by the code, the last stick command is held for up to 0.5 s, then zero is sent).
7. Live gains: only the CBF radius has been changed in flight.

## Not applied / exceptions

No requested closure status or comment remains unapplied. All three closure comments match the instruction text. Existing flight-evidence comments still contain the previously noted automatic unrelated pull request links for ledger references #36 and #37; these were not edited or duplicated. No new issues were created for proposed findings.

## Project totals

Freshly verified after closures. All non-trashed issues, including archived. No other statuses returned.

| Project | Total | Backlog | In Progress | Done | Canceled |
| --- | --- | --- | --- | --- | --- |
| HTX-R1 Swarm Sim Validation (Isaac) | 66 | 52 | 1 | 12 | 1 |
| HTX-R2 Starling Flight Bring-up (M2–M8) | 36 | 19 | 4 | 12 | 1 |
| HTX-R3 Multi-Drone Localisation (VO + UWB) | 17 | 16 | 0 | 1 | 0 |
