INTERNAL · a build plan written for the lab's AI coding assistants (17 November 2026), kept for history, not instructions: the contact-tag track, a side quest in which a tag is physical contact; the track was not started (the contact tag exists as a tested game mode only, nothing is trained with it) and it stays a side quest after gate G0 gave the main game a tag at a distance · start at [../../README.md](../../README.md); the side quest's standing today: [STANDARDS §2](../../STANDARDS.md#2-wording)

# Contact-tag track: a Guard drone that makes contact, tested without crashing drones

**Status: DRAFT for the owner (17 November 2026). Nothing approved or started.** Every gate below is PROPOSED
(STANDARDS §7: approved and frozen before its run). Every result is "observed in the training simulator" unless a
stage says otherwise. Nothing in this plan authorises a flight; flight stages are hand-overs to the flight stack and
follow `docs/PREFLIGHT.md` and `docs/RUNBOOK.md` at the repository root.

## Why a separate track

The owner split the work into two tracks (17 November 2026):

| Track | Game | Contact | Safety filter |
|---|---|---|---|
| 1. Area denial (the partner strategy port) | Guard team keeps the Strike team out of the zone by position | none | on, every pair |
| 2. **Contact tag (this plan)** | one Guard drone against one Strike drone; the Guard drone tags by contact | the goal | staged (below) |

This matches the programme's design review, which keeps a contact demonstration separate from the area denial
demonstration (programme FR&PDR v1.2, §6.1; confidential, cited by name only). It also matches STANDARDS: the tag
is a side quest; the main game has no tag (`STANDARDS.md:118`).

## What already exists

- Contact in tier 1: two centres closer than 0.50 m (`STANDARDS.md:119`; `configs/s2_game.toml [contact_rules]`;
  `source/svg_training/core/pair_rules.py` `contact_tags`). The Strike drone leaves; the Guard drone leaves unless
  `guard_survives_tag_prob` (now 0.0).
- The `contact` preset runs the safety filter between team-mates only (`core/starling_layer.py` `filter_pairs`).
- Tier 2 (Isaac Lab) drones have no colliders (`docs/S2B_RESULTS.md:288-290`).
- The flight stack's filter keeps every pair ≥ 1.10 m apart and cannot exempt one pair (`STANDARDS.md:166, 188-192`).

## What the reviews found (17 November 2026; three read-only reviews: training, physics, flight stack)

1. **No simulator here can be trusted for the contact itself.** Tier 2 has no colliders and no aerodynamics; with
   colliders PhysX would bounce two boxes with an invented restitution; blades are not geometry. What can be trusted:
   the approach and the contact test (distance). Contact physics must be rehearsed on hardware.
2. **Downwash rules out contact from above or below.** Scaled from Crazyflie measurements, the lower drone loses
   about 35 % of thrust 0.64 m below (DERIVED; arxiv.org/html/2507.09463). Contact is sideways and level only.
3. **The fall is the hazard, not the touch.** About 0.1 J at 0.83 m/s against about 6.6 J for a 1.2 m fall
   (DERIVED). Blade tips move at about 53 m/s: overlapping rotor discs break blades at any closing speed, so
   **propeller guards on both drones for any real contact**, and contact low, over a net or mats.
4. **Tag distance shapes the learned behaviour.** At 1.5 m a Guard drone parked at the zone centre tags almost
   everything in small arenas; the Guard drone's response lag stops mattering. Below about 0.7 m, timing and
   closing speed start to count. A distance that shrinks with performance, given to the policy as an input, with
   about 20 % of games replayed at earlier distances, is the supported route (arxiv.org/pdf/2010.08193).
5. **The flight stack can host most stages without code changes**: a proximity tag at 1.5 m with the filter on;
   the filter radius can be lowered live (done in flight, ledger #37); CMU's commander has a real/sim drone mix
   (`drone_modes`), never flown. Real contact needs a pair mask in CMU's filter and the owner changing two
   PREFLIGHT rules.

## Rules for the contact tag (PROPOSED)

| Rule | Value | Status |
|---|---|---|
| Contact | 3-D centre distance < tag distance d; d = 0.50 m at the end (`STANDARDS.md:119`) | d schedule PROPOSED |
| Closing-speed cap | a tag counts only if the closing speed ≤ v_cap; above it, a **foul**: the Guard drone leaves, the Strike drone stays | v_cap OPEN (owner): start 0.3 m/s |
| Geometry | only when the height difference ≤ 0.2 m (sideways, level); no tag from above or below | PROPOSED |
| Arena | the hangar band (≈ 7–8 m, 8 m hangar), heights 0.5–1.8 m | PROPOSED |
| Logging at every tag | closing speed, height difference, approach angle, filter corrections | PROPOSED |

## Stages

Each stage ends at a **stop point** for the owner. Each run gets a record in `records/` and a row in
`records/LEDGER.md`; each flight a row in the flight ledger `docs/record/LEDGER.md` at the repository root.

### Stage 1 — Training simulator (this folder)
1. Code (test first, `train-change`): closing speed and geometry at every tag; the closing-speed cap and foul;
   the height rule; d as a game setting and a policy input; a switch for the `contact` preset to run the filter on
   every pair (needed for stage 2's d = 1.5 m with the filter on).
2. Train 1 v 1 on tier 1 with the Starling layer, d shrinking 1.5 → 1.2 → 0.9 → 0.7 → 0.5 m when a stage target is
   met; Strike drones retrained through the opponent pool as d shrinks.
3. Tier 2 cross-check of the approach (no collider physics trusted).

Proves: a Guard policy that makes slow, level contact in the training simulator.
**Gates (PROPOSED), per d, 1,000 games against dodging scripted Strike drones, 95 % intervals:** tag rate ≥ 0.6;
95th-percentile closing speed at tag ≤ v_cap; fouls ≤ 0.05; a Guard drone hovering at the zone centre holds less
than the policy does (the "parking" check); tier 1 vs tier 2 tag rate within 0.10. **Stop.**

### Stage 2 — Proximity tag in flight (flight stack as it is)
d = 1.5 m, filter on every pair (radius 0.55 m), scored by motion capture. AirStack simulator first, then real.
Proves: chase and tag on real drones. Hazard: drones 0.06–0.10 m inside the keep-out (ledger #34, #35, #37); a
Guard drone pinned against a wall. **Stop.**

### Stage 3 — "Virtual contact" in flight (no code change)
Filter on; its radius lowered live in steps 0.55 → 0.45 → 0.35 m per drone; contact scored as distance ≤ keep-out
+ a margin. Never raise the radius while drones are inside it (the push-apart fires).
Proves: the filter holds close to the airframe at game closing speeds. **Stop.**

### Stage 4 — Real Guard drone against a simulated Strike drone
CMU's real/sim mix (`drone_modes`; the October 2026 monthly report names it, confidential, not quoted). Needs an owner exception to
PREFLIGHT's "no simulator on the network" rule, a separate drone name, and care with the simulator clock.
Proves: real tracking at the moment of contact, with nothing to hit. **Stop.**

### Stage 5 — Guarded Guard drone against a mock Strike drone
A foam sphere on a rigid pole (never a string: it can wrap a propeller), at 1 m or lower, over mats; propeller
guards on the Guard drone (model refitted with guards: STANDARDS §5 rule 10). Closing speed raised step by step
from 0.3 m/s. Abort: tilt beyond 30° → KILL.
Proves: real impact, closing speed and recovery, with only the Guard drone at risk. **Stop.**

### Stage 6 — Two guarded drones
Sideways and level, ≤ 0.3 m/s, over a net, then game speed. Needs: CMU's filter with a pair mask and a backstop
radius below the tag distance (outside this folder; owner and CMU); the owner changing the PREFLIGHT rules that
forbid exempt pairs; the `drone_1` motor hazard cleared (root `CLAUDE.md` iron rule 10). Contact → KILL both, land,
inspect before re-arming.
Proves: the end goal. **Stop.**

## Not in this plan

Changes to CMU's filter, AirStack configs or PREFLIGHT (owner and flight stack); any value flowing from training
into the drone (STANDARDS §1); hard contact without guards.

## Open for the owner

1. v_cap (closing-speed cap) to start with, and the end value.
2. Propeller guards for the Starling 2 Max: none found as a product; source or make.
3. Whether stage 4 (real/sim mix) is worth a PREFLIGHT exception, or skip to stage 5.
4. Contact is not described on the programme's public pages (STANDARDS §2): keep this track internal.
