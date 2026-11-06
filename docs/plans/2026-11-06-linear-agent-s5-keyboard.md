# Linear update — 2026-11-06, S5 says keyboard, not gamepad

Instructions for the Linear agent, in the **nearlab** workspace. Apply every step below. Delete nothing. Change only the words named here. All of this is simulation (Isaac Sim). The real drone is untouched.

## Part 1 · Milestone "S5 Finish basic sim flight checks" (project HTX-R1 Swarm Sim Validation (Isaac))

The owner decided on 2026-11-05 that S5's hand-flying is by keyboard. It has never been by gamepad.

In the milestone's description, make exactly these two replacements:

1. Replace "get one-drone gamepad flying working in the construction site" with "get one-drone keyboard flying working in the construction site".
2. In the "Done when" list, replace "drone_1 is hand-flown by gamepad in the construction site with cuVSLAM running, and the flight is scored." with "drone_1 is hand-flown by keyboard in the construction site with cuVSLAM running, and the flight is scored."

Leave every other word of the description as it is. If either phrase is not found exactly, change nothing for that phrase, and quote the description as it stands in the sync record.

Do not change the milestone HTX-R2 "M5 · Gamepad flying on the real drone" or any of its issues. Do not change any issue's status.

## Part 2 · Write the sync record

Write a Markdown file named `2026-11-06-linear-synced.md`. State only what Linear now holds:

- the full S5 milestone description, including "Done when", exactly as it now reads;
- which of the two replacements were applied, and anything not applied, and why;
- the S5 progress;
- the totals per project for **all three** projects (HTX-R1, HTX-R2 and HTX-R3): total, Backlog, In Progress, Done, Canceled.
