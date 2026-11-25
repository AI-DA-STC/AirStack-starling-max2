#!/usr/bin/env python3
"""Launch a job detached, wait for it, list jobs (STE learning track, task L0.7). Linux only, standard library only.

    python scripts/ste_job.py launch --task L0.11 --name <job> --run-dir runs/<folder> --min-s <seconds> --gpu-h <hours> [--post-clips3d | --no-post-clips3d] -- <command ...>
    python scripts/ste_job.py wait <job>
    python scripts/ste_job.py status
    python scripts/ste_job.py carry --gpu-h <hours> --note "<machine> <date>"
    python scripts/ste_job.py owner-pauses
    python scripts/ste_job.py post-clips3d --run-dir runs/<folder>

launch   starts <command ...> detached (its own session; output appended to <run-dir>/job.log) behind a thin wrapper
         that records the command's own exit code in <run-dir>/exit_code, and records the job (pid, process start
         time, boot id, the exact command, start time, expected minimum duration) in <run-dir>/job.json and in the
         shared state.json. --min-s: the shortest effective duration a real finish can have. --gpu-h: GPU-hours asked
         for, the job's total over all its launches (0 for a CPU job); the launch is refused if the task's cap or the
         phase cap in configs/ste_learning.toml would be passed (hours this job has already logged in the same
         run folder are not asked for twice; a new run folder under an old name is a new run). Refused too while
         the job, or any job in that run folder, is alive, and while an owner pause (scripts/gpu_pause.sh pause) is
         open, even one that stopped no job: only the owner resumes it (a pause the lead made with
         GPU_PAUSE_BY=lead, of its own sibling jobs, does not block). Run the same line again after a job died (a
         reboot, a kill): the command resumes from its checkpoint. After a reboot use bash <run-dir>/cmd.txt: it
         sets or unsets PYTHONPATH, CUDA_VISIBLE_DEVICES, PYTORCH_CUDA_ALLOC_CONF, SVG_SHARED_DIR and
         SVG_PAUSE_LEGACY_LOGS as at the first launch. A relaunch with another shared folder than the run folder
         recorded is refused.
         The post-run 3-D clips (the logic: the ste package's post-run module) are ON by default when the command
         runs scripts/ste_exploit_l012.py as a run of record (not --pilot, --run0 or verdict); --post-clips3d turns
         them on for any other command, --no-post-clips3d off; the choice is kept in job.json and cmd.txt. When the
         command exits 0 and its run folder holds a complete results.json and agent_final.pt, the wrapper starts
         scripts/ste_l5_clips3d.py --run-dir <run-dir> as its own recorded job (clips3d_<job>, run folder <run-dir>/videos3d, the same task and
         settings, --gpu-h 0.1, --min-s 30), so its GPU-hours are logged against the run's task cap. It never waits:
         an open owner pause, a busy GPU (scripts/isaac_preflight.sh --approved-headless --allow-siblings) or the cap
         leave "pending" in <run-dir>/videos3d/HOOK_STATUS with the retry line; exit 0 without a finished run leaves
         "skipped"; a non-zero exit only a job.log line; any hook error is a job.log line. The
         job's own exit code and results are written first and never changed. --clips3d-for is set by the hook on the
         clips job itself (it then writes its end into that run's HOOK_STATUS); not for hand use.
wait     blocks until the job has ended, prints one line
             <task> <job> <VERDICT> exit=<code> duration=<s>s effective=<s>s
         and exits with the JOB'S exit code. Verdicts: DONE (0), REFUSED (2), CAP (3), INTERRUPTED (4), NONFINITE (5),
         CONTROL_FAILED (6: a control with a known answer failed; terminal, never retried),
         FAILED (any other code); ENDED_EARLY when the effective duration is under --min-s (own exit status 20 if the
         job's code was 0, else the job's code); a resumed trainer is judged on its whole run (run_effective, from
         the progress.json it saves with each checkpoint), not on its last launch; DIED when the job is gone and
         recorded no exit code (own status 21).
         An unknown job name: status 22, nothing on stdout. The waiter's own failure (state.json unreadable): 23.
status   one line per job: alive | alive (paused) | alive (wrapper gone) | dead | dead (previous boot), the exit code;
         clips3d=<running/pending/skipped/done/failed> for a run with a post-run clips marker; clips3d=missing for an
         exit-0 run with the hook on whose clips are not complete and whose clips job is not alive (a killed wrapper,
         a reboot): run the post-clips3d line.
         faults=<n> (in wait's line and in status) counts bookkeeping writes the wrapper had to retry (a full disk,
         any error): the job was not harmed by them; details in <run-dir>/job.json and job.log. A last line gives the
         budget section in work: used (this machine's ledger rows + carried hours) of its cap.
carry    one ledger per machine, one cap for both (the 13.0 of L1 + L2 is shared by the laptop and the RTX 5090):
         appends one marked row (group "carried:L1+L2") of GPU-hours the other machine used, which counts toward the
         cap of the budget section in work, never toward a task. --gpu-h: a finite number, 0 or more. --note: the
         machine and the date. Refused (status 2, nothing written) otherwise.

owner-pauses  lists the open pauses that are not the lead's own (not tagged GPU_PAUSE_BY=lead), one line each; exit
         0 if there is none, 2 if there is one. scripts/gpu_pause.sh runs it before a resume or stop tagged
         GPU_PAUSE_BY=lead and refuses while an owner pause is open (never end a pause the session did not make).

post-clips3d  the post-run 3-D clip hook again, by hand, for a finished run folder whose clips are pending or missing
         (the line HOOK_STATUS gives): the same checks (exit code 0, complete run, no owner pause, the preflight, the
         cap). Exit 0 if the clips job was launched, 2 otherwise (the reason is printed and, except while a clips job of
         the run is already running, written to HOOK_STATUS).

A job is told apart by pid, process start time and boot id, never by its name or command line. To stop a job with a
checkpoint, send SIGINT to the recorded pid (the wrapper passes it on) or use scripts/gpu_pause.sh stop. Logic and the
full description: source/svg_training/ste/jobs.py.
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

from svg_training.ste import budget, jobs  # noqa: E402
from svg_training.ste.config import SETTINGS_FILE, load_ste_learning  # noqa: E402
from svg_training.ste.run_contract import EXIT_DONE, EXIT_REFUSED  # noqa: E402

SEPARATOR = "--"


def parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True,
                                     metavar="{launch,wait,status,carry,owner-pauses,post-clips3d}")
    launch = commands.add_parser("launch", help="start a command detached and record the job")
    launch.add_argument("--task", required=True, help="task ID, as in configs/ste_learning.toml (L1.9)")
    launch.add_argument("--name", required=True, help="job name: letters, digits, . _ -")
    launch.add_argument("--run-dir", required=True, type=Path, help="the job's run folder")
    launch.add_argument("--min-s", required=True, type=float, help="expected minimum effective duration, seconds")
    launch.add_argument("--gpu-h", required=True, type=float, help="GPU-hours asked for; 0 for a CPU job")
    launch.add_argument("--settings", type=Path, default=SETTINGS_FILE, help="the track's settings file (caps)")
    launch.add_argument("--beat-s", type=float, default=jobs.BEAT_S, help="seconds between heartbeats")
    hook = launch.add_mutually_exclusive_group()
    hook.add_argument("--post-clips3d", dest="post_clips3d", action="store_const", const=True, default=None,
                      help="after a 0 exit and a complete run, start its 3-D clips as their own job (default: on when "
                           "the command runs scripts/ste_exploit_l012.py as a run of record)")
    hook.add_argument("--no-post-clips3d", dest="post_clips3d", action="store_const", const=False,
                      help="no post-run 3-D clips for this job")
    launch.add_argument("--clips3d-for", type=Path, default=None, help=argparse.SUPPRESS)   # set by the hook only
    launch.add_argument("cmd", nargs=argparse.REMAINDER, help="-- then the command and its arguments")
    wait = commands.add_parser("wait", help="block until a job has ended; exit with its exit code")
    wait.add_argument("name")
    wait.add_argument("--poll-s", type=float, default=jobs.POLL_S, help="seconds between looks")
    status = commands.add_parser("status", help="list the jobs and the budget in work")
    status.add_argument("--settings", type=Path, default=SETTINGS_FILE, help="the track's settings file (caps)")
    carry = commands.add_parser("carry", help="add GPU-hours another machine used to the budget in work")
    carry.add_argument("--gpu-h", required=True, type=float, help="GPU-hours the other machine used SINCE ITS LAST CARRY (an increment of its own ledger rows only, never a running total; the ledger is append-only)")
    carry.add_argument("--note", required=True, help="the machine and the date, as \"rtx5090 2026-11-24\"")
    carry.add_argument("--settings", type=Path, default=SETTINGS_FILE, help="the track's settings file (caps)")
    commands.add_parser("owner-pauses", help="list the open owner pauses; exit 2 if there is one")
    clips = commands.add_parser("post-clips3d", help="start a finished run's pending 3-D clips (the post-run hook)")
    clips.add_argument("--run-dir", required=True, type=Path, help="the finished training run folder")
    wrapper = commands.add_parser(jobs.WRAPPER_COMMAND)             # the wrapper: started by launch, not by hand
    wrapper.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)                                  # a bad argument exits 2, which is EXIT_REFUSED
    if args.command == "wait" and not args.poll_s > 0:
        parser.error("--poll-s must be above 0")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse(argv)
    try:
        return run(args)
    except Exception:           # the tool's own failure must not leave with a status a job could have returned (1)
        traceback.print_exc()
        return jobs.EXIT_TOOL_ERROR


def run(args: argparse.Namespace) -> int:
    if args.command == jobs.WRAPPER_COMMAND:
        return jobs.run_wrapper(args.run_dir)
    if args.command == "launch":
        cmd = args.cmd[1:] if args.cmd[:1] == [SEPARATOR] else args.cmd
        try:
            job = jobs.launch(args.task, args.name, args.run_dir, cmd, args.min_s, args.gpu_h, settings=args.settings,
                              beat_s=args.beat_s, post_clips3d=args.post_clips3d, clips3d_for=args.clips3d_for)
        except jobs.LaunchRefused as err:
            print(f"refused: {err}", file=sys.stderr)
            return EXIT_REFUSED
        print(f"launched {args.task} {args.name} pid={job['pid']} launch={job['launch']} log={job['log']}")
        return EXIT_DONE
    if args.command == "wait":
        try:
            outcome = jobs.wait(args.name, poll_s=args.poll_s)
        except jobs.NoSuchJob:
            print(f"no job named {args.name!r} in state.json (scripts/ste_job.py status lists them)", file=sys.stderr)
            return jobs.EXIT_NO_SUCH_JOB
        print(outcome.line, flush=True)
        return outcome.status
    if args.command == "post-clips3d":
        from svg_training.ste import post_run
        return post_run.retry(args.run_dir)
    if args.command == "owner-pauses":
        lines = jobs.owner_pause_lines()
        print("\n".join(lines or ["no owner pause is open"]))
        return EXIT_REFUSED if lines else EXIT_DONE
    if args.command == "carry":
        in_work = load_ste_learning(args.settings)[0].budget_in_work()
        try:
            row = budget.log_carried(in_work, args.gpu_h, args.note)
        except budget.BudgetError as err:
            print(f"refused: {err}", file=sys.stderr)
            return EXIT_REFUSED
        print(f"carried {row['carried_gpu_h']!r} GPU-h to [{in_work.section}] ({row['note']}); "
              f"{budget.budget_summary(args.settings)}")
        return EXIT_DONE
    print("\n".join([*jobs.status_lines(), f"budget {budget.budget_summary(args.settings)}"]))
    return EXIT_DONE


if __name__ == "__main__":
    raise SystemExit(main())
