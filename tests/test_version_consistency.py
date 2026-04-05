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


def test_monsterborg_docs_use_current_release_language() -> None:
    root = Path(__file__).resolve().parents[1]
    current_release = "v2.8.0"
    release_docs = [
        root / "README.md",
        root / "docs" / "controller-authoring-and-editing.md",
        root / "docs" / "world-authoring-and-editing.md",
        root / "docs" / "mcp-contracts.md",
        root / "docs" / "project-import-and-replay.md",
        root / "docs" / "zero-to-sim.md",
    ]
    for path in release_docs:
        content = path.read_text(encoding="utf-8")
        if "monsterborg" not in content.lower():
            continue
        assert "v2.2.0" not in content, path
        assert "v2.3.0-alpha.1" not in content, path
        assert "v2.5.0" not in content, path
        assert "feature/monsterborg-support" not in content, path
        assert current_release in content or "monsterborg" in content.lower(), path
