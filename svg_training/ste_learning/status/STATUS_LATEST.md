INTERNAL · the latest status of STE's own learning track and the NUS port, overwritten at every update by the `train-status` skill · [../README.md](../README.md); the history: [LOG.md](LOG.md)

**Status, 2026-11-23 13:45 (+08:00) (home RTX 5090; documentation clean-up, no GPU work)**

**Main track:** phase L1, making the training drone realistic: nothing ran today; L1.7 (speed re-measure), L1.9 and L1.10 stay queued until the owner says what runs first. **Side track:** none. **Documentation (L9):** the clean-up the owner asked for is done on `docs-cleanup` and merged to `development`.

## Watch

![The story in one picture: from NUS's code to STE's own game](../../docs/figures/overview_story.png)

The story figure that opens the front page. Every page now starts with one line saying what it is for and where to go next.

## Plain summary

What was done: every page under `svg_training/` was given a first line with its label and its next step; the three story pages (overview, front page, learning-track page) were rewritten for any reader; the page map became a directory grouped by what a reader wants to do; 16 superseded pages were moved into `archive/` folders with indexes. What happened: 171 pages reachable, 0 orphans, 0 broken links; docs check 13 PASS · 0 FAIL; document tests 228 passed. Why it matters: a reader starting at the repository's README reaches the results in one click and is never left on a page that does not say where to go.

## Phases

| Phase | What | Math library | Simulator | Where it stands |
|---|---|---|---|---|
| NUS port, Phases 0–5 | NUS's code and policies under STE's drone conditions | JAX (NUS's code), PyTorch (STE's copy) | fast engine; Isaac Lab | done to 20 Nov 2026; route paused after stage 5.1 FAIL |
| L0 Pipeline check | the game with a tag, hand-written tactics, first trained teams | PyTorch | fast engine; Isaac Lab | done; gate G0 ruled 22 Nov 2026 |
| L1 Drone model | estimate-error model, drag, fit to flight logs | PyTorch | fast engine; Isaac Lab; AirStack simulator (logs) | in work; 3.54 of 13 GPU-h (L1 + L2) used, all carried from the laptop |
| L2 Game at 1.15 m | the main training set-up | PyTorch | Isaac Lab | approved with L1; not started |
| L3–L9 | training, scoring, flight hand-over, documentation | — | — | open at their own gates; L9 runs alongside |

## Phase L1, task by task

| Task | Where it stands |
|---|---|
| L1.0 5090 checks | done 23 Nov ~02:45 (record in `records/`) |
| L1.1b estimate-error model | built on the laptop 23 Nov; off by default |
| L1.7 Same effects in tier 1 (speed re-measure) | queued; **not started** (owner, 23 Nov: documentation only today) |
| L1.9 1v1 read, L1.10 tag-draw read | queued behind L1.7; spec in `drafts/L1_9_10_SPEC.md` |

## Other workstreams

| Work | Where it stands |
|---|---|
| Documentation clean-up (owner, 23 Nov) | done: 17 commits on `docs-cleanup`, merged to `development`; `main` fast-forwarded (docs-only pushes move both, owner's default 4) |
| Reviews of the clean-up | newcomer walk ran and its fixes are in; **numbers review and flow review owed** (reviewer agents stopped on the 5-hour usage limit, resets 14:10) |
| Training agent | stopped before any launch; 0 GPU-h; nothing committed |

**Next:** when the owner says so, the two owed reviews (cheap: two read-only agents), then L1.7 or whichever task the owner names first.

**Waiting on you:** (1) which L1 task runs first (L1.7 speed re-measure as planned, or L1.9's CPU screen); (2) the push.

**Usage:** this update: three agents for the clean-up (archive ~160k tokens, heads ~230k, training prep ~90k, stopped) plus one newcomer reviewer (~110k); two reviewers lost to the usage limit; tests 2 min 52 s on CPU; 0 GPU-h. Which check ran: the short document check (docs-only merge), not the full suite.

**Ready to push:** `development` and `main` (same commit).
