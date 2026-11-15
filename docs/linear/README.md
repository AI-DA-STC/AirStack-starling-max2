# Linear files

Linear is the source of truth for issues and status. These files are the repo's record of what we asked Linear to change and what Linear reported back.

| Folder | What is in it | File name |
|---|---|---|
| [updates/](updates/) | Instructions handed to the Linear agent, and change lists | `YYYY-MM-DD-linear-agent-<topic>.md`, `YYYY-MM-DD-linear-change-list.md` |
| [synced/](synced/) | The record the Linear agent writes back after applying an update | `YYYY-MM-DD-linear-sync-record.md` (`-2`, `-3` for later syncs that day) |
| [snapshots/](snapshots/) | A full copy of the three projects, milestones and issue titles on a date | `YYYY-MM-DD-project-plan-linear.md` |

How one update goes:

1. Write the instructions in `updates/`.
2. The owner uploads the file to the Linear agent.
3. Save the record it returns in `synced/`.
4. If titles, milestones or statuses changed, write a new snapshot in `snapshots/`.

The docs checker reads the snapshot named in `PLAN_FILE` in [tools/docs_check/check_docs.py](../../tools/docs_check/check_docs.py), currently [snapshots/2026-11-13-project-plan-linear.md](snapshots/2026-11-13-project-plan-linear.md). A newer snapshot is only used once `PLAN_FILE` points to it.

The Isaac Lab training project keeps its own Linear files in [svg_training/docs/linear/](../../svg_training/docs/linear/).
