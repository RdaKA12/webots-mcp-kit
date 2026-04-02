from __future__ import annotations

import tomllib
from pathlib import Path

import webots_mcp_kit


def test_package_version_matches_module_version() -> None:
    root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == webots_mcp_kit.__version__
