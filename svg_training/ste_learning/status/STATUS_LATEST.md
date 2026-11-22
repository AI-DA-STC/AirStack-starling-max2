INTERNAL · the latest status of STE's own learning track and the NUS port, overwritten at every update; the history is in [LOG.md](LOG.md). Produced by the `train-status` skill.

**Status, 2026-11-22 16:43 (+08:00), event: gate G0 ruled, phase L1 open** · laptop RTX 5070 Ti · GPU idle · 0 jobs

**Plain summary.** You ruled gate G0 today. Phase L0 is closed, phase L1 (the drone model, plus a small 1.15 m side track)
is open with 13 GPU-hours for L1 and L2 together. Nothing has run on the GPU since this morning.

**Your rulings** ([DISCUSSION §14](../DISCUSSION_2026-11-19_20.md#14-gate-g0-rulings-owner-22-nov-2026)):
- the main game has a 1-for-1 tag (your old "no tag" rule is overturned);
- tag 1.6 m to build the pipeline and for the first demo (the hand-written 1v1); 1.15 m trained after L2, with a small
  1.15 m side track in L1;
- the fast simulator for quick experiments and checks, the main training in Isaac Lab;
- 13 GPU-h for L1 + L2; 120 s games (shorter clocks only as experiments); the AirStack-simulator logs approved;
- open arena first, then random blocks, then the construction site;
- train 3v3 (and 1v1), score every trained team at 2v1 and 5v3 too; a training-settings sweep added to the plan;
- a task still running at the Monday switch is handed over to the 5090, never cut short.

**What I did since** (each reviewed by two agents):
- recorded the rulings in the plan, the decision page, the game spec, the standards and the costed plan;
- the budget settings know phase L1 (13 GPU-h shared by the laptop and the 5090: hours are carried across at each
  switch with `ste_job.py carry`); L0 is closed to new runs; full test suite 2,048 passed;
- the trained players L1 needs are now in git (`ste_provisional/`), so the 5090 can load them;
- the side-track spec is written and fixed before any run ([L1_SIDE_TRACK_SPEC](../drafts/L1_SIDE_TRACK_SPEC.md)).

**Next (tonight, laptop, fast simulator):** build the driver additions (an implementer is on it now, then two code
reviewers), then three runs: the 1.6 m Guard team against every Strike script (minutes); a Strike team trained against
the second Guard script at 1.6 m (about 0.6 GPU-h); and two small 1.15 m Strike runs, one with a 30 s training clock and
one weighting a clock loss more (about 0.8 GPU-h together). I will message you when the first GPU run starts.

**Phases**

| Phase | Status | Simulator |
|---|---|---|
| L0 Game definition and feasibility | **done; G0 ruled 22 Nov** (13.77 of 19 GPU-h) | fast engine, Isaac Lab |
| L1 Drone model (+ side track) | **open**: side-track build in progress | Isaac Lab, fast engine for checks |
| L2–L9 | intended | — |

**Waiting on you:** nothing for L1. Later: whether the NUS-facing pages that still say "the main game has no tag" may be
updated (svg_training README, GLOSSARY, RESEARCH, THE_GAME, DESIGN, docs/README, the contact-tag plan); I will show you
the wording first.

**Usage:** today about 45 agent runs since the morning digest (reviews, writers, two implementers), about 5 M tokens;
two full test suites (36 min each); 0 GPU-h. L1 + L2 used 0 of 13.

**Ready to push:** `development` is 1 commit ahead of GitHub in the mirror (the G0 rulings, f914423e) — plus this
status commit.
