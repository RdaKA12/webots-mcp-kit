from __future__ import annotations

from pathlib import Path

from webots_mcp_kit.monsterborg_adapter import (
    build_monsterborg_physical_bundle,
    verify_monsterborg_physical_environment,
)
from webots_mcp_kit.scenario_ops import replay_session


def test_verify_monsterborg_physical_environment_shape() -> None:
    payload = verify_monsterborg_physical_environment(camera_required=False)
    assert payload["robot_family"] == "monsterborg"
    assert payload["robot_profile"] == "monsterborg-4wd"
    assert payload["runtime_target"] == "monsterborg-physical"
    assert set(payload["module_status"]) == {"ThunderBorg3", "picamera2", "smbus2"}


def test_build_monsterborg_physical_bundle_is_replay_compatible(tmp_path: Path) -> None:
    samples = [
        {
            "state": {"robot_time": 0.0, "step_index": 0},
            "sensors": {"front_range": 410.0, "heading": 0.0, "yaw_rate": 0.0, "left_encoder": 0.0, "right_encoder": 0.0},
            "metrics": {"obstacle_pressure": 0.4, "mean_forward_speed": 2.5},
            "actuators": {"left_velocity": 2.5, "right_velocity": 2.5},
        },
        {
            "state": {"robot_time": 1.2, "step_index": 38},
            "sensors": {"front_range": 360.0, "heading": 0.02, "yaw_rate": 0.03, "left_encoder": 1.1, "right_encoder": 1.1},
            "metrics": {"obstacle_pressure": 0.35, "mean_forward_speed": 2.8},
            "actuators": {"left_velocity": 2.8, "right_velocity": 2.8},
        },
    ]

    bundle = build_monsterborg_physical_bundle(
        output_dir=tmp_path / "physical-export",
        scenario="obstacle-avoidance",
        robot_name="monsterborg-physical",
        samples=samples,
        benchmark_name="obstacle-avoidance",
        benchmark_report={"benchmark": "obstacle-avoidance", "pass": True, "controller_fix_hints": []},
    )
    assert bundle["runtime_target"] == "monsterborg-physical"
    assert (tmp_path / "physical-export" / "export.json").exists()

    replay = replay_session(tmp_path / "physical-export")
    assert replay["runtime_environment"]["runtime_target"] == "monsterborg-physical"
    assert replay["benchmark_summary"]["benchmark_name"] == "obstacle-avoidance"
