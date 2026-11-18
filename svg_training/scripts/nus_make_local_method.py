"""Write the git-ignored local method file (NUS port Phase 5, task M1; G1): the partner's self-play, PPO and reward settings from a
reference run's resolved ``config.json``, plus the constants that sit in the partner's learner code (parsed from the clone with ``ast``;
nothing is imported, nothing is copied).

    python scripts/nus_make_local_method.py --run-config <partner run folder or its config.json> --clone <partner clone> \
        --out configs/local/nus_method.toml

``--out`` must lie under configs/local/ (refused otherwise). The script refuses a run whose method this port does not copy: APEX on, a
learning-rate schedule other than constant, per-slot advantage normalisation, no permanent scripted slot or a scripted controller other
than APF, a non-deterministic selection mode, an initial archive, or a critic state with other fields than the port builds.

It prints the output path, the key names and the sha256 of the file, never a value.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from svg_training.nus.method_cfg import METHOD_KEYS, STRING_KEYS, load_method  # noqa: E402
from svg_training.nus.rules import ROOT, file_sha256  # noqa: E402

LOCAL_OUT_DIR = ROOT / "configs" / "local"  # the only folder a method file may be written to (git-ignored); tests patch it
TEAM_OF = {"defender": "guard", "attacker": "strike"}
# the critic-state fields the port builds, in the order the port builds them (nus/replica_train.py CENTRAL_FIELDS)
EXPECTED_STATE_FIELDS = ("p_pos", "done", "step", "area_pos", "prev_p_pos", "agent_spawn_center", "adversary_spawn_center", "breach")
SCRIPTED = "apf"


# ------------------------------------------------------------------------------------------------ the run's config.json
def _get(cfg: dict[str, Any], dotted: str) -> Any:
    node: Any = cfg
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"run config has no '{dotted}'")
        node = node[part]
    return node


def refuse_unsupported(cfg: dict[str, Any]) -> None:
    """Refuse a run whose method the port does not copy (keys named, values never)."""
    problems = []
    if (cfg.get("apex") or {}).get("enabled") or (_get(cfg, "self_play").get("apex") or {}).get("enabled"):
        problems.append("apex.enabled")
    if str((_get(cfg, "trainer").get("lr_schedule") or {}).get("kind", "constant")) != "constant":
        problems.append("trainer.lr_schedule.kind")
    if bool(_get(cfg, "trainer").get("per_slot_advantage_norm", False)):
        problems.append("trainer.per_slot_advantage_norm")
    if not bool(cfg.get("include_apf_in_pool")):
        problems.append("include_apf_in_pool")
    if str(cfg.get("scripted_opponent") or SCRIPTED) != SCRIPTED:
        problems.append("scripted_opponent")
    for team, kind in (_get(cfg, "self_play").get("scripted_opponents") or {}).items():
        if kind not in (None, SCRIPTED):
            problems.append(f"self_play.scripted_opponents.{team}")
    if str(cfg.get("selection_action_mode", "deterministic")) != "deterministic":
        problems.append("selection_action_mode")
    if _get(cfg, "self_play").get("initial_archive"):
        problems.append("self_play.initial_archive")
    if tuple(_get(cfg, "environment.env.global_state_fields")) != EXPECTED_STATE_FIELDS:
        problems.append("environment.env.global_state_fields")
    if str(cfg.get("train_team")) not in TEAM_OF:
        problems.append("train_team")
    if problems:
        raise SystemExit(f"refusing: the port does not copy this run's method (keys: {problems})")


def from_run_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Every method value that the resolved run configuration holds."""
    refuse_unsupported(cfg)
    s, t, p = "self_play.", "trainer.", "trainer.policy."
    out: dict[str, Any] = {
        "first_team": TEAM_OF[str(cfg["train_team"])],
        "generations": int(_get(cfg, s + "generations")),
        "updates_per_generation": int(_get(cfg, s + "updates_per_generation")),
        "max_learned_opponents": int(_get(cfg, s + "max_learned_opponents")),
        "recent_opponents": int(_get(cfg, s + "recent_opponents")),
        "episodes_per_opponent": int(_get(cfg, s + "episodes_per_opponent")),
        "minimum_rollout_batch": int(_get(cfg, s + "minimum_rollout_batch")),
        "win_rate_ema": float(_get(cfg, s + "training_win_rate_ema")),
        "selection_interval_updates": int(_get(cfg, s + "evaluation.interval_updates")),
        "selection_games_per_opponent": int(_get(cfg, s + "evaluation.episodes_per_opponent")),
        "max_pool_slots": int(_get(cfg, t + "max_pool_slots")),
        "hidden_dim": int(_get(cfg, p + "hidden_dim")),
        "hidden_blocks": int(_get(cfg, p + "n_hidden_layers")),
        "activation": str(_get(cfg, p + "activation_type")),
        "use_layernorm": bool(_get(cfg, p + "use_layernorm")),
        "compute_dtype": str(_get(cfg, "jax.compute_dtype")),
        "initial_log_std": float(_get(cfg, p + "initial_log_std")),
        "zero_init_output": bool(_get(cfg, p + "zero_init_output")),
        "ppo_epochs": int(_get(cfg, t + "ppo_epochs")),
        "ppo_minibatches": int(_get(cfg, t + "ppo_num_mini_batch")),
        "ppo_clip": float(_get(cfg, t + "ppo_clip")),
        "entropy_coef": float(_get(cfg, t + "entropy_coef")),
        "critic_loss_coef": float(_get(cfg, t + "critic_loss_coef")),
        "max_grad_norm": float(_get(cfg, t + "max_grad_norm")),
        "shaping_scale": float(_get(cfg, t + "rewards.defender.attacker_distance_scale")),
        "inside_penalty": float(_get(cfg, t + "rewards.defender.breach_penalty")),
        "clean_timeout_reward": float(_get(cfg, t + "rewards.defender.clean_timeout_reward")),
        "first_reach_penalty": float(_get(cfg, t + "rewards.defender").get("first_breach_penalty", 0)),
    }
    for partner, team in TEAM_OF.items():
        block = _get(cfg, t + partner)
        out |= {f"{team}_actor_lr": float(block["actor_lr"]), f"{team}_critic_lr": float(block["critic_lr"]),
                f"{team}_gamma": float(block["task_gamma"]), f"{team}_gae_lambda": float(block["task_gae_lambda"]),
                f"{team}_advantage_weight": float(block["task_advantage_weight"])}
    return out


# ------------------------------------------------------------------------------------------------ constants in the partner's code
def _number(node: ast.AST) -> float:
    """A literal number, possibly negated; anything else is refused."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_number(node.operand)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    raise LookupError("expected a literal number in the partner source")


def _named(tree: ast.AST, kind: type, name: str) -> ast.AST:
    found = [n for n in ast.walk(tree) if isinstance(n, kind) and getattr(n, "name", None) == name]
    if len(found) != 1:
        raise LookupError(f"expected one {kind.__name__} '{name}' in the partner source, found {len(found)}")
    return found[0]


def _calls(node: ast.AST, attr: str) -> list[ast.Call]:
    """Calls whose function is ``<something>.<attr>`` or the bare name ``attr``."""
    return [c for c in ast.walk(node) if isinstance(c, ast.Call)
            and (getattr(c.func, "attr", None) == attr or getattr(c.func, "id", None) == attr)]


def _one(values: list[float], what: str) -> float:
    distinct = set(values)
    if len(distinct) != 1:
        raise LookupError(f"expected exactly one {what} in the partner source, found {len(distinct)}; read it and update this script")
    return distinct.pop()


def read_learner_constants(clone: Path | str) -> dict[str, Any]:
    """Constants of the partner's learner that no config holds, by file (cited in the plan, section 4.1):

    * ``ma_skills/jax/policy.py`` ``TeamActor``: the log-std clip bounds (class defaults) and the orthogonal gain of the output layer;
    * ``ma_skills/jax/nn.py`` ``trunc_normal_in``: the fan-in scale and the truncation of the initialiser;
    * ``ma_skills/jax/training.py``: the variance epsilon and the clip of the advantage normalisation (``_masked_normalize``) and the
      log-ratio clip (``actor_loss``);
    * ``ma_skills/runner/fixed_opponent_runner.py`` ``_optimizer``: the weight decay;
    * ``ma_skills/runner/ensemble_self_play_runner.py`` ``_evaluate``: the rounding of the selection rank.
    """
    clone = Path(clone)
    jax_dir, runner_dir = clone / "ma_skills" / "jax", clone / "ma_skills" / "runner"
    actor = _named(ast.parse((jax_dir / "policy.py").read_text()), ast.ClassDef, "TeamActor")
    defaults = {n.target.id: _number(n.value) for n in actor.body
                if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None
                and n.target.id in ("log_std_min", "log_std_max")}
    if set(defaults) != {"log_std_min", "log_std_max"}:
        raise LookupError("TeamActor log-std bounds not found; read policy.py and update this script")
    gain = _one([_number(c.args[0]) for c in _calls(actor, "orthogonal")], "orthogonal gain in TeamActor")

    init = _named(ast.parse((jax_dir / "nn.py").read_text()), ast.FunctionDef, "trunc_normal_in")
    scale = _one([_number(n.left) for n in ast.walk(init) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)
                  and isinstance(n.left, (ast.Constant, ast.UnaryOp))], "fan-in scale in trunc_normal_in")
    bounds = [(_number(c.args[1]), _number(c.args[2])) for c in _calls(init, "truncated_normal")]
    if len(bounds) != 1 or bounds[0][0] != -bounds[0][1]:
        raise LookupError("trunc_normal_in truncation not found or not symmetric; read nn.py and update this script")

    training = ast.parse((jax_dir / "training.py").read_text())
    normalise = _named(training, ast.FunctionDef, "_masked_normalize")
    epsilon = _one([_number(n.right) for s in _calls(normalise, "sqrt") for n in ast.walk(s)
                    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add)], "variance epsilon in _masked_normalize")

    def literal(node: ast.AST) -> float | None:
        try:
            return _number(node)
        except LookupError:
            return None

    def symmetric_clip(func: ast.AST, what: str) -> float:
        """The bound of the one ``clip(x, -c, c)`` with literal bounds (clips with computed bounds are skipped)."""
        pairs = [(literal(c.args[1]), literal(c.args[2])) for c in _calls(func, "clip") if len(c.args) == 2 + 1]
        return _one([hi for lo, hi in pairs if lo is not None and hi is not None and lo == -hi], what)

    advantage_clip = symmetric_clip(normalise, "advantage clip in _masked_normalize")
    log_ratio_clip = symmetric_clip(_named(training, ast.FunctionDef, "actor_loss"), "log-ratio clip in actor_loss")

    optimiser = _named(ast.parse((runner_dir / "fixed_opponent_runner.py").read_text()), ast.FunctionDef, "_optimizer")
    decay = _one([_number(k.value) for c in _calls(optimiser, "adamw") for k in c.keywords if k.arg == "weight_decay"],
                 "weight decay in _optimizer")

    evaluate = _named(ast.parse((runner_dir / "ensemble_self_play_runner.py").read_text()), ast.FunctionDef, "_evaluate")
    digits = _one([_number(c.args[1]) for c in _calls(evaluate, "round") if len(c.args) == 2], "rank rounding in _evaluate")

    return {"log_std_min": float(defaults["log_std_min"]), "log_std_max": float(defaults["log_std_max"]),
            "output_init_gain": float(gain), "init_std_scale": float(scale), "init_truncation": float(bounds[0][1]),
            "advantage_epsilon": float(epsilon), "advantage_clip": float(advantage_clip), "log_ratio_clip": float(log_ratio_clip),
            "weight_decay": float(decay), "rank_round_digits": int(digits)}


# ------------------------------------------------------------------------------------------------ writing
def build_method(run_config: Path, clone: Path) -> dict[str, Any]:
    config = run_config / "config.json" if run_config.is_dir() else run_config
    values = from_run_config(json.loads(config.read_text())) | read_learner_constants(clone)
    missing = [k for k in METHOD_KEYS if k not in values]
    if missing:
        raise KeyError(f"method keys without a source: {missing}")
    return values


def write_method_file(path: Path, values: dict[str, Any]) -> None:
    lines = ["# Local training-method values of the partner (NUS). Git-ignored. Written by scripts/nus_make_local_method.py; "
             "never copy into a tracked file."]
    for key in METHOD_KEYS:
        v = values[key]
        lines.append(f'{key} = "{v}"' if key in STRING_KEYS else f"{key} = {str(v).lower() if isinstance(v, bool) else repr(v)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-config", required=True, type=Path, help="the reference run's folder or its resolved config.json")
    parser.add_argument("--clone", required=True, type=Path, help="the partner's code folder (read only)")
    parser.add_argument("--out", required=True, type=Path, help="must lie under configs/local/")
    args = parser.parse_args(argv)
    out_dir = LOCAL_OUT_DIR.resolve()
    if out_dir not in (args.out.resolve(), *args.out.resolve().parents):
        raise SystemExit(f"refusing: --out must lie under {out_dir} (the git-ignored local folder)")
    values = build_method(args.run_config, args.clone)
    write_method_file(args.out, values)
    load_method(args.out)  # refuses an inconsistent file
    print(f"wrote {args.out}")
    print(f"keys: {', '.join(METHOD_KEYS)}")
    print(f"sha256: {file_sha256(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
