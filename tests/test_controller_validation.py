from __future__ import annotations

from pathlib import Path

from webots_mcp_kit.controller_validation import validate_controller


def test_validate_example_controller() -> None:
    path = Path(__file__).resolve().parents[1] / "examples" / "line-follower" / "controllers" / "line_follower_agent.py"
    result = validate_controller(path)
    assert result.valid is True
    assert result.integration_mode == "toolkit-agent"
