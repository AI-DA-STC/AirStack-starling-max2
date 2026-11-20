#!/usr/bin/env python3
"""Launch a job detached, wait for it, list jobs (STE learning track, task L0.7). Linux only, standard library only.

    python scripts/ste_job.py launch --task L0.11 --name <job> --run-dir runs/<folder> --min-s <seconds> --gpu-h <hours> -- <command ...>
    python scripts/ste_job.py wait <job>
    python scripts/ste_job.py status
    python scripts/ste_job.py owner-pauses

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
wait     blocks until the job has ended, prints one line
             <task> <job> <VERDICT> exit=<code> duration=<s>s effective=<s>s
         and exits with the JOB'S exit code. Verdicts: DONE (0), REFUSED (2), CAP (3), INTERRUPTED (4), NONFINITE (5),
         CONTROL_FAILED (6: a control with a known answer failed; terminal, never retried),
         FAILED (any other code); ENDED_EARLY when the effective duration is under --min-s (own exit status 20 if the
         job's code was 0, else the job's code); a resumed trainer is judged on its whole run (run_effective, from
         the progress.json it saves with each checkpoint), not on its last launch; DIED when the job is gone and
         recorded no exit code (own status 21).
         An unknown job name: status 22, nothing on stdout. The waiter's own failure (state.json unreadable): 23.
status   one line per job: alive | alive (paused) | alive (wrapper gone) | dead | dead (previous boot), the exit code.
         faults=<n> (in wait's line and in status) counts bookkeeping writes the wrapper had to retry (a full disk,
         any error): the job was not harmed by them; details in <run-dir>/job.json and job.log.

owner-pauses  lists the open pauses that are not the lead's own (not tagged GPU_PAUSE_BY=lead), one line each; exit
         0 if there is none, 2 if there is one. scripts/gpu_pause.sh runs it before a resume or stop tagged
         GPU_PAUSE_BY=lead and refuses while an owner pause is open (never end a pause the session did not make).

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

from svg_training.ste import jobs  # noqa: E402
from svg_training.ste.config import SETTINGS_FILE  # noqa: E402
from svg_training.ste.run_contract import EXIT_DONE, EXIT_REFUSED  # noqa: E402

SEPARATOR = "--"


def parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True, metavar="{launch,wait,status,owner-pauses}")
    launch = commands.add_parser("launch", help="start a command detached and record the job")
    launch.add_argument("--task", required=True, help="task ID, as in configs/ste_learning.toml (L0.11)")
    launch.add_argument("--name", required=True, help="job name: letters, digits, . _ -")
    launch.add_argument("--run-dir", required=True, type=Path, help="the job's run folder")
    launch.add_argument("--min-s", required=True, type=float, help="expected minimum effective duration, seconds")
    launch.add_argument("--gpu-h", required=True, type=float, help="GPU-hours asked for; 0 for a CPU job")
    launch.add_argument("--settings", type=Path, default=SETTINGS_FILE, help="the track's settings file (caps)")
    launch.add_argument("--beat-s", type=float, default=jobs.BEAT_S, help="seconds between heartbeats")
    launch.add_argument("cmd", nargs=argparse.REMAINDER, help="-- then the command and its arguments")
    wait = commands.add_parser("wait", help="block until a job has ended; exit with its exit code")
    wait.add_argument("name")
    wait.add_argument("--poll-s", type=float, default=jobs.POLL_S, help="seconds between looks")
    commands.add_parser("status", help="list the jobs")
    commands.add_parser("owner-pauses", help="list the open owner pauses; exit 2 if there is one")
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
                              beat_s=args.beat_s)
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
    if args.command == "owner-pauses":
        lines = jobs.owner_pause_lines()
        print("\n".join(lines or ["no owner pause is open"]))
        return EXIT_REFUSED if lines else EXIT_DONE
    print("\n".join(jobs.status_lines()))
    return EXIT_DONE


if __name__ == "__main__":
    raise SystemExit(main())
