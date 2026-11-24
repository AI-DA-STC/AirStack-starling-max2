Simulator: tier 2, Isaac Lab rigid-body Starling; pipeline check, not for flight; observed in the training simulator

# L3.1 Isaac smoke: the tier-2 skills fixed-choice replay

1000 games per cell, 2400 ticks, device cuda.

| Control | Status |
|---|---|
| ctl_clips | PASS |
| ctl_device_placement | PASS |
| ctl_nonfinite_stale | PASS |
| ctl_reload_across_devices | PASS |
| ctl_replay_guard | PASS |
| ctl_replay_strike | PASS |

Throughput: two-level team 2,312,729 game-steps/s, one script 2,994,698; ratio 0.772 (spec B1)

Clips: videos/l3_smoke_tier2_game0_reach.gif: tier 2, game 0, reach; videos/l3_smoke_tier2_game1_reach.gif: tier 2, game 1, reach

Of record: True. Upsets: {'guard': {'two_level': 0, 'scripts': 0, 'composite': 0}, 'strike': {'two_level': 0, 'scripts': 0, 'composite': 0}}.
Device: host syncs inside the dispatch (choose, command) in the replay batches: 0 (torch.cuda sync debug mode, a prototype that does not see every sync). CUDA replay tolerance: exercised only by the Isaac run on CUDA (exploit.replay_ok's CUDA tolerances); --dry-cpu plays the CPU game-for-game rule.
