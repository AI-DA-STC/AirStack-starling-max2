"""S2 observations (obs_view = "full": every drone's state, D9) and the central state for critics."""
from __future__ import annotations

import torch
from torch import Tensor

from .arena import Arenas
from .game_config import GameCfg

# Policy interface version (STANDARDS §3). History: "0" = 69 observation numbers (59 state); "0.1" = 71 (61 state),
# zone centre appended at the end, 16 November 2026. A layout or scaling change raises it.
# "0.2" (owner approved 18 November 2026 ~18:20; NUS port Phase 5 plan section 12 item 1) = 73: v0.1 plus the height band's
# floor and ceiling (m, world z) appended at indices 71-72, no earlier index moved. v0.2 is OPT-IN (``obs_v02``): the game's
# own observation, ``INTERFACE_VERSION`` and ``OBS_DIM`` stay v0.1, so every v0.1 consumer (the adapters, the stand-in, the
# NUS players, the pilots) is unchanged; only the Phase 5 stage 5.2 hangar games serve v0.2.
INTERFACE_VERSION = "0.1"
INTERFACE_VERSION_V02 = "0.2"
SLOT = 7                      # rel pos 3, rel vel 3, present 1
OBS_DIM = 71                  # own 8 + game 5 + (pad_guards + pad_strikes) x 7 + zone centre 2 (default pads 5 + 3)
OBS_DIM_V02 = OBS_DIM + 2     # v0.1 + height band floor and ceiling
INTERFACE_LAYOUTS = {"0": 69, "0.1": OBS_DIM, "0.2": OBS_DIM_V02}   # observation width of each version
STATE_DIM = 61                # game 3 + 8 slots x 7 + zone centre 2
# Interface history: 69 / 59 until 16 November 2026 (S2 Task 9 fix round 1); the zone centre (2 floats) was then
# appended at the end of both, so no earlier index moved.


class ObsView:
    """Named slices of one drone's observation [OBS_DIM] (for strategies that read it).
    Positions are relative to the zone centre (STANDARDS §3); slot k holds the other drone with slot index k
    (Guard drones first, padded to pad_guards, then Strike drones): rel pos 3, rel vel 3, present 1. The last two
    floats are the zone centre relative to the arena centre (the arena is a square centred on the world origin),
    so own position + zone centre = own position in the arena, and the walls are at +-arena_half."""
    own_pos = slice(0, 3)
    own_vel = slice(3, 6)
    sin_cos_yaw = slice(6, 8)
    zone_radius = 8
    arena_half = 9
    time_left = 10
    team = 11                 # -1 Guard, +1 Strike
    alive = 12
    SLOTS_FROM = 13
    zone_centre = slice(69, 71)   # zone centre x, y relative to the arena centre (m): where the walls are
    height_band = slice(71, 73)   # v0.2 only: the height band's floor and ceiling (m, world z), as the walls for height

    def slot(self, k: int) -> slice:
        a = self.SLOTS_FROM + SLOT * k
        return slice(a, a + SLOT)


def _check_pads(cfg: GameCfg, guards: int, strikes: int) -> None:
    if guards > cfg.pad_guards or strikes > cfg.pad_strikes:
        raise ValueError(f"{guards}v{strikes} does not fit pads {cfg.pad_guards}+{cfg.pad_strikes}")
    if cfg.pad_guards + cfg.pad_strikes != 8:
        raise ValueError(f"OBS_DIM = {OBS_DIM} assumes pad_guards + pad_strikes = 8")


def _pad(feat: Tensor, cfg: GameCfg, guards: int) -> Tensor:
    """feat [N, ..., M, F] with Guard drones first -> [N, ..., pad_guards + pad_strikes, F], zeros in padding."""
    g, s = feat[..., :guards, :], feat[..., guards:, :]
    zg = g.new_zeros(*g.shape[:-2], cfg.pad_guards - g.shape[-2], g.shape[-1])
    zs = s.new_zeros(*s.shape[:-2], cfg.pad_strikes - s.shape[-2], s.shape[-1])
    return torch.cat((g, zg, s, zs), dim=-2)


def build_obs(cfg: GameCfg, pos_m: Tensor, vel_mps: Tensor, yaw: Tensor, alive: Tensor, ar: Arenas,
              time_left_s: Tensor, guards: int, strikes: int) -> dict[str, Tensor]:
    """pos_m, vel_mps [N, M, 3]; yaw [N, M]; alive [N, M] bool; time_left_s [N]. Returns
    {"guard": [N, G, OBS_DIM], "strike": [N, S, OBS_DIM]}. A drone that is out gets an all-zero observation
    except team and alive = 0; a drone that is out is absent (all zeros, present 0) in the others'. The last two
    floats (ObsView.zone_centre) are the zone centre relative to the arena centre, ar.zone_centre_m [N, 2]."""
    _check_pads(cfg, guards, strikes)
    n, m = pos_m.shape[:2]
    eye = torch.eye(m, dtype=torch.bool, device=pos_m.device)
    present = alive[:, None, :] & alive[:, :, None] & ~eye                       # [N, self, other]
    rel_p = pos_m[:, None, :, :] - pos_m[:, :, None, :]
    rel_v = vel_mps[:, None, :, :] - vel_mps[:, :, None, :]
    feat = torch.cat((rel_p, rel_v, present[..., None].to(pos_m.dtype)), dim=-1) * present[..., None]
    slots = _pad(feat, cfg, guards).reshape(n, m, -1)                            # [N, M, 8 * 7]
    own_p = torch.cat((pos_m[..., :2] - ar.zone_centre_m[:, None, :], pos_m[..., 2:]), dim=-1)
    a = alive[..., None].to(pos_m.dtype)
    team = torch.where(torch.arange(m, device=pos_m.device) < guards, -1.0, 1.0).to(pos_m.dtype)
    team = team[None, :, None].expand(n, m, 1)
    game = torch.stack((ar.zone_radius_m, ar.half_m, time_left_s), dim=-1)[:, None, :].expand(n, m, 3)
    zc = ar.zone_centre_m[:, None, :].expand(n, m, 2)
    obs = torch.cat((own_p, vel_mps, yaw.sin()[..., None], yaw.cos()[..., None], game, team, a, slots, zc),
                    dim=-1)
    obs = torch.where(alive[..., None], obs, obs * 0)                            # out: zeros ...
    obs = torch.cat((obs[..., :ObsView.team], team, obs[..., ObsView.team + 1:]), dim=-1)   # ... but team kept
    return {"guard": obs[:, :guards], "strike": obs[:, guards:]}


def obs_v02(obs_v01: Tensor, cfg: GameCfg) -> Tensor:
    """Interface v0.2 from v0.1: obs_v01 [..., OBS_DIM] -> [..., OBS_DIM_V02], the height band's floor and ceiling
    (``cfg.arena.height_band_m``, m, world z, the same frame as the own height at index 2) appended at indices 71-72.
    A drone that is out (alive 0) gets zeros there, as in every other field but team. Indices 0-70 are copied unchanged."""
    if obs_v01.shape[-1] != OBS_DIM:
        raise ValueError(f"obs_v02 takes a v0.1 observation of {OBS_DIM} numbers, got {obs_v01.shape[-1]}")
    floor, ceiling = cfg.arena.height_band_m
    band = torch.tensor((floor, ceiling), dtype=obs_v01.dtype, device=obs_v01.device).expand(*obs_v01.shape[:-1], 2)
    return torch.cat((obs_v01, band * obs_v01[..., ObsView.alive:ObsView.alive + 1]), dim=-1)


def build_state(cfg: GameCfg, pos_m: Tensor, vel_mps: Tensor, alive: Tensor, ar: Arenas, time_left_s: Tensor,
                guards: int, strikes: int) -> Tensor:
    """Central state [N, STATE_DIM]: zone radius, arena half, time left, then 8 slots (Guard drones, padding,
    Strike drones, padding) of position relative to the zone centre 3, velocity 3, present 1, then the zone
    centre relative to the arena centre (x, y, m)."""
    _check_pads(cfg, guards, strikes)
    n = pos_m.shape[0]
    p = torch.cat((pos_m[..., :2] - ar.zone_centre_m[:, None, :], pos_m[..., 2:]), dim=-1)
    feat = torch.cat((p, vel_mps, alive[..., None].to(pos_m.dtype)), dim=-1) * alive[..., None]
    slots = _pad(feat, cfg, guards).reshape(n, -1)
    return torch.cat((torch.stack((ar.zone_radius_m, ar.half_m, time_left_s), dim=-1), slots, ar.zone_centre_m),
                     dim=-1)
