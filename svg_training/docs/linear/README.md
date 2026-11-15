# Linear files: Isaac Lab Pipeline for NUS Strategy Training

Linear is the source of truth for this project's issues and status (project P-NEAR-31, team NEAR Lab). These files
are the repo's record of what we asked Linear to change and what Linear reported back. The layout follows the
repository's own [docs/linear/](../../../docs/linear/README.md); the flight-stack projects (HTX-R1, R2, R3) live
there, this project lives here.

| Folder | What is in it | File name |
|---|---|---|
| [updates/](updates/) | Instructions handed to the Linear agent | `YYYY-MM-DD-linear-agent-<topic>.md` |
| [synced/](synced/) | The record the Linear agent writes back after applying an update | `YYYY-MM-DD-linear-sync-record.md` (`-2`, `-3` for later syncs that day). The 16 November instruction files asked for `…-linear-synced-<topic>.md`: those records were renamed to this pattern when saved |
| [snapshots/](snapshots/) | A full copy of the project, its milestones and issues on a date | `YYYY-MM-DD-project-plan-linear.md` |

How one update goes:

1. Write the instructions in `updates/`, asking for a record named `YYYY-MM-DD-linear-sync-record.md`.
2. The owner uploads the file to the Linear agent.
3. Save the record it returns in `synced/`.
4. If titles, milestones, statuses or assignees changed, write a new snapshot in `snapshots/`.

Files in `updates/` and `synced/` are dated history: keep their text as written; only fix a link that a move broke.

Latest snapshot: [snapshots/2026-11-16-project-plan-linear.md](snapshots/2026-11-16-project-plan-linear.md).
Owner's rules for this project: no cycles and no due dates on issues; every issue is assigned to the owner; target
dates only on completed milestones; issue comments never carry the partner's confidential game numbers.
