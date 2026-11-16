"""A saved stand-in (``scripts/train_standin.py``) behind the strategy contract (S2 Task 10, built in S2b Task 9).

The stand-in is a pipe test: it proves that the game, the skrl adapter, training, saving, loading and scoring
connect. It is never "the policy" and never a strategy of record.

A run folder holds ``agent.pt`` (skrl's ``agent.save``: per Guard name the policy, the value network, the optimiser
and the two ``RunningStandardScaler`` preprocessors) and ``interface.toml`` (STANDARDS §3 rule 1). The networks are
built here, once, for both the trainer and the loader, so the two can never drift apart.

``SkrlPolicyStrategy`` loads a run folder as a Guard ``Strategy``: Guard drone k is played by network ``guard_k`` on
its own observation (decentralised execution, STANDARDS §3 rule 2), after the saved observation scaler (applied
without updating it). One network per Guard slot, so it refuses a Guard team size other than the one trained.

This module imports skrl; ``opponents/__init__.py`` and ``opponents/scripted.py`` import it only when a run folder
is asked for, so the scripted opponents still import no training library."""
from __future__ import annotations

import tomllib
from pathlib import Path

import gymnasium
import torch
from skrl.models.torch import DeterministicMixin, GaussianMixin, Model
from skrl.resources.preprocessors.torch import RunningStandardScaler
from torch import Tensor

from ..core.observations import INTERFACE_VERSION, OBS_DIM

ACT_DIM = 4
OBS_SPACE = gymnasium.spaces.Box(-float("inf"), float("inf"), (OBS_DIM,), "float32")
ACT_SPACE = gymnasium.spaces.Box(-1.0, 1.0, (ACT_DIM,), "float32")
INTERFACE_FILE = "interface.toml"
AGENT_FILE = "agent.pt"


def _mlp(sizes: list[int], out: int) -> torch.nn.Sequential:
    """Linear + ELU for every hidden size, then a linear output layer."""
    layers: list[torch.nn.Module] = []
    width = OBS_DIM
    for h in sizes:
        layers += [torch.nn.Linear(width, h), torch.nn.ELU()]
        width = h
    layers.append(torch.nn.Linear(width, out))
    return torch.nn.Sequential(*layers)


class StandinPolicy(GaussianMixin, Model):
    """Gaussian policy: obs [B, OBS_DIM] (already scaled) -> mean action [B, 4], one learned log std per axis."""

    def __init__(self, hidden: list[int], device) -> None:
        Model.__init__(self, observation_space=OBS_SPACE, action_space=ACT_SPACE, device=device)
        GaussianMixin.__init__(self, clip_actions=True)
        self.net = _mlp(list(hidden), ACT_DIM)
        self.log_std = torch.nn.Parameter(torch.zeros(ACT_DIM))

    def compute(self, inputs, role=""):
        return self.net(inputs["observations"]), {"log_std": self.log_std}


class StandinValue(DeterministicMixin, Model):
    """Value network: obs [B, OBS_DIM] (already scaled) -> value [B, 1] (in the value scaler's units)."""

    def __init__(self, hidden: list[int], device) -> None:
        Model.__init__(self, observation_space=OBS_SPACE, action_space=ACT_SPACE, device=device)
        DeterministicMixin.__init__(self)
        self.net = _mlp(list(hidden), 1)

    def compute(self, inputs, role=""):
        return self.net(inputs["observations"]), {}


def make_models(names: list[str], hidden: list[int], device) -> dict[str, dict[str, Model]]:
    """{agent name: {"policy": StandinPolicy, "value": StandinValue}}: separate networks per name (IPPO)."""
    return {a: {"policy": StandinPolicy(hidden, device).to(device), "value": StandinValue(hidden, device).to(device)}
            for a in names}


def read_interface(run_dir: str | Path) -> dict:
    """The run folder's interface.toml as a dict (FileNotFoundError if the folder holds none)."""
    p = Path(run_dir) / INTERFACE_FILE
    if not p.is_file():
        raise FileNotFoundError(f"{run_dir}: no {INTERFACE_FILE} (not a stand-in run folder)")
    return tomllib.loads(p.read_text())


def is_run_folder(spec: str) -> bool:
    """True if ``spec`` names a folder holding an interface.toml (make_strategy's run-folder form)."""
    p = Path(spec)
    return p.is_dir() and (p / INTERFACE_FILE).is_file()


class SkrlPolicyStrategy:
    """A saved stand-in as a Guard strategy (module docstring).

    run_dir: the training run folder (interface.toml + agent.pt). num_games: N. device: where to run.
    deterministic: True plays each network's mean action (scoring); False samples from its Gaussian with the
    saved log std (``seed`` seeds that draw). ``team`` = "guard"; ``name`` = "standin:<run folder name>"."""

    team = "guard"

    def __init__(self, run_dir: str | Path, num_games: int, device, deterministic: bool = True,
                 seed: int = 0) -> None:
        self.run_dir = Path(run_dir)
        self.meta = read_interface(self.run_dir)
        if self.meta.get("interface_version") != INTERFACE_VERSION:
            raise ValueError(f"{self.run_dir.name}: trained on observation interface "
                             f"{self.meta.get('interface_version')!r}; this game serves {INTERFACE_VERSION!r}")
        if self.meta.get("team") != "guard":
            raise ValueError(f"{self.run_dir.name}: trained for team {self.meta.get('team')!r}, not 'guard'")
        self.guards = int(self.meta["guards"])
        self.agents = [f"guard_{k}" for k in range(self.guards)]
        self.name = f"standin:{self.run_dir.name}"
        self.num_games = num_games
        self.device = torch.device(device)
        self.deterministic = deterministic
        self._gen = torch.Generator(device=self.device)
        self._gen.manual_seed(seed)
        saved = torch.load(self.run_dir / AGENT_FILE, map_location=self.device, weights_only=False)
        hidden = list(self.meta["network"]["hidden"])
        self.policies: list[StandinPolicy] = []
        self.scalers: list[RunningStandardScaler] = []
        for a in self.agents:
            if a not in saved:
                raise ValueError(f"{self.run_dir.name}: {AGENT_FILE} has no network for {a!r}")
            pol = StandinPolicy(hidden, self.device).to(self.device)
            pol.load_state_dict(saved[a]["policy"])
            pol.eval()
            sc = RunningStandardScaler(OBS_SPACE, device=self.device)
            sc.load_state_dict(saved[a]["observation_preprocessor"])
            sc.eval()
            self.policies.append(pol)
            self.scalers.append(sc)

    def reset(self, games: Tensor) -> None:
        """Stateless networks: nothing to clear. games [N] bool."""

    def act(self, obs: Tensor) -> Tensor:
        """obs [N, G, OBS_DIM] -> actions [N, G, 4] in [-1, 1]. Raises ValueError if G is not the trained size."""
        if obs.shape[1] != self.guards:
            raise ValueError(f"{self.name}: trained for {self.guards} Guard drones (one network per slot), got "
                             f"{obs.shape[1]}; score it at {self.guards}vS only")
        out = []
        with torch.no_grad():
            for k, (pol, sc) in enumerate(zip(self.policies, self.scalers)):
                mean = pol.net(sc(obs[:, k], train=False))
                if not self.deterministic:
                    std = pol.log_std.clamp(-20.0, 2.0).exp()
                    mean = mean + std * torch.randn(mean.shape, generator=self._gen, device=mean.device)
                out.append(mean.clamp(-1.0, 1.0))
        return torch.stack(out, dim=1).to(obs.dtype)
