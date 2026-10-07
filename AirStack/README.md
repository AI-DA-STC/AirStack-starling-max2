# AirStack — Starling Max 2 lab snapshot (code folder)

**What this folder is:** a frozen, working copy of CMU AirStack, taken 2026-10-07 from branch
`yikuan/SVG_ground_control` (commit `cf719f0`) of
[castacks/AirStack](https://github.com/castacks/AirStack), **with our one still-needed local
bug fix already applied** (camera-info init race in PegasusSimulator — patch file and
explanation in [`../patches/`](../patches/), one level up in this repo). The second patch from
the previous snapshot (swarm_commander logger-severity crash) is **already fixed upstream** on
this branch and is no longer applied.

**Why it exists:** insurance. `yikuan/SVG_ground_control` is a personal branch on CMU's
repo — it could be rebased, changed, or deleted at any time. This snapshot is the exact code
our documentation on this branch describes, so the lab can always rebuild the same setup.

**Previous snapshot:** the earlier copy (branch `daniel/diffaero_ground_control`, commit
`f544c743`, taken 2026-07-20, flown 2026-09-01→03) is preserved on git tag
`airstack-starling-max2` and branch `archive/airstack-starling-max2` of this repo. The two
AirStack branches are **siblings** (common ancestor `a46f04b` "goal tracking verified"), not
parent and child — see [`../docs/MIGRATION.md`](../docs/MIGRATION.md) for what changed.

**Differences from a normal AirStack clone:**

- Git submodules are included as **plain folders** — no `git submodule update` needed, and
  no `.gitmodules` file. Fully self-contained. Submodule commits at snapshot time:
  `PegasusSimulator` `8e01d01`, `macvo` `8683b53`, `vdb_mapping` `07cfb7b`,
  `vdb_mapping_ros2` `2d6d171`, `xdot_cpp` `c3afaf8`, `rviz_polygon_selection_tool` `018c746`.
- Patch 0001 is already in the code — do **NOT** re-apply it on top of this snapshot.
- Two machine-specific config files are excluded (`simulation/isaac-sim/docker/omni_pass.env`
  and `user.config.json`) — `./airstack.sh setup` generates both automatically (press Enter at
  its "API Token" prompt to skip the CMU-only Nucleus login).
- The OptiTrack NatNet SDK is **not** included (it is a binary download CMU's `.gitignore`
  excludes). Run `robot/ros_ws/src/perception/natnet_ros2/install_sdk.sh` once before the
  first build, or `natnet_ros2` will not compile. Our `./mocap.sh` bridge does not need it,
  but the workspace build does.

**How to use it:** follow "Setting up AirStack on a NEW machine" in the
[repo README](../README.md) one level up — this folder itself is your working folder
(`~/AirStack-starling-max2/AirStack`). No submodule or patch steps are needed.
