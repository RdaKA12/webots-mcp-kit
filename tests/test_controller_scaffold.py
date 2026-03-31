from __future__ import annotations

from pathlib import Path

from webots_mcp_kit.controller_scaffold import scaffold_controller
from webots_mcp_kit.controller_validation import validate_controller


def test_scaffold_controller_creates_valid_file(tmp_path: Path) -> None:
    target = tmp_path / "generated_line_follower.py"
    payload = scaffold_controller(path=target, scenario="line-follower")
    assert payload["scenario"] == "line-follower"
    assert target.exists()

    result = validate_controller(target, scenario="line-follower", strict=True)
    assert result.valid is True
