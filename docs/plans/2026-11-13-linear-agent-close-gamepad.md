# Linear update — 2026-11-13, close three issues on the owner's decision

Instructions for the Linear agent, in the **nearlab** workspace, project **HTX-R2 Starling Flight Bring-up (M2–M8)**. Apply every step below. Delete nothing. Use the comments exactly as written. Change no title. Check Linear before each step: if a status or comment is already in place, do not repeat it. No issue is created.

This file follows `2026-11-13-linear-agent-gamepad.md`, which is already applied. The owner has reviewed the flights of 2026-11-13 and closes the three issues below on what was flown. Evidence is unchanged: ledger rows 36 and 37 in `docs/record/LEDGER.md` of https://github.com/AI-DA-STC/AirStack-starling-max2, and the laptop folder `~/flight_logs/2026-11-13/`.

## Part 1 · Set to Done, each with its comment

**NEAR-834 "Gamepad fence test"**

> 2026-11-13. Closed by the owner on the result already recorded here: three approaches into the −y teleop wall at up to 0.66 m/s, at most 0.03 m past it. The +x wall and the top at 1.8 m were not flown. All walls run on the same code.

**NEAR-835 "Release-to-hold test and coast distance"**

> 2026-11-13. Closed by the owner on the result already recorded here: from about 0.5 m/s the drone coasted 0.05 to 0.28 m and stopped within 0.9 to 1.6 s of release, then held within 0.15 m for 5 s. Unplugging the pad in flight was not flown.

**NEAR-831 "Change gains live from the panel in flight"**

> 2026-11-13. Closed by the owner on the result already recorded here: the CBF radius was changed from the panel in flight (0.55 → 0.90) and took effect. The other gains in the dropdown were not changed in flight.

## Part 2 · Findings for the owner to turn into issues

Do NOT create issues for these. List them in the sync record under "proposed, not created", one line each, after the four already listed on 2026-11-13.

5. Teleop fence: the +x wall and the top at 1.8 m have not been flown.
6. Gamepad: unplugging the pad in flight has not been flown (by the code, the last stick command is held for up to 0.5 s, then zero is sent).
7. Live gains: only the CBF radius has been changed in flight.

## Part 3 · Write the sync record

Write a Markdown file named `2026-11-13-linear-synced-2.md`. State only what Linear now holds:

- the title and status of NEAR-831, NEAR-833, NEAR-834 and NEAR-835;
- each comment added here, and whether it was added now or already present;
- the progress of milestones M4 and M5;
- the list from Part 2, marked "proposed, not created";
- anything not applied, and why;
- the totals per project for **all three** projects (HTX-R1, HTX-R2 and HTX-R3): total, Backlog, In Progress, Done, Canceled.
