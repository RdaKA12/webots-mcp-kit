from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import webots_mcp_kit


def test_package_version_matches_module_version() -> None:
    root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == webots_mcp_kit.__version__


def test_cli_version_matches_module_version() -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    result = subprocess.run(
        [sys.executable, "-m", "webots_mcp_kit.cli", "--version"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=root,
    )
    assert result.stdout.strip() == f"webots-mcp-kit {webots_mcp_kit.__version__}"
