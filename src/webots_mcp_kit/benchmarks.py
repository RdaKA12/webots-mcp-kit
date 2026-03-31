from __future__ import annotations

from pathlib import Path

from .models import ScenarioDefinition, bundled_example_root


def _examples_root() -> Path:
    return bundled_example_root()


def scenario_registry() -> dict[str, ScenarioDefinition]:
    root = _examples_root()
    return {
        "line-follower": ScenarioDefinition(
            name="line-follower",
            description="Follow a high-contrast floor line with a camera-based controller.",
            world=root / "line-follower" / "worlds" / "line_follower_benchmark.wbt",
            controller=root / "line-follower" / "controllers" / "line_follower_agent.py",
            target_robot_name="epuck-line-follower",
            target_robot_def="EPUCK",
            benchmark_kind="line-follower",
            default_camera="camera",
            required_sensor_keys=("camera_left_band", "camera_center_band", "camera_right_band"),
            required_metric_keys=("line_visible", "center_error", "ir_balance_error"),
            required_actuator_keys=("left_velocity", "right_velocity"),
            benchmark_thresholds={"line_loss_streak_fail": 25},
        ),
        "obstacle-avoidance": ScenarioDefinition(
            name="obstacle-avoidance",
            description="Avoid arena obstacles using the e-puck proximity sensors.",
            world=root / "obstacle-avoidance" / "worlds" / "obstacle_avoidance_benchmark.wbt",
            controller=root / "obstacle-avoidance" / "controllers" / "obstacle_avoidance_agent.py",
            target_robot_name="epuck-obstacle-agent",
            target_robot_def="EPUCK",
            benchmark_kind="obstacle-avoidance",
            default_camera="camera",
            required_sensor_keys=("ps0", "ps1", "ps2", "ps3", "ps4", "ps5", "ps6", "ps7"),
            required_metric_keys=("line_visible", "center_error", "ir_balance_error", "obstacle_pressure", "mean_forward_speed"),
            required_actuator_keys=("left_velocity", "right_velocity"),
            benchmark_thresholds={
                "max_collision_events": 0,
                "min_travelled_distance": 0.15,
                "min_mean_forward_speed": 0.5,
            },
        ),
        "waypoint-nav": ScenarioDefinition(
            name="waypoint-nav",
            description="Drive toward a fixed waypoint in an open arena while exposing telemetry through ControllerAgent.",
            world=root / "waypoint-nav" / "worlds" / "waypoint_nav_benchmark.wbt",
            controller=root / "waypoint-nav" / "controllers" / "waypoint_nav_agent.py",
            target_robot_name="epuck-waypoint-agent",
            target_robot_def="EPUCK",
            benchmark_kind="waypoint-nav",
            default_camera="camera",
            required_sensor_keys=("ps0", "ps1", "ps2", "ps3", "ps4", "ps5", "ps6", "ps7"),
            required_metric_keys=("line_visible", "center_error", "ir_balance_error", "obstacle_pressure", "mean_forward_speed"),
            required_actuator_keys=("left_velocity", "right_velocity"),
            benchmark_thresholds={
                "target_position": (0.55, 0.0),
                "target_tolerance": 0.16,
                "max_collision_events": 0,
                "min_travelled_distance": 0.8,
                "min_mean_forward_speed": 1.0,
            },
        ),
    }


def get_scenario(name: str) -> ScenarioDefinition:
    registry = scenario_registry()
    if name not in registry:
        available = ", ".join(sorted(registry))
        raise KeyError(f"Unknown scenario '{name}'. Available scenarios: {available}")
    return registry[name]


def scenario_names() -> list[str]:
    return sorted(scenario_registry())
