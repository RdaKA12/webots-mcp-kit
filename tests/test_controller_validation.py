from __future__ import annotations

from pathlib import Path

from webots_mcp_kit.controller_validation import validate_controller


def test_validate_example_controller_strict() -> None:
    path = Path(__file__).resolve().parents[1] / "examples" / "line-follower" / "controllers" / "line_follower_agent.py"
    result = validate_controller(path, scenario="line-follower", strict=True)
    assert result.valid is True
    assert result.integration_mode == "controller-agent"
    assert result.details["default_camera"] == "camera"
    assert result.details["function_inventory"]
    assert result.details["compile_readiness"]["supported"] is False
    assert result.details["runtime_readiness"]["ready"] is True
    assert result.status == "ready"
    assert result.summary["error_count"] == 0


def test_validate_missing_begin_step_is_invalid(tmp_path: Path) -> None:
    controller = tmp_path / "broken_controller.py"
    controller.write_text(
        """
from controller import Robot
from webots_mcp_kit.agent import ControllerAgent

robot = Robot()
agent = ControllerAgent.from_robot(robot, default_camera="camera")

while robot.step(int(robot.getBasicTimeStep())) != -1:
    agent.report_step(
        sensors={"camera_left_band": 0.0, "camera_center_band": 0.0, "camera_right_band": 0.0},
        metrics={"line_visible": True, "center_error": 0.0, "ir_balance_error": 0.0},
        actuators={"left_velocity": 0.0, "right_velocity": 0.0},
        camera_frames={},
    )
""".strip(),
        encoding="utf-8",
    )
    result = validate_controller(controller, scenario="line-follower", strict=True)
    assert result.valid is False
    assert result.status == "misconfigured"
    assert any("begin_step" in error for error in result.errors)


def test_validate_plain_webots_controller_is_invalid(tmp_path: Path) -> None:
    controller = tmp_path / "plain_controller.py"
    controller.write_text(
        """
from controller import Robot

robot = Robot()

while robot.step(int(robot.getBasicTimeStep())) != -1:
    pass
""".strip(),
        encoding="utf-8",
    )
    result = validate_controller(controller)
    assert result.valid is False
    assert result.status == "misconfigured"
    assert result.integration_mode == "plain-webots"


def test_validate_non_literal_metrics_warns_without_strict(tmp_path: Path) -> None:
    controller = tmp_path / "non_literal_controller.py"
    controller.write_text(
        """
from controller import Robot
from webots_mcp_kit.agent import ControllerAgent

robot = Robot()
agent = ControllerAgent.from_robot(robot, default_camera="camera")

while robot.step(int(robot.getBasicTimeStep())) != -1:
    metrics = {"line_visible": True, "center_error": 0.0, "ir_balance_error": 0.0}
    sensors = {"camera_left_band": 0.0, "camera_center_band": 0.0, "camera_right_band": 0.0}
    actuators = {"left_velocity": 0.0, "right_velocity": 0.0}
    agent.begin_step()
    agent.report_step(sensors=sensors, metrics=metrics, actuators=actuators, camera_frames={})
""".strip(),
        encoding="utf-8",
    )
    result = validate_controller(controller, scenario="line-follower", strict=False)
    assert result.valid is True
    assert result.status == "ready"
    assert result.warnings
    assert result.details["benchmark_contract_gaps"]
    assert result.details["controller_fix_hints"]
