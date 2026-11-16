"""scripts/_isaac_app.start_headless: headless by default, --windowed only on request (screenshots, owner's approval
16 Nov 2026). CPU only: Isaac Lab's launcher is replaced by a fake in sys.modules, so nothing starts."""
import argparse
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def launcher(monkeypatch):
    started = []

    class FakeAppLauncher:
        def __init__(self, args):
            started.append(args)
            self.app = "app"

        @staticmethod
        def add_app_launcher_args(parser):
            parser.add_argument("--headless", action="store_true")
            parser.add_argument("--enable_cameras", action="store_true")

    mod = types.ModuleType("isaaclab.app")
    mod.AppLauncher = FakeAppLauncher
    monkeypatch.setitem(sys.modules, "isaaclab", types.ModuleType("isaaclab"))
    monkeypatch.setitem(sys.modules, "isaaclab.app", mod)
    sys.modules.pop("_isaac_app", None)
    import _isaac_app
    return _isaac_app, started


def _start(mod, monkeypatch, argv, cameras=False):
    monkeypatch.setattr(sys, "argv", ["x", *argv])
    return mod.start_headless(argparse.ArgumentParser(), cameras=cameras)


def test_no_flag_is_refused(launcher, monkeypatch):
    mod, started = launcher
    with pytest.raises(SystemExit) as e:
        _start(mod, monkeypatch, [])
    assert e.value.code == 2 and started == []


def test_headless_starts_without_window(launcher, monkeypatch):
    mod, started = launcher
    args, app = _start(mod, monkeypatch, ["--headless"], cameras=True)
    assert app == "app" and args.headless and not args.windowed and args.enable_cameras and len(started) == 1


def test_windowed_starts_with_window(launcher, monkeypatch):
    mod, started = launcher
    args, app = _start(mod, monkeypatch, ["--windowed"])
    assert app == "app" and args.windowed and not args.headless and len(started) == 1


def test_headless_and_windowed_together_is_refused(launcher, monkeypatch):
    mod, started = launcher
    with pytest.raises(SystemExit) as e:
        _start(mod, monkeypatch, ["--headless", "--windowed"])
    assert e.value.code == 2 and started == []
