# Linear update — 2026-11-03, sim keyboard teleop in Drive mode

Instructions for the Linear agent, in the **nearlab** workspace. Apply every step below. Delete nothing. Use the titles exactly as written, including any curly apostrophe ’. The new issue is **Backlog**, unassigned, with no due date. All of this is simulation (Isaac Sim). The real drone is untouched and nothing here flew.

Evidence lives in the repo https://github.com/AI-DA-STC/AirStack-starling-max2: `docs/superpowers/specs/2026-11-03-sim-teleop-body-frame-design.md` and `docs/record/CHANGES.md`.

## Part 1 · HTX-R1 Swarm Sim Validation (Isaac)

Create this issue in milestone "S5 Finish basic sim flight checks":

**Title:** Sim keyboard teleop flies in Drive mode (BODY), F switches to Room mode, with the forward-follows-the-nose test

**Description:**

> Sim-only. The real drone and the gamepad path are untouched and stay room-fixed.
>
> Drive mode means the up arrow follows the drone's nose, whichever way it points. CMU's teleop is room-fixed (WORLD), and it stays that way on the real drone.
>
> How it is built: a small relay of ours sits between safe_teleop and the commander. It turns the keyboard's body-frame push into a room-frame command. A heading guard stops it if the heading is not known. The config is `teleop_single_ours.yaml`. Start it with `tools/sim.sh keys` or `tools/sim.sh relay`.
>
> Keys: Space is STOP. F switches between Drive mode (BODY) and Room mode (WORLD).
>
> Done when (target): the owner watches a video session with `teleop_single_ours.yaml` where the up arrow still follows the nose after a 180° turn, and F flips to Room mode. Plus one PASS of `tools/sim.sh test teleop_frame`, with these gates:
> - each push goes within 20° of the nose
> - the drone moves at least 0.15 m
> - it parks within 0.30 m
> - the heading is reached within 10°
> - one Room-mode push goes within 20° of +X

Status: Backlog. Add a relation: the new issue **relates to NEAR-789** (keyboard teleop).

## Part 2 · Comment on NEAR-874 "Write the velocity contract with NUS and CMU (frame, units, limits, rate, timeout)"

Add this comment. Leave the status unchanged.

> The NUS velocity contract stays room-frame (WORLD). The sim keyboard's Drive mode is a relay in tools/teleop only and does not touch that path.

## Part 3 · Write the sync record

Write a Markdown file named `2026-11-03-linear-synced.md`. State only what Linear now holds:

- the new issue's NEAR id, title, milestone and status;
- the relation to NEAR-789;
- the comment added on NEAR-874;
- anything not applied, and why;
- the totals per project for **all three** projects (HTX-R1, HTX-R2 and HTX-R3): total, Backlog, In Progress, Done, Canceled.
