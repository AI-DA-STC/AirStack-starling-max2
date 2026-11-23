INTERNAL · reference page of the STE learning track, from the specialist draft `archive/VALIDATION_QC_draft.md` (20 Nov 2026). **[PLAN.md](PLAN.md) takes precedence** where the two differ; its section 2 lists every change made at integration.

# Validation and QC plan: STE learning track

> **Integration notes (PLAN v2, 20 Nov).** (1) Stage 1 and the game-design check of stage 3 are now phase L0 (tasks
> L0.2, L0.3, L0.11, L0.12, L0.13), with the best-response test L0.12 as the degeneracy test; its band (Guard-trivial /
> Strike-trivial / worth learning, limit 0.2 PROPOSED) replaces the "more than half of the games" rule below. (2) **G-B is
> rewritten at G0**: under 1-for-1 tags, losing one Guard at 3v3 leaves 2v3, which head-count may decide; G-B's bar will
> be computed from references played at the reduced size, not as a fixed drop from G-A. (3) **L-2 "generations"**: in a
> league where both teams train at once there are no generations; L-2 becomes "no two consecutive league snapshots of
> the same team whose worst win rate against the pool is ≤ 0.5" (wording fixed with the L5 gates). (4) Sizes in the
> encoder tests follow the range ruled at G0 (P9), not 1–3.

**Basis.** [DISCUSSION_2026-11-19_20.md](DISCUSSION_2026-11-19_20.md) (D1–D9, P1–P8), STANDARDS §7, §8, §11, and Phase 5's
rigour ([plan](../docs/plans/2026-11-18-nus-phase5-retraining.md): R0, C0, N0, frozen verdict; T29, T30, T33, T43). Gates resting
on OPEN items are marked "if P*n*". The 1.6 m tag conflicts with STANDARDS §4's two FIXED tag rows, §5 rule 7 ("filter per team")
and `train-debug`'s per-team filter check; this draft overrides none of them (open questions).

## 0. Rules shared by every gate

1. Before the run, write `gates.toml`. Copy it verbatim into the run folder and give its sha256 in the record. It is never edited. A new limit means a new run.
2. Play at least 1,000 games per condition. Use one paired-starts file, pinned by sha256, and give Wilson 95 % intervals (`core/metrics.py`).
3. **Compute bars from references played under the same rules**, by code, from a pinned `scores.json`. T23, T24 and T41 were played without a tag and with the filter on every pair, so their numbers are not bars for the tag game.
4. **Run the controls first.** The positive control must PASS and the negative control must FAIL before any trained checkpoint is scored (the C0 and N0 pattern). A failed control stops the stage and leads to a new gate version.
5. The verdict order is fixed: FAIL, then INCONCLUSIVE, then PASS. Use INCONCLUSIVE only where the gate pre-registers it, together with its follow-up seeds. A FAIL is final.
6. Seeds are fixed in `gates.toml`, including follow-up seeds wherever INCONCLUSIVE is allowed. Use seeds spaced so that no stage seed collides (P5-12). A method claim needs 3 seeds and passes when at least 2 of 3 pass (the 5.2 rule).
7. Keep the gated set small. The rest of the robustness suite (§3) is INFO.
8. Name the simulator; write "observed in the training simulator".

## 1. Test pyramid

| Level | What it checks (oracle) | Where, cost | When |
|---|---|---|---|
| T-U unit and property | **Tag** fires only below the 3-D radius, 1-for-1; tagged drones descend as filter obstacles. **Option B**: Strike correction 0 on Guard–Strike pairs; same-team pairs and the B-off mode unchanged. **Delay, noise, drag**: k-tick delay shifts a step by k ticks; noise moments as stated; all zero = today's tier 2 bit for bit. **Encoder**: permutation and masked-slot invariance (≤ 1e-5); 1–3 drones. **Drone loss**: a removed drone neither scores nor tags. Zero-sum reward; loop lint; privacy scans. Oracles: PyTorch reference world (`models/rigid_body.py`), `cbf_filter.py` | CPU, seconds | every commit |
| T-I integration | Trainer smoke: both teams, 32 games, 2 updates. League pool selection is deterministic for a given seed. Save, resume, export and reload; videos appear under `runs/`; `score.py` refuses non-finite values | CPU, minutes | every commit |
| T-Ii Isaac-marked | `SVG_ISAAC_TESTS=1 pytest -m isaac` (conftest) | GPU, headless, after `isaac_preflight.sh` | nightly when the GPU is free; before merging any change to `models/`, `envs/`, `compat/` or the filter |
| T-X tier cross-checks | Tier 2 against the PyTorch world (T10 gates: closed-loop speed RMS ≤ 0.01 m/s, end position ≤ 20 mm). Paired scripted games, tier 1 against tier 2 (T13 gates: hold gap ≤ 0.10 per cell, closest approach ≤ 0.10 m). Step tests against flight logs (T11) | GPU, 1–3 h | per stage, and after any drone-model or filter change |
| T-S AirStack simulator | Real PX4 1.16.1 and EKF2 on Pegasus; a five-file test written to `docs/TEST_STANDARD.md`; owned by an AirStack session; recorded in the flight ledger | GPU, needs the owner (P5) | per stage gate (§2, rows 2a and 7) |
| T-R real flight | 1v1 under `docs/PREFLIGHT.md` | the owner | owner only |

A skip is not a pass.

## 2. Stage gates (written before each run)

| Stage | Gate (PROPOSED) | Controls | A FAIL triggers |
|---|---|---|---|
| **1. Measurement step 1** (if P3) | INFO, no pass mark. Tier-2 3v3 throughput, given with games, drones per game, tier and GPU, together with the training hours it implies. Zero-shot T41 policy on tier 2, 1,000 games on the Phase 4 paired starts (tier 1: 829/1,000, T41) | ParkedGuard against S20: the Strike team's reach count must lie inside T24's interval (524/1,000, [0.493, 0.555]). Outside it, stop and use `train-debug` | Estimated hours above the cap: owner (D3 cost). The zero-shot gap is a finding |
| **2a. Tier 2 + delay, noise and drag vs AirStack simulator** (if P5) | The FIXED S1 fit gates: held-out velocity RMS ≤ 0.10 m/s, t63 error ≤ 0.10 s, fitted delay 0–0.40 s, ≥ 8 held-out steps. Same airframe settings on both sides, so that only the estimator differs. The result describes the simulator, never the training set (§5 rule 10) | Negative (constructed): the fitted model with its delay offset by 0.2 s must fail t63. If it passes, the comparison cannot isolate the estimator: stop | First rule out the simulator's traps (the 1.9× clock, T3; the speed-only MAVROS route; PX4 1.16.1; the SIM-ONLY gains), then blame the delay model |
| **2b. Same model vs the real NEAR-962 flight** | Same FIXED gates. The T11 worst-leg speed RMS must stay ≤ 0.10 m/s. The parameter set of record is fitted here | Negative: today's tier 2 (no delay) should fail t63 (it misses by up to 0.38 s, T11) | Refit. A batched PyTorch EKF (D7 step 4) only after a failed refit; owner informed |
| **3. Filter option B and tag** (if P1, P2) | Regression: with option B off, the output on the CPU is bit-identical to today's training copy on T2's 2,000 scenes (as T31). T2's accepted FAIL against `cbf_filter.py` is restated, not re-gated. Option B: Strike correction = 0 on every feasible Guard–Strike pair; closed-loop closest approach ≥ 1.10 m minus measured lag. **Game design check** (zone radius is also 1.6 m: DISCUSSION P1 warning): score the references under the new rules; pin them as the bars file | References: parked Guard, untrained shared policy, scripted Guards, T41 zero-shot, random | Regression FAIL: no training. If the parked Guard holds the zone in more than half of the games against straight or flank Strike drones (PROPOSED), the tag radius makes the game trivial: owner (P1) |
| **4. Shared attention policy and drone loss** | Per seed: G-A, hold against each scripted Strike, with Wilson lower bound above the bars file's highest reference upper bound. G-B, with one Guard lost at a random time: **rewritten at gate G0 (integration note 2)**; version 1's wording, which gates nothing until then, was: hold lower bound above the parked-Guard bar, and a drop from G-A of at most 0.15. G-C: 0 non-finite values. 3 seeds, at least 2 must pass | Positive: the pipeline test (1v1 against `strike_straight`) must clear its bar within 1 GPU-h. Negative: an untrained shared policy must fail G-A and G-B | Fewer than 2 seeds pass: `train-debug`, then a new plan. No relaunch with moved bars |
| **5. League self-play** | Per seed, final Guard: L-1, hold against the **held-out** scripted Strike drones (§3) above the bars. L-2, no two consecutive failed same-team generations (as 5.1-b). L-3, an exploiter Strike team trained against the frozen Guard must reach the zone at least 0.10 less often than a second exploiter, trained with the same budget against the parked Guard (Wilson intervals separate). At least 2 of 3 seeds | Negative: an untrained Guard is exploited (L-3 fails). Optional INFO: a pool-off run (latest opponent only), expected to cycle | FAIL: owner, because the method claim (D6) is at stake |
| **6. Export** | Reload in a fresh process: actions within 1e-6 of recorded ones on ≥ 10,000 observations. Complete `interface.toml`. Each drone uses only its own observation. CPU time for 3 drones ≤ 10 ms (PROPOSED). The exported file reproduces the checkpoint's tier-2 score game for game | — | No hand-over (`train-export`) |
| **7. AirStack simulator 1v1** | First the **tier-2 1v1 score in the filter mode the flight copy runs** (every pair, even split, until an AirStack change). Then 20 games (PROPOSED): hold count inside tier 2's 95 % binomial prediction interval. Safety: 0 fence breaches, 0 filter emergencies, every game landed and disarmed. Stage 6 gap OPEN (§7.7) | Scripted Guard 1v1 in the same session | Owner; an AirStack session records it |
| **8. Real 1v1** (owner) | Safety only: 0 filter emergencies, 0 fence breaches, closest distance ≥ 1.10 m minus lag. Outcomes INFO (n ≈ 10). No exemptions (PREFLIGHT); `land` lands every drone, so the first tag ends the game | Scripted Guard flight first | Stop; owner |

## 3. Robustness suite for a Guard

| Group | Conditions | Status |
|---|---|---|
| Held-out Strike drones | `strike_straight`, `strike_flank`, APF Strike, trained exploiter, never in the training pool. Converted NUS S20 and P3S have a fixed team size and no alive flag (`nus/strategy.py` refuses drop-out), so tag games with them are INFO | L-1 and L-3 gated; rest INFO |
| Drone loss | 0; 1 Guard lost at a random time; 1 Strike lost; 2 Guards lost; sizes 1v1, 2v1, 3v3, 3v2 and 2v3 (outside the trained range) | G-B gated; rest INFO |
| Height | Strike start ±0.3 m and ±0.6 m from the Guards; edges of the height band; count of over and under passes (T13 failure mode) | INFO |
| Tag radius | Evaluate at 1.4, 1.6 and 1.8 m a policy trained at 1.6 m; parked Guard at each radius | INFO; owner reads the slope |
| Filter mismatch | Two by two: train with {B, every pair} × evaluate with {B, every pair}, ≥ 1,000 games each. Every pair is what flies today. Option A (team-mates only) as INFO research | B-trained evaluated on every pair: PROPOSED gate, drop ≤ 0.15 |
| Estimator, safety | Delay ×0.5 and ×1.5, noise ×2, drag off; closest approach, filter share, smoothness | INFO |

**Filter-as-wall probe.** Under option B a Strike drone no longer gives way. If T41's 829 holds relied on that, its zero-shot hold under B falls towards the parked Guard's. Same starts; INFO; informs P2.

## 4. Debugging playbook (extends `train-debug`)

| Symptom | First checks | Likely causes |
|---|---|---|
| NaN or infinite values | First bad tensor; softmax over all-masked slots; drag at speed; noise before clipping | All slots masked after drone loss; delay-buffer index; tiny standard deviation |
| Flat reward | Hold per scripted opponent; tag rate; filter share; initial log std | Opponent too strong; tag never fires (units); noise too wide or moving start (fixes: log std −1.6, `[standin_v2]`; zero-mean start, T41) |
| Reward hacking: a parked Guard | Guard speed distribution; parked-Guard control at the same radius; videos | A tag radius too large makes standing still optimal; zone small compared with 1.6 m |
| Filter as a wall | Filter share around Guards; option B probe (§3); Strike drones pinned at walls in videos (T41) | Strike drones give way under the even split |
| Self-play cycling | Cross-play table; last-mover share (5.1-e); scripted share in the pool | Pool too short; scripted slots dropped (forbidden, §6.3) |
| Tier 1 and tier 2 disagree | Paired scripted cells (T13); step responses (T11); over and under pass counts | Tier 1 heights exactly equal (T13); tier 1 too slow through the commander (0.56–0.88 s against 0.19–0.25 s, T11); delay on one side only |
| Isaac crashes at start-up | `isaac_preflight.sh` exit code; headless; `unset PYTHONPATH` (5090) | Foreign process > 1,024 MiB (exit 11); a window over remote desktop (T1) |
| GPU starved when shared | Seconds per tick against the solo rate; updates by launch + 45 min (T39 guard) | Side-by-side jobs (T32: about 2.4 s per tick); reserved memory 23–31 GB at ≥ 16,384 games (T25); set `expandable_segments` |

## 5. QC checklist

**Before any merge to `development`:**
- [ ] Full CPU suite green, with its output quoted. Isaac-marked tests green if `models/`, `envs/`, `compat/` or the filter changed.
- [ ] `git -C .. status --short -- AirStack tools patches mocap mocap.sh starling_1_indoor_params.params localisation` prints nothing.
- [ ] `tools/docs_check/check_docs.sh` 0 FAIL; every relative link in `svg_training/**/*.md` resolves (HANDOFF 19 Nov).
- [ ] Privacy scans pass; no NUS source.
- [ ] HANDOFF updated; W rows renumbered.

**Before any result appears in docs:**
- [ ] A record exists: simulator on line 1, every §8 field, and the `gates.toml` sha256 matching the frozen copy.
- [ ] A ledger row exists, append-only. A FAIL stays FAIL.
- [ ] The controls ran and behaved as required.
- [ ] Videos were recorded in the run, and a GIF plays on GitHub.
- [ ] Figures come from a committed script, with numbered captions.
- [ ] Every number links to its record. Status labels and programme wording are used. `train-gatekeeper` returned no FAIL.

## 6. Human gates: stop the automation and go to the owner

1. A result bearing on P1 or P2: a degenerate tag game (parked Guard wins); a B-trained policy collapsing under every-pair evaluation.
2. Stage 2b FAIL after a refit, or step 1's cost above the cap (D3 at stake).
3. Stage 4 or 5 method FAIL, or an exploiter beating the trained Guard as easily as a parked one.
4. A misbehaving control (positive not PASS, negative not FAIL): the gate is wrong.
5. Any wish to move a gate after a result, change the interface version or shrink the suite.
6. Anything bound for AirStack code, the AirStack simulator or real flight.
7. A mechanism claim ("the Guard learned X") for reader pages without a control.

## Open questions

1. STANDARDS conflicts: a 1.6 m tag (P1) replaces §4's FIXED "no tag radius" and "main game has no tag"; filter on every pair contradicts §5 rule 7 and `train-debug`'s per-team check. Owner ruling, then a STANDARDS edit. **RULED 22 Nov 2026** ([DISCUSSION §14](DISCUSSION_2026-11-19_20.md#14-gate-g0-rulings-owner-22-nov-2026)): the main game has a 1-for-1 tag and STANDARDS §4 "Tag" is changed; §5 rule 7 and `train-debug`'s per-team check are not changed yet.
2. Option B (P2) or every pair for training? It decides which mismatch cell is gated.
3. Tag radius equals zone radius (1.6 m): is the game degenerate? Stage 3's design check answers; owner reads it.
4. How should converted NUS Strike policies behave when a team-mate is tagged? Undefined today.
5. Real 1v1: which Strike flies (scripted, policy, hand-flown)? Is 20 AirStack simulator games acceptable while the stage 6 gap is OPEN?
6. Exploiter budget and the limits 0.15, 0.10, "half of games": approve or set.
7. The relative-link check over `svg_training/**/*.md` is not a committed script: commit one?
8. P8: evaluate against a Strike team that runs no filter?
