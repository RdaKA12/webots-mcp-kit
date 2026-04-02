from __future__ import annotations

from webots_mcp_kit.agent import ControllerAgent
from webots_mcp_kit.gate import build_v1_gate_steps


def test_controller_agent_public_surface_is_stable() -> None:
    assert hasattr(ControllerAgent, "from_robot")
    assert hasattr(ControllerAgent, "begin_step")
    assert hasattr(ControllerAgent, "report_step")


def test_v1_gate_includes_real_runtime_flow(tmp_path) -> None:
    steps = build_v1_gate_steps(tmp_path / "v1-gate")
    names = [step.name for step in steps]
    assert "bundled_benchmark_line" in names
    assert "bundled_benchmark_obstacle" in names
    assert "bundled_benchmark_waypoint" in names
    assert "generated_line_session_start" in names
    assert "generated_waypoint_session_start" in names
    assert "generated_obstacle_session_start" in names
    assert "generated_line_benchmark_run" in names
    assert "generated_waypoint_benchmark_run" in names
    assert "generated_obstacle_benchmark_run" in names
    assert "imported_session_export" in names
    assert "imported_session_replay_manifest" in names
