from __future__ import annotations

from webots_mcp_kit.agent import ControllerAgent


def test_controller_agent_public_surface_is_stable() -> None:
    assert hasattr(ControllerAgent, "from_robot")
    assert hasattr(ControllerAgent, "begin_step")
    assert hasattr(ControllerAgent, "report_step")
