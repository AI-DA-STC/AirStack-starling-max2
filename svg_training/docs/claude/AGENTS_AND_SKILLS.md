# Agents and skills for the training pipeline

Start Claude from the `svg_training` folder (`cd ~/AirStack-starling-max2/svg_training && claude`) so
these load. They are committed with the folder (owner, 14 November 2026); the clone ignores `.claude/`
by default, so a new agent or skill file needs `git add -f`.

## Skills (the standard process, in `.claude/skills/`)

| Skill | Use | What it enforces |
|---|---|---|
| `train-start` | Start of every session | Read CLAUDE.md, STANDARDS sections, HANDOFF §4–5; check working copy and GPU; intent stated before editing |
| `train-change` | Any edit in the folder | Paths inside the folder, test first, wording and labels, definition of done, HANDOFF updated, `git status` proof, no commit |
| `train-run` | Launch a benchmark or training run | GPU free, no AirStack simulator, `gates.toml` dated first, seeds, headless, ABORTED record, record and ledger row |
| `train-evaluate` | Score a checkpoint | Gates loaded and unchanged, fixed suite, 1,000 games or more, 95 % intervals, tier 2 cross-check, gatekeeper read |
| `train-debug` | Something is wrong | Evidence first, symptom table, one hypothesis at a time, never move a gate |
| `train-export` | Hand a policy to AirStack | Stages 3 and 4 passed, `interface.toml` complete, reload check, then stop at the folder boundary |

## Agents (in `.claude/agents/`)

| Agent | Expert in | Writes? | Use when |
|---|---|---|---|
| `train-isaaclab-engineer` | Isaac Lab 2.3.2 and 3.0, batched environments, cloning, `Multirotor`, throughput | No | Designing or reviewing tier 2 or any Isaac Lab call |
| `train-drone-dynamics` | Quadrotor dynamics, PX4 cascade, system identification, sim-to-real | No | Fitting or reviewing the tier 1 and tier 2 drone models |
| `train-marl-researcher` | Multi-agent RL for two-team games: pools, starts, rewards, evaluation | No | Designing or reviewing the training recipe or a result |
| `train-flight-interface-reviewer` | Policy interface, safety filter port, hand-over to AirStack | No | Before an interface change or an export |
| `train-gatekeeper` | STANDARDS §7, §8, §11; fail-closed record review | No | Before a run starts and after a record is written |
| `train-implementer` | Writing code inside `svg_training/`, test first | Yes, in the folder only | Building a plan the lead has agreed |

The five advisers are read-only. The implementer does not touch git.

## How the work is organised

The lead (the main Claude session) plans. It briefs the advisers in parallel, giving each the files
and not its own conclusion, and reconciles what they return into one decision. It shows the owner.
One implementer builds the agreed plan, test first. The gatekeeper reads the record. The lead
verifies the result against STANDARDS §11 before saying it is done. Agents never commit or push; the
lead handles git only on the owner's say-so.

## How a design question runs

1. The lead reads the question against `docs/DESIGN.md`, `STANDARDS.md` and `HANDOFF.md` §5.
2. The lead picks the two or three advisers whose field the question touches and briefs them in
   parallel, with file paths and the question, not a preferred answer.
3. The lead reconciles their answers: where they agree, where they differ, what nobody could verify.
4. The lead shows the owner a short summary in tables, with the options and a recommendation, before
   anything uncertain is executed.
5. After the owner decides, the lead changes the documents (`train-change`), records the decision in
   HANDOFF §4, and only then hands a plan to `train-implementer`.

## Rejected, do not re-propose

- Full physics only (approach A in `docs/DESIGN.md` §9).
- A response model only, without a cross-check on the rigid body (approach B).
- Moving the flight laptop to Isaac Lab 3.0 now. 3.0 is for the RTX 5090 machine, behind the adapter module.
- YAML configs (the repository hook treats them as behaviour changes).
- Fixed start positions (starts are random from the first run).
- Training without the safety filter in the loop.
- A tag radius, or a safety filter between the two teams (owner, 14 November 2026: a tag is contact).
- Google Photorealistic 3D Tiles or OneMap3D as training worlds (their terms do not allow it).
