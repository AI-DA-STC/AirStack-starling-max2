INTERNAL · copies of the lab's project-tracker (Linear) items. Not needed to read or run anything here.

# Linear sync record, 2026-11-23

Verified project <project id="P-NEAR-31">Isaac Lab Pipeline for NUS Strategy Training</project>, team <team id="5720f96e-df12-4514-8b6b-5c8f241f9d51">NEAR Lab</team>.

The complete project inventory contains 48 issues and 18 milestones. Issue statuses are 33 Done, 3 In Progress, and 12 Backlog. All 48 issues are assigned to <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user>, with no cycle and no due date. These fields were read back after the final changes.

This sync created 28 issues and 10 milestones, added 11 comments, changed 4 existing issue statuses, and set the existing S3 milestone target date. The 11 earlier comments remain present and unchanged. No existing issue title was changed. No issue or milestone was deleted. Cycles automatically added during status changes or creation were removed and the final inventory verified.

## Every milestone, in project order

Progress is the value reported by Linear, not a percentage recalculated from issue counts.

| Milestone | Target date | Progress | Present before this sync |
|---|---|---|---|
| <projectmilestone id="a5efae9d-a753-4044-b4a6-6c31c844bdf8">S0 · Measure training speed</projectmilestone> | 2026-11-15 | 50% | Yes |
| <projectmilestone id="2eacee32-139f-438d-b6ee-55dc69d0aa27">S1 · Drone model and collision filter</projectmilestone> | 2026-11-15 | 67% | Yes |
| <projectmilestone id="1cdf9986-a68e-4938-898d-d4c16d39245a">S2 · Game and plug-in point</projectmilestone> | 2026-11-16 | 100% | Yes |
| <projectmilestone id="8836ab6a-bfcb-43cd-a9b2-760fa0b39859">S2b · Game on Isaac Lab drones</projectmilestone> | None | 31% | Yes |
| <projectmilestone id="b3b7cb59-44d1-40c1-9b66-170d3e87c175">S3 · NUS strategy scored</projectmilestone> | 2026-11-20 | 100% | Yes |
| <projectmilestone id="8cdfce07-ee24-4b6b-9041-2a20a0830c92">S4 · Realistic worlds and physics cross-check</projectmilestone> | None | 0% | Yes |
| <projectmilestone id="2e836fae-4459-47be-a9b9-668a5cdd80d6">S5 · Hand-over to AirStack</projectmilestone> | None | 0% | Yes |
| <projectmilestone id="4186b1fd-b557-4dae-a582-7fce246f2b26">Side quest · NEAR Lab strategies</projectmilestone> | None | 25% | Yes |
| <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0 · Game definition and feasibility</projectmilestone> | 2026-11-22 | 100% | No |
| <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1 · Drone model</projectmilestone> | None | 48% | No |
| <projectmilestone id="dfb3c3c7-bae6-4595-a676-cc3883b1ba6a">STE L2 · Game rules in the training copy</projectmilestone> | None | 0% | No |
| <projectmilestone id="a2d5f11b-3352-4acd-b8cb-5bb08c632a5f">STE L3 · Learner</projectmilestone> | None | 0% | No |
| <projectmilestone id="a2d062b7-39a4-448d-a134-88e761acca0e">STE L4 · Evaluation suite and gates</projectmilestone> | None | 0% | No |
| <projectmilestone id="da595ecc-f540-4048-81f9-b5db6656ff9c">STE L5 · League self-play</projectmilestone> | None | 0% | No |
| <projectmilestone id="0f6e9eb1-c091-4098-8473-2a8734b4b871">STE L6 · QC and export</projectmilestone> | None | 0% | No |
| <projectmilestone id="c1939e77-195a-444b-a2f8-5efd0851bf2e">STE L7 · AirStack side</projectmilestone> | None | 0% | No |
| <projectmilestone id="8ee15bdf-4702-42d4-ab6c-78426e14fff8">STE L8 · Real flight</projectmilestone> | None | 0% | No |
| <projectmilestone id="0c5e198b-612d-474f-9b06-6e90df9f4dc2">STE L9 · Documentation</projectmilestone> | None | 0% | No |

### Milestone descriptions

- <projectmilestone id="a5efae9d-a753-4044-b4a6-6c31c844bdf8">S0</projectmilestone>: How many games per second the training simulator runs, on the laptop and later on a workstation.
- <projectmilestone id="2eacee32-139f-438d-b6ee-55dc69d0aa27">S1</projectmilestone>: The Starling's response to velocity commands, and a copy of CMU's collision filter, inside the training simulator.
- <projectmilestone id="1cdf9986-a68e-4938-898d-d4c16d39245a">S2</projectmilestone>: The game under NUS's rules, arenas of varied size, a plug-in point any strategy fits, a scoring tool, a faster collision filter, a stand-in trainer that proves the pipe.
- <projectmilestone id="8836ab6a-bfcb-43cd-a9b2-760fa0b39859">S2b</projectmilestone>: The S2 game on rigid-body Starling drones in Isaac Lab, with a PX4-like velocity controller using the real drone's gains, compared with the fast PyTorch simulator; the stand-in trainer on both simulators, logged to TensorBoard; an Isaac Lab video of the game.
- <projectmilestone id="b3b7cb59-44d1-40c1-9b66-170d3e87c175">S3</projectmilestone>: NUS's strategy plugged in and scored two ways: under NUS's rules, and with the Starling's limits and collision filter.
- <projectmilestone id="8cdfce07-ee24-4b6b-9041-2a20a0830c92">S4</projectmilestone>: Obstacles and the construction-site world; the same games checked on full drone physics in Isaac Lab.
- <projectmilestone id="2e836fae-4459-47be-a9b9-668a5cdd80d6">S5</projectmilestone>: Export a strategy with its interface file and fly it in the AirStack simulator.
- <projectmilestone id="4186b1fd-b557-4dae-a582-7fce246f2b26">Side quest</projectmilestone>: Research: NEAR Lab trains its own Guard and Strike strategies on the same pipeline.
- <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone>: Which game the track trains, whether it is worth learning, and whether Isaac Lab can train it and at what cost. Ended at gate G0, ruled by the owner on 22 Nov 2026.
- <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone>: Make the training drone realistic: the flight estimator's error, drag, a fit to real flight logs and a comparison with the AirStack simulator. Main reads at tag 1.6 m, with a 1.15 m side track.
- <projectmilestone id="dfb3c3c7-bae6-4595-a676-cc3883b1ba6a">STE L2</projectmilestone>: The rules chosen at G0 in the training game: landing obstacles, drone loss and the second filter option with its convergence check. No issues yet: they are added when the phase starts.
- <projectmilestone id="a2d5f11b-3352-4acd-b8cb-5bb08c632a5f">STE L3</projectmilestone>: The learner: the observation, an attention encoder, one shared actor per team, a team critic and PPO. No issues yet: they are added when the phase starts.
- <projectmilestone id="a2d062b7-39a4-448d-a134-88e761acca0e">STE L4</projectmilestone>: The scoring suite and its pass/fail limits, calibrated on known players; the owner approves the limits. No issues yet: they are added when the phase starts.
- <projectmilestone id="da595ecc-f540-4048-81f9-b5db6656ff9c">STE L5</projectmilestone>: League training: pilots, then runs of record with three seeds. No issues yet: they are added when the phase starts.
- <projectmilestone id="0f6e9eb1-c091-4098-8473-2a8734b4b871">STE L6</projectmilestone>: Scoring, cross-checks and the policy file handed over. No issues yet: they are added when the phase starts.
- <projectmilestone id="c1939e77-195a-444b-a2f8-5efd0851bf2e">STE L7</projectmilestone>: A trained strategy run in the AirStack simulator (real PX4 and EKF2); specs here, build by an AirStack session. No issues yet: they are added when the phase starts.
- <projectmilestone id="8ee15bdf-4702-42d4-ab6c-78426e14fff8">STE L8</projectmilestone>: A real 1 v 1 on two Starlings, with the owner's approval. No issues yet: they are added when the phase starts.
- <projectmilestone id="0c5e198b-612d-474f-9b06-6e90df9f4dc2">STE L9</projectmilestone>: Status, records, the results page and standards updates after each ruling; runs alongside the other phases. No issues yet: they are added when the phase starts.

## Every issue

Milestone short labels in this table refer to the full names above. New issues appear in their creation order after the 20 existing issues.

| NEAR id | Title | Milestone | Status | Assignee | Cycle | Due date |
|---|---|---|---|---|---|---|
| <issue id="NEAR-955">NEAR-955</issue> | Isaac Lab: train in parallel with the Starling model and measure steps per second | <projectmilestone id="a5efae9d-a753-4044-b4a6-6c31c844bdf8">S0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-959">NEAR-959</issue> | Measure training speed on the training workstation | <projectmilestone id="a5efae9d-a753-4044-b4a6-6c31c844bdf8">S0</projectmilestone> | Backlog | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-960">NEAR-960</issue> | Copy CMU's collision filter into the training simulator | <projectmilestone id="2eacee32-139f-438d-b6ee-55dc69d0aa27">S1</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-961">NEAR-961</issue> | Starling response model from the 13 Nov flight logs (exploratory) | <projectmilestone id="2eacee32-139f-438d-b6ee-55dc69d0aa27">S1</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-962">NEAR-962</issue> | Fit the drone model from a planned-pushes real flight | <projectmilestone id="2eacee32-139f-438d-b6ee-55dc69d0aa27">S1</projectmilestone> | Backlog | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-963">NEAR-963</issue> | Game core: thousands of games at once, varied arena and zone sizes | <projectmilestone id="1cdf9986-a68e-4938-898d-d4c16d39245a">S2</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-964">NEAR-964</issue> | Check the drone model against the 12 Nov rosbag | <projectmilestone id="1cdf9986-a68e-4938-898d-d4c16d39245a">S2</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-965">NEAR-965</issue> | Faster collision filter, checked against CMU's | <projectmilestone id="1cdf9986-a68e-4938-898d-d4c16d39245a">S2</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-966">NEAR-966</issue> | Scoring tool and scripted opponents | <projectmilestone id="1cdf9986-a68e-4938-898d-d4c16d39245a">S2</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-967">NEAR-967</issue> | Plug-in point for a partner's strategy, with a written guide | <projectmilestone id="1cdf9986-a68e-4938-898d-d4c16d39245a">S2</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-968">NEAR-968</issue> | Stand-in trainer: prove the training pipe end to end | <projectmilestone id="8836ab6a-bfcb-43cd-a9b2-760fa0b39859">S2b</projectmilestone> | Backlog | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-969">NEAR-969</issue> | S2 results page | <projectmilestone id="1cdf9986-a68e-4938-898d-d4c16d39245a">S2</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-970">NEAR-970</issue> | Get NUS's strategy and its rule details | <projectmilestone id="b3b7cb59-44d1-40c1-9b66-170d3e87c175">S3</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-971">NEAR-971</issue> | Score NUS's strategy: NUS's rules against Starling limits | <projectmilestone id="b3b7cb59-44d1-40c1-9b66-170d3e87c175">S3</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-972">NEAR-972</issue> | Games among obstacles and in the construction-site world | <projectmilestone id="8cdfce07-ee24-4b6b-9041-2a20a0830c92">S4</projectmilestone> | Backlog | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-973">NEAR-973</issue> | Cross-check the fast simulator against full drone physics in Isaac Lab | <projectmilestone id="8836ab6a-bfcb-43cd-a9b2-760fa0b39859">S2b</projectmilestone> | Backlog | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-974">NEAR-974</issue> | Export a strategy and fly it in the AirStack simulator | <projectmilestone id="2e836fae-4459-47be-a9b9-668a5cdd80d6">S5</projectmilestone> | Backlog | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-975">NEAR-975</issue> | Train NEAR Lab's own Guard and Strike strategies (research) | <projectmilestone id="4186b1fd-b557-4dae-a582-7fce246f2b26">Side quest</projectmilestone> | In Progress | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-980">NEAR-980</issue> | Wrap the S2 game as an Isaac Lab environment with a PX4-like controller | <projectmilestone id="8836ab6a-bfcb-43cd-a9b2-760fa0b39859">S2b</projectmilestone> | In Progress | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-981">NEAR-981</issue> | Isaac Lab video of the game | <projectmilestone id="8836ab6a-bfcb-43cd-a9b2-760fa0b39859">S2b</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-991">NEAR-991</issue> | L0.1 Track set-up: config and test skeleton | <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-992">NEAR-992</issue> | L0.7 Process tooling and drills | <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-993">NEAR-993</issue> | L0.8 Game spec sheet | <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-994">NEAR-994</issue> | L0.9 Tag rule for the study: 1-for-1, nearest pair first | <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-995">NEAR-995</issue> | L0.10 Scripted players for the study | <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-996">NEAR-996</issue> | L0.11 Screening sweep | <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-997">NEAR-997</issue> | L0.12 Best-response test: is the game worth learning? | <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-998">NEAR-998</issue> | L0.2 Tier 2 speed in contested play | <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-999">NEAR-999</issue> | L0.13 Does tier 2 train at all? | <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1000">NEAR-1000</issue> | L0.3 STE Guard policy in tier 2 without retraining | <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1001">NEAR-1001</issue> | L0.4 Side-by-side Starling render | <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1002">NEAR-1002</issue> | L0.5 Starling video look fix | <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1003">NEAR-1003</issue> | L0.14 Crazyflie route check | <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1004">NEAR-1004</issue> | L0.6 Gate G0 | <projectmilestone id="9ef30b91-8f26-4937-bee2-19bd992bb3d8">STE L0</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1005">NEAR-1005</issue> | L1.0 5090 checks and speed re-measure | <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1006">NEAR-1006</issue> | L1.1 State delay and noise in tier 2 | <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1007">NEAR-1007</issue> | L1.1b Estimator model shape | <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1008">NEAR-1008</issue> | L1.1c Second-order estimate error | <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone> | Backlog | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1009">NEAR-1009</issue> | L1.2 Drag in tier 2 | <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1010">NEAR-1010</issue> | L1.3 Fit delay, noise and drag to real logs | <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone> | In Progress | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1011">NEAR-1011</issue> | L1.4 AirStack-simulator velocity-step logs | <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone> | Backlog | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1012">NEAR-1012</issue> | L1.5 Tier 2 against the AirStack simulator | <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone> | Backlog | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1013">NEAR-1013</issue> | L1.6 Batched estimator (only if needed) | <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone> | Backlog | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1014">NEAR-1014</issue> | L1.7 Same effects in tier 1 | <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1015">NEAR-1015</issue> | L1.8 T46's base policies re-scored on the new tier 2 | <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1016">NEAR-1016</issue> | L1.9 1v1 best-response read at tag 1.6 m, plus a scripted 1v1 screen also at 1.15 m | <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone> | Backlog | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1017">NEAR-1017</issue> | L1.10 Tag drawn within 1.5–1.7 m, 3v3, both sides | <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone> | Backlog | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |
| <issue id="NEAR-1018">NEAR-1018</issue> | L1 side track: 1.15 m tests (L1.11–L1.15) | <projectmilestone id="3c2dcfba-9bc7-4bdf-a0d8-78dcbf3137ca">STE L1</projectmilestone> | Done | <user id="2482b7a1-d9f6-47e1-b133-9690be76bf23">HweHuang Chia</user> | None | None |

## Comments added in this sync

All 11 requested comments below were absent before this sync, added now, and read back. Each appears once. Paragraph wrapping is normalized; visible wording is preserved.

### <issue id="NEAR-970">NEAR-970</issue>, added now

<comment id="b4221608-8c36-4920-8e1c-17c7e4a50556" />

2026-11-23. Done. NUS shared its code (not trained checkpoints); STE installed the branch NUS named as the most recent on the lab's RTX 5090 workstation on 17 Nov, ledger row T35 (65 of NUS's 66 tests pass; NUS confirmed the one failure is an out-of-date test). The target said "on the laptop": the code stays on the 5090 by the owner's decision; the laptop works from the lab's own converted policies and settings files. NUS's game has no metres or seconds and NUS said to scale it to the arena, so STE chose a scale for the hangar. Details: `svg_training/docs/WHAT_WE_DID_DAY_BY_DAY.md` §1–3.

### <issue id="NEAR-971">NEAR-971</issue>, added now

<comment id="d388bf63-75b8-454c-a1b4-b1abefd9c6eb" />

2026-11-23. Done, scored on the hangar set-up only (not per arena size). NUS's game was copied to PyTorch and checked against the original (ledger row T15 PASS), and STE-trained NUS-code policies converted (ledger rows T16–T17 PASS); six tests then brought the game to Starling conditions one step at a time (ledger rows T18–T20 and T22–T24 INFO; T21 ABORTED, over time): the safety filter and free height break NUS's push-blocking, so the Strike team gets through far more often, and Isaac Lab's physics drones agree with the fast simulator. Retraining in STE conditions stopped at stage 5.1 (ledger row T43 FAIL: one seed of three missed the learner check and one scripted range) and the NUS route is paused (lead call D8, 20 Nov); STE's own learning track continues under <issue id="NEAR-975">NEAR-975</issue>.

### <issue id="NEAR-981">NEAR-981</issue>, added now

<comment id="6a9b088a-bf5c-413e-9b60-8f1b8c03e9bb" />

2026-11-23. Done. Seven scripted games rendered headless on Isaac Lab Starlings (2 v 1 and 5 v 3, lab to large arenas; two in the construction-site world and one among blocks and columns, all as backdrops), captioned "training simulator", in `svg_training/docs/media/s2b_*` (S2b Task 6). Tool VID-1 then replays a run's key games in 3-D with the Starling's own look from a top and a 3-D camera (MP4 + GIF): L0.11's scripted games and the L0.12 trained teams, shown in `svg_training/ste_learning/G0_REPORT.md`. Clips are pictures, with no ledger row.

### <issue id="NEAR-980">NEAR-980</issue>, added now

<comment id="b25c9f9a-a3dc-4d6a-96d3-e6c3f61eca13" />

2026-11-23. Built (S2b Tasks 1–8): rigid-body Starlings in Isaac Lab 2.3.2 flown by a copy of PX4 1.14's control loops with the drone's own gains (yaw-rate gains SIM-ONLY, owner ruling), scored on both simulators; it now carries the STE track's Isaac Lab work (ledger rows T53, T62, T64). Its "Done when" target is not fully met: the two physics worlds differ by 1.15 mm after 1 s against a 1 mm limit (ledger row T10 FAIL, accepted by the owner); step tests T11 FAIL; scripted games T13 FAIL (Strike drones pass over or under Guards; the owner kept this, option (a)). Speed T12 INFO: up to 262,190 drone-steps/s on the laptop, above S0's 20,000 line. The registered Isaac Lab task (Task 8b) is not built. Results: `svg_training/docs/S2B_RESULTS.md`. **Owner decides:** close as built, or keep open until Task 8b is built.

### <issue id="NEAR-968">NEAR-968</issue>, added now

<comment id="a9e1abf6-f72f-4087-9e5f-95d178c7399a" />

2026-11-23. Result: ledger row T14 FAIL. The pipe worked end to end on Isaac Lab drones (2 seeds trained 100 M game-steps each, logged to TensorBoard, scored), but the Guards learned almost nothing: the gate asked for 20 more holds per 100 games than random Guards, and the seeds held 0 per 100 against straight Strikes and 7 and 13 per 100 against flanking ones; seed 3 was not run (it cannot change the verdict). Since then the STE track's trainer showed training works on the same pipe, Isaac Lab included (ledger row T53 PASS: trained Guards hold 832 of 1,000, parked Guards 538). **Owner decides:** close as Done with the failed result, or keep open (seed 3 on the RTX 5090, or a new stand-in plan).

### <issue id="NEAR-973">NEAR-973</issue>, added now

<comment id="f11266df-99d6-4229-b942-cb7d8e620353" />

2026-11-23. Results so far: ledger rows T10 FAIL (accepted), T11 FAIL, T12 INFO, T13 FAIL (scripted games: hold rates differ by more than 10 per 100 games in 36 of 60 cells, mostly because Strike drones pass over or under Guards on the physics drone). The trained players move between the two simulators far better: the same training on both gives 832 and 836 holds of 1,000 (ledger row T53, STE task L0.13), and the 1.6 m trained teams re-scored on Isaac Lab shift by −33 to +47 of 1,000 per cell, in both directions (ledger row T64, STE task L1.8). **Owner decides:** close as Done with the failed T13 result, or keep open for the cross-checks of later STE phases.

### <issue id="NEAR-962">NEAR-962</issue>, added now

<comment id="54ac65f8-8e9c-403a-8daf-beb59072e44e" />

2026-11-23. A first fit from the 13 Nov flight log is done (ledger row T63, EXPLORATORY, STE task L1.3): while hovering, the drone's position estimate differs from the motion-capture position by about 1 cm (σ 0.0099 m, lasting about 1.2 s), its velocity by about 2 cm/s, its tilt by at most 0.003 rad; while moving the position spread reaches 2.5 cm. The planned-pushes flight is still needed. It should record: the motion-capture time on a clock synced with PX4; ULog at the highest rate for vehicle_local_position, vehicle_attitude, vehicle_visual_odometry and estimator_innovations; an independent reference if possible; hovers of at least 5 min on both drones; moving legs at known speeds; each log's checksum and EKF2_EV_DELAY / EKF2_EV_CTRL.

### <issue id="NEAR-959">NEAR-959</issue>, added now

<comment id="bf0ee6ab-866e-44b0-b720-be7b6cfc12b1" />

2026-11-23. The laptop's training speed with both teams playing is measured (ledger row T48, STE task L0.2): 3 v 3, fast simulator 51,000–208,000 and Isaac Lab 10,000–67,000 game-steps/s, Isaac Lab about 5× slower. On the RTX 5090 the machine checks are done (23 Nov, STE task L1.0: same game results as the laptop, 2,213 tests pass; record `svg_training/records/2026-11-23_ste_l10_5090_checks_record.md`); its speed re-measure runs on an idle GPU with the STE L1.7 speed check, and closes this issue.

### <issue id="NEAR-972">NEAR-972</issue>, added now

<comment id="d979842f-ac99-4bf7-8c4b-9dba30bcb3be" />

2026-11-23. Order ruled by the owner at gate G0 (22 Nov, ruling R11): open arena until a trained team passes the opponent panel, then random blocks and columns, then the construction-site world. The STE learner (phase L3) is designed so obstacles can be added without a new network.

### <issue id="NEAR-974">NEAR-974</issue>, added now

<comment id="40e756ab-2efd-43da-9cdc-acae901cb9ff" />

2026-11-23. Unchanged. This is phase L7 of the STE learning track (milestone STE L7 · AirStack side): specs written in `svg_training/`, the build and the AirStack-simulator games by an AirStack session, with the owner's approval.

### <issue id="NEAR-975">NEAR-975</issue>, added now

<comment id="80961f5b-80c2-4dda-9c25-13410ff474d7" />

2026-11-23. This issue is now the umbrella of STE's own learning track (since 20 Nov 2026), planned in ten phases, each a milestone of this project: STE L0 · Game definition and feasibility (done, gate G0 ruled 22 Nov), STE L1 · Drone model (in work), STE L2 · Game rules in the training copy, STE L3 · Learner, STE L4 · Evaluation suite and gates, STE L5 · League self-play, STE L6 · QC and export, STE L7 · AirStack side, STE L8 · Real flight, STE L9 · Documentation. Plan: `svg_training/ste_learning/PLAN.md`. Nothing trained into a strategy yet; nothing flown. Terms used in these issues: "tier 1" = the fast training simulator, "tier 2" = Isaac Lab's physics drones; "ledger row Tnn" = a numbered test result in `svg_training/records/LEDGER.md`; G0 = the gate the owner ruled at the end of L0, with numbered rulings (R11) and decisions (D8, D9); P5 = the approved AirStack-simulator logs; "5090" = the lab's RTX 5090 training workstation.

## Earlier comments, already present

These 11 comments were already present, were not reposted or edited, and remain in Linear.

### <issue id="NEAR-955">NEAR-955</issue>, already present

<comment id="14f2ac98-0e89-41a4-b522-1ca7a4cf1284" />

2026-11-16. Done for the laptop (RTX 5070 Ti), ledger row T1, 2026-11-15. Fast simulator, 5 Guard and 3 Strike drones with full sensing: about 48,000 games-steps per second. Isaac Lab full drone physics: up to 455,000 drone steps per second. These are simulator speeds with random actions, not training speeds. Not done: the training workstation (new issue in S0). Results: `svg_training/docs/S0_RESULTS.md`.

### <issue id="NEAR-960">NEAR-960</issue>, already present

<comment id="eb4061ad-4ad0-4009-ba9c-af2c88d75707" />

2026-11-15. Built and checked against CMU's filter on 2,000 recorded scenes, ledger row T2: FAIL on 2 of 4 checks, accepted by the owner on the exact counts (13 and 109 scenes outside the limits; emergency decisions agree in 1,998 of 2,000). Results: `svg_training/docs/S1_RESULTS.md`.

### <issue id="NEAR-961">NEAR-961</issue>, already present

<comment id="f9345da5-c52e-4d58-894a-abbdf5ea3992" />

2026-11-15. Fitted on the 13 Nov gamepad flight of drone_2 (ledger row 36): at up to 0.5 m/s the drone follows its command about 0.1–0.15 s late. Exploratory, no gates. The AirStack simulator was also fitted (ledger row T3, FAIL): its commander runs on the wall clock while the simulated PX4 runs about 1.9 times faster, so it is not used for training.

### <issue id="NEAR-963">NEAR-963</issue>, already present

<comment id="c0c46d48-8527-4aa3-9ce4-c7fb675a9d3a" />

2026-11-16. Done. The game runs thousands of games at once with random arena (4–16 m) and zone sizes; NUS's rules are the main game, contact tags stay for the side quest; the Starling layer adds the fitted drone model and CMU's collision filter on every pair. Every part reviewed; a bug at the arena walls was found in review and fixed. Results: `svg_training/docs/S2_RESULTS.md`.

### <issue id="NEAR-964">NEAR-964</issue>, already present

<comment id="85735500-cca4-4b80-8a75-8c82cf7614cc" />

2026-11-16. Done with a FAIL, ledger row T5. Worst leg 0.120 m/s against a 0.10 m/s limit; the timing check failed mainly because of how the check fed the setpoint (joined as in the original fit, the three clean pushes fit within 0.05 m/s); the fourth leg is a 408 s gap in the recording. The model stays exploratory until a planned-pushes flight (<issue id="add143af-21f1-4f88-ab36-ba948ac5d49b" label="NEAR-962" href="https://linear.app/nearlab/issue/NEAR-962/fit-the-drone-model-from-a-planned-pushes-real-flight" />).

### <issue id="NEAR-965">NEAR-965</issue>, already present

<comment id="f105066d-aa2e-44be-9cd2-de1a4d87d77a" />

2026-11-16. Done, ledger row T8 PASS: same answers as the full filter on all 2,000 test scenes, about 121,000 game-steps/s for 5 v 3 at 4,096 games (target 100,000), against 9,900 before; about 90,000 averaged over a whole game (information only). The speed-error limit was read at its 4 written decimals (owner's ruling). Ledger row T7 is an aborted first attempt, stopped to put in the wall fix.

### <issue id="NEAR-966">NEAR-966</issue>, already present

<comment id="f4c9f075-c1ca-4c62-b8e0-1196749e47a1" />

2026-11-16. Done. Scoring tool and five scripted Guard and two scripted Strike tactics; reference runs ledger rows T6 and T9 (T9 on the fixed walls). Crowded 5 v 3 games still bring drones to 0.75–0.80 m near walls: a limit of CMU's filter, which does not know the walls, shared with the real commander.

### <issue id="NEAR-967">NEAR-967</issue>, already present

<comment id="b0aed77f-9ed2-4d70-95a1-f2a5f88dbbca" />

2026-11-16. Done. skrl and Gymnasium adapters and the partner guide `svg_training/docs/PLUG_IN.md`, with runnable examples a test executes; checked by a newcomer read-through. The worked example with the stand-in trainer comes with <issue id="65040454-330f-459b-adcd-e3b0c17bbae0" label="NEAR-968" href="https://linear.app/nearlab/issue/NEAR-968/stand-in-trainer-prove-the-training-pipe-end-to-end" />.

### <issue id="NEAR-968">NEAR-968</issue>, already present

<comment id="be2e458e-d776-45c6-9191-b5671b432f09" />

2026-11-16. Moved to S2b by the owner: it runs on both simulators (PyTorch as a control, then Isaac Lab), with TensorBoard logging, so training is proven on the simulator that matters.

### <issue id="NEAR-969">NEAR-969</issue>, already present

<comment id="78bab450-d43c-49fa-a19d-1cc09430204a" />

2026-11-16. Done: `svg_training/docs/S2_RESULTS.md`, after a final review of the whole stage and one fix wave.

### <issue id="NEAR-973">NEAR-973</issue>, already present

<comment id="bfb99ac8-e508-4b93-babe-6b2dbb284c98" />

2026-11-16. Moved from S4 to S2b: the owner pulled the Isaac Lab work forward.

## Not applied and why

None of the requested Linear changes remain unapplied. The three existing milestone dates for <projectmilestone id="a5efae9d-a753-4044-b4a6-6c31c844bdf8">S0</projectmilestone>, <projectmilestone id="2eacee32-139f-438d-b6ee-55dc69d0aa27">S1</projectmilestone>, and <projectmilestone id="1cdf9986-a68e-4938-898d-d4c16d39245a">S2</projectmilestone> were preserved. Only the specified existing milestone date and the new dated milestone were set. <projectmilestone id="8836ab6a-bfcb-43cd-a9b2-760fa0b39859">S2b</projectmilestone> remains open with no target date. No issues were created for STE L2–L9, as instructed. No completion dates were backdated or supplied manually.
