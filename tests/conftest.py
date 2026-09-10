"""Shared pytest fixtures for passist tests.

We isolate state by pointing `PROMPTASSIST_DATA_DIR` at a temp dir,
so tests never touch the real `%LOCALAPPDATA%` / `~/.config/promptassist`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def data_dir(tmp_path: Path):
    d = tmp_path / "datadir"
    d.mkdir()
    os.environ["PROMPTASSIST_DATA_DIR"] = str(d)
    yield d
    os.environ.pop("PROMPTASSIST_DATA_DIR", None)


@pytest.fixture
def assets_dir():
    return REPO_ROOT / "passist" / "data"


@pytest.fixture
def cli_env(tmp_path: Path, assets_dir: Path) -> dict:
    env = dict(os.environ)
    env["PROMPTASSIST_DATA_DIR"] = str(tmp_path / "cli-data")
    env["PROMPTASSIST_ASSETS_DIR"] = str(assets_dir)
    (tmp_path / "cli-data").mkdir(exist_ok=True)
    return env


@pytest.fixture
def python_exec() -> str:
    return sys.executable


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo-repo"
    repo.mkdir()
    return repo


def run_cli(args: list[str], env: dict, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run the CLI in a subprocess — isolates from the test process env."""
    cmd = [sys.executable, "-m", "passist", *args]
    return subprocess.run(
        cmd,
        env=env,
        cwd=cwd or os.getcwd(),
        capture_output=True,
        text=True,
        timeout=30,
    )
