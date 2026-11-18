"""Alternating best-response self-play with the archive pool (NUS port Phase 5, task M4), described from the partner's
``ma_skills/runner/ensemble_self_play_runner.py`` and ``fixed_opponent_runner.py`` (plan section 4.1, items 1-7 and 14). No APEX
(plan P5-1); no specialists, generation gate, plateau restart or benchmark opponents (disabled in the reference runs).

Per generation g (``first_team`` trains in odd generations, the other team in even ones):

1. a **fresh learner** of that team (``nus/mappo.py``), initialised from the stage seed (run seed + g - 1) and the team code;
2. the **pool**: the archived entries of the other team chosen by ``selection.select_opponents``, fixed for the generation, plus the
   permanent scripted slot (APF of the other team); frozen entries act deterministically, as one batched call over their stacked
   parameters (``OpponentPool``);
3. every update plays whole games from fresh starts in **equal blocks**, one per slot (learned slots first, APF last); the critic sees
   the slot one-hot; the per-slot win rates feed an exponential moving average;
4. every ``selection_interval_updates`` updates and at the last one the learner (mean action) plays ``selection_games_per_opponent``
   games per slot from fresh starts; rank = (geometric mean of the per-slot win rates, worst, mean), rounded; the **best** snapshot so
   far is kept, and at the end of the generation it is archived (``archive/<gggg>_<team>/actor.pt`` and ``metadata.json``);
5. a resumable state file and two alternating checkpoints (``resume_a``/``resume_b``) let a run continue after a stop; a non-finite
   metric aborts (``NonFiniteError``) and leaves the last checkpoint.

Runs write only under the run folder given (``runs/...``, git-ignored). Everything that touches games is batched; the Python loops are
over steps, updates, opponents of a pool (to stack them once) and generations. This file holds no partner value (G2).
"""
from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import torch

from .mappo import Learner, MappoActor, squash, stack_trees, trunk_forward
from .method_cfg import NusMethod, team_of_generation
from .replica_train import NusTrainEnv, TrainState
from .selection import rollout_batch_size, select_opponents, stage_seed

STATE_FILE = "self_play_state.json"
SCHEMA = 1


def other_team(team: str) -> str:
    return "strike" if team == "guard" else "guard"


def _seeded(device: torch.device, *parts: int) -> torch.Generator:
    """A generator on ``device`` (a CUDA draw refuses a CPU generator) seeded from the parts."""
    state = np.random.SeedSequence([int(p) for p in parts]).generate_state(1, dtype=np.uint64)[0]
    return torch.Generator(device=device).manual_seed(int(state) >> 1)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False))
    os.replace(tmp, path)


class OpponentPool:
    """The frozen learned opponents of one team (stacked parameters, deterministic) and the scripted APF slot, in equal game blocks."""

    def __init__(self, env: NusTrainEnv, team: str, actors: list[MappoActor]):
        self.env, self.team, self.learned = env, team, len(actors)
        self.slots = self.learned + 1
        self.speed, self.floor = env.team_speed(team), env.deploy.disk_floor
        if actors:
            m = actors[0].method
            self.forward = dict(bf16=m.compute_dtype == "bfloat16", activation=m.activation, eps=actors[0].eps, use_norm=m.use_layernorm)
            with torch.no_grad():
                self.tree = stack_trees([_detached(a.trunk.tree()) for a in actors])

    @torch.no_grad()
    def actions(self, state: TrainState, block: int) -> torch.Tensor:
        """(N, team size, 2) for N = slots x block games: block i of games plays learned opponent i; the last block plays APF."""
        guard_obs, strike_obs = self.env.observe(state)
        obs = guard_obs if self.team == "guard" else strike_obs
        apf = self.env.apf_actions(state, self.team)
        if not self.learned:
            return apf
        n_learned = self.learned * block
        a, d = obs.shape[1], obs.shape[2]
        stacked = obs[:n_learned].reshape(self.learned, block * a, d)
        mean = trunk_forward(self.tree, stacked, **self.forward)
        learned = squash(mean, self.speed, self.floor).reshape(n_learned, a, -1)
        return torch.cat((learned, apf[n_learned:]), dim=0)


def _detached(tree: dict) -> dict:
    def d(pair):
        return tuple(t.detach().clone() for t in pair)
    return {"proj": d(tree["proj"]), "input": d(tree["input"]), "output": d(tree["output"]),
            "blocks": [{k: d(v) for k, v in b.items()} for b in tree["blocks"]]}


class SelfPlay:
    """One lineage: ``seed`` is the run seed. ``updates_per_generation``, ``games_per_update`` and ``selection_after`` override the
    method's schedule (variants 5.1b/5.1c and tests); by default the copied method's are used."""

    def __init__(self, method: NusMethod, env: NusTrainEnv, seed: int, run_dir: Path | str, *, device: torch.device | str = "cpu",
                 updates_per_generation: int | None = None, games_per_update: int | None = None,
                 selection_after: tuple[int, ...] | None = None, generations: int | None = None):
        self.method, self.env, self.seed, self.device = method, env, int(seed), torch.device(device)
        self.run_dir = Path(run_dir)
        self.updates = updates_per_generation or method.updates_per_generation
        self.games_per_update = games_per_update
        self.generations = generations or method.generations
        every = method.selection_interval_updates
        self.selection_after = set(selection_after) if selection_after else {u for u in range(every, self.updates + 1, every)}
        self.selection_after.add(self.updates)
        path = self.run_dir / STATE_FILE
        if path.exists():
            self.state = json.loads(path.read_text())
            if self.state.get("schema") != SCHEMA or self.state.get("seed") != self.seed:
                raise ValueError(f"{path}: another run (schema or seed differs)")
        else:
            self.state = {"schema": SCHEMA, "seed": self.seed, "archive": [], "active": None}
        self.learner: Learner | None = None
        self.pool: OpponentPool | None = None

    # ------------------------------------------------------------------ archive
    def load_actor(self, entry: dict[str, Any]) -> MappoActor:
        actor = MappoActor(self.env.obs_dim, self.method, self.env.deploy.layernorm_epsilon)
        actor.load_state_dict(torch.load(Path(entry["path"]) / "actor.pt", map_location="cpu", weights_only=True))
        return actor.to(self.device).eval()

    def _save(self) -> None:
        _write_json(self.run_dir / STATE_FILE, self.state)

    # ------------------------------------------------------------------ generation
    def _start(self) -> None:
        generation = len(self.state["archive"]) + 1
        team = team_of_generation(self.method, generation)
        active = self.state["active"]
        if active is None:
            chosen = select_opponents(self.state["archive"], team=team, generation=generation, seed=self.seed,
                                      maximum=self.method.max_learned_opponents, recent=self.method.recent_opponents)
            slots = len(chosen) + 1
            games = self.games_per_update or rollout_batch_size(slots, self.method.episodes_per_opponent, self.method.minimum_rollout_batch)
            if games % slots:
                raise ValueError("games per update must split into equal blocks per slot")
            active = {"generation": generation, "team": team, "opponents": chosen, "games": games, "update": 0, "checkpoint": None,
                      "ema": None, "best_rank": None, "best_update": None, "best_ema": None, "best_actor": None, "evaluations": []}
            self.state["active"] = active
        self.learner = Learner(self.method, self.env, team, stage_seed(self.seed, generation), self.device)
        self.pool = OpponentPool(self.env, other_team(team), [self.load_actor(e) for e in active["opponents"]])
        self.generator = _seeded(self.env.device, self.seed, generation, 0)
        if active["checkpoint"]:
            self._restore(Path(active["checkpoint"]))
        else:
            self._checkpoint()

    def _checkpoint(self) -> None:
        active = self.state["active"]
        last = Path(active["checkpoint"]).name if active["checkpoint"] else "resume_b"
        folder = self.run_dir / "generations" / f"{active['generation']:04d}_{active['team']}" / ("resume_b" if last == "resume_a" else "resume_a")
        folder.mkdir(parents=True, exist_ok=True)
        torch.save({"actor": self.learner.actor.state_dict(), "critic": self.learner.critic.state_dict(),
                    "actor_opt": self.learner.actor_opt.state_dict(), "critic_opt": self.learner.critic_opt.state_dict(),
                    "generator": self.generator.get_state()}, folder / "learner.pt")
        if active["best_actor"] is not None:  # the best snapshot travels with the checkpoint, so a resume keeps it
            best = torch.load(active["best_actor"], weights_only=True)
            torch.save(best, folder / "best_actor.pt")
            active["best_actor"] = str(folder / "best_actor.pt")
        active["checkpoint"] = str(folder)
        self._save()

    def _restore(self, folder: Path) -> None:
        saved = torch.load(folder / "learner.pt", map_location="cpu", weights_only=True)
        self.learner.actor.load_state_dict(saved["actor"])
        self.learner.critic.load_state_dict(saved["critic"])
        self.learner.actor_opt.load_state_dict(saved["actor_opt"])
        self.learner.critic_opt.load_state_dict(saved["critic_opt"])
        self.generator.set_state(saved["generator"])

    # ------------------------------------------------------------------ one update
    def _update(self) -> dict[str, float]:
        active, learner = self.state["active"], self.learner
        games, slots = active["games"], self.pool.slots
        block = games // slots
        slot_ids = torch.arange(slots, device=self.device).repeat_interleave(block)
        start = self.env.reset(games, self.generator)
        rollout = learner.collect(self.env, start, self.generator, self.env.episode_steps,
                                  lambda s, g: self.pool.actions(s, block), slot_ids)
        metrics = learner.update(rollout, self.generator)
        wins = rollout.reached if active["team"] == "strike" else ~rollout.reached
        rates = wins.reshape(slots, block).float().mean(dim=1).tolist()
        alpha = self.method.win_rate_ema
        active["ema"] = rates if active["ema"] is None else ((1 - alpha) * np.asarray(active["ema"]) + alpha * np.asarray(rates)).tolist()
        active["update"] += 1
        return metrics | {f"win_vs_slot{i}": r for i, r in enumerate(rates)}

    @torch.no_grad()
    def evaluate(self, games_per_opponent: int | None = None) -> dict[str, Any]:
        """The learner's mean action against every slot of the pool, ``games_per_opponent`` games each from fresh starts."""
        active = self.state["active"]
        per = games_per_opponent or self.method.selection_games_per_opponent
        slots = self.pool.slots
        generator = _seeded(self.env.device, self.seed, active["generation"], active["update"] + 1)
        state = self.env.reset(slots * per, generator)
        team = active["team"]
        for _ in range(self.env.episode_steps):
            guard_obs, strike_obs = self.env.observe(state)
            own, _ = self.learner.act(guard_obs if team == "guard" else strike_obs, None, deterministic=True)
            other = self.pool.actions(state, per)
            g_act, s_act = (own, other) if team == "guard" else (other, own)
            state, _ = self.env.step(state, g_act, s_act, self.learner.gamma)
        reached = state.game.reached > 0
        wins = (reached if team == "strike" else ~reached).reshape(slots, per).float().mean(dim=1)
        rates = wins.tolist()
        if not all(math.isfinite(r) for r in rates) or not bool(torch.isfinite(state.game.pos).all()):
            raise RuntimeError("non-finite evaluation state")
        digits = self.method.rank_round_digits
        geometric = float(np.prod(rates) ** (1 / len(rates)))
        return {"update": active["update"], "win_rates": rates, "geometric_win_rate": geometric, "worst_win_rate": min(rates),
                "mean_win_rate": float(np.mean(rates)),
                "rank": [round(geometric, digits), round(min(rates), digits), round(float(np.mean(rates)), digits)],
                "games_per_opponent": per}

    def _select(self) -> None:
        active = self.state["active"]
        result = self.evaluate()
        active["evaluations"].append(result)
        if active["best_rank"] is None or tuple(result["rank"]) > tuple(active["best_rank"]):
            active["best_rank"], active["best_update"], active["best_ema"] = result["rank"], active["update"], list(active["ema"])
            folder = self.run_dir / "generations" / f"{active['generation']:04d}_{active['team']}"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / "best_actor_latest.pt"
            torch.save(copy.deepcopy(self.learner.actor.state_dict()), path)
            active["best_actor"] = str(path)

    def _finish(self) -> None:
        active = self.state["active"]
        folder = self.run_dir / "archive" / f"{active['generation']:04d}_{active['team']}"
        folder.mkdir(parents=True, exist_ok=True)
        torch.save(torch.load(active["best_actor"], weights_only=True), folder / "actor.pt")
        entry = {"generation": active["generation"], "team": active["team"], "path": str(folder), "best_update": active["best_update"],
                 "best_rank": active["best_rank"], "opponent_generations": [e["generation"] for e in active["opponents"]],
                 "training_win_rate_ema": active["best_ema"], "evaluations": active["evaluations"], "games_per_update": active["games"]}
        _write_json(folder / "metadata.json", entry)
        self.state["archive"].append({k: entry[k] for k in ("generation", "team", "path", "best_update")})
        self.state["active"] = None
        self._save()
        self.learner = self.pool = None

    def run(self, max_updates: int | None = None) -> list[dict[str, Any]]:
        """Run every generation; ``max_updates`` stops (with a checkpoint) after that many updates of this call. Returns the archive."""
        done = 0
        while len(self.state["archive"]) < self.generations:
            if self.learner is None:
                self._start()
            active = self.state["active"]
            while active["update"] < self.updates:
                if max_updates is not None and done >= max_updates:
                    self._checkpoint()
                    return self.state["archive"]
                self._update()
                done += 1
                if active["update"] in self.selection_after:
                    self._select()
                    self._checkpoint()
            self._finish()
        return self.state["archive"]
