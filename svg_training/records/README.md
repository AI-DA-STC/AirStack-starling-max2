REFERENCE · how to read a run's record and the ledger: verdict words, T and W rows, and the masked values.

# Records and the ledger

**For** anyone checking a number. Every number on a reader page links to a record here. Records are evidence: they are
written by the tooling at the end of a run and never edited afterwards, even when a later page corrects how a result is
described. Every record is observed in the training simulator; none is a flight result.

## The ledger

[LEDGER.md](LEDGER.md) lists every run of this folder, one row each, oldest first. It is separate from the flight
ledger of the repository (`../../docs/record/LEDGER.md`, rows #1, #2, …).

| Column | Holds |
|---|---|
| # | the run's number: T1, T2, … T*n* is the *n*-th run of this folder |
| Date | the run's time stamp (+08:00, Singapore; T1's dates are UTC from the container) |
| Simulator | which simulator: the replica of NUS's game, tier 1 (our fast drone model) or tier 2 (Isaac Lab), and on which machine |
| Run | the run's name; the record file is `<run>_record.md` |
| What | the headline numbers, in one cell |
| Result | the verdict word (below) |
| Record | the path of the record |

**T and W rows.** A row written on the lab's second workstation, before its branch joins `main`, is numbered W1, W2, …;
at the merge it gets the next free T number. T15–T21 were W1–W7, and T22–T24 also ran on that workstation; the Phase 5 rows W11–W16 and the filter record
became T25–T32, and C0 (W17) T33 (the map is in the ledger's header). Records and code comments may still say the W number. T35–T38 are INFO records of the NUS port's Phase 1, Run 0, Phase 2a and
self-play matrix, written after the fact from their logs (T34 is unused; numbers are never reused).

## Verdict words

| Word | Means |
|---|---|
| **PASS** | every gate of the run was met. Gates are pass marks written before the run and never moved |
| **FAIL** | at least one gate was missed. A FAIL stays a FAIL in the ledger |
| **FAIL (accepted)** | a gate was missed; the lab owner read the cause, judged it harmless, and the work went on. Still a FAIL |
| **INFO** | the run had no gates: a measurement or a pilot. Its numbers describe; they do not pass or fail |
| **ABORTED** | the run was stopped before it finished (too long, a starved GPU, a wrong set-up). Its partial numbers prove nothing |
| **TOO_SLOW** | STE task L0.13 only (LEAD CALL 21 Nov 2026): the training stopped at its cap before its game-step budget; that is the result (too slow at that cap), and the gate is read at the steps reached for information only |
| PASS / FAIL on NUS's port | they grade our code and our copies against NUS's code, never NUS's code |

## What a record holds

Records follow [_template_record.md](_template_record.md). In order:

1. **One line naming the simulator**, and "not a flight result".
2. **A table of facts:** purpose (the question and the plan section), gates (the file and its sha256, written before
   the run), date and machine, code commit, local settings files (sha256 only), seeds, games.
3. **Results**: counts as `k/n [low, high]`, a Wilson 95 % interval in brackets.
4. **Verdict**, then videos, GPU hours, limits and the ledger row.

Paths under `runs/` in a record name the run's raw output. `runs/` is not in git: the record holds what we keep.

## "at the local value"

Until 18 November 2026 NUS's settings and the hangar's size were kept out of git, so the record writers replace any
number that equals a value in the git-ignored `configs/local/` files with the words "at the local value". Example: rung
1's G19 v ApfStrike row reads `175/1000 [0.153, at the local value]`; the hidden upper bound is 0.200. NUS has since
agreed that its settings may be published, so reader pages print the numbers; the records stay as written. To recompute
a masked bound, use the Wilson formula on `k/n` (`wilson` in `source/svg_training/core/metrics.py`).

## How to check a number

1. On the reader page, follow the number's link to its record, or find its T number in [LEDGER.md](LEDGER.md).
2. In the record, find the results table and the row for the pair or check.
3. Read the record's limits section before you reuse the number.

Ladder records say "rung" where the pages say "row": `..._nus_phase4_rung4_2_record.md` is row 4 (its first attempt,
`..._rung4_record.md`, is ABORTED).
