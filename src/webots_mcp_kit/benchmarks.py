from __future__ import annotations

from pathlib import Path

from .models import ScenarioDefinition, bundled_example_root
from .robot_profiles import get_robot_profile, robot_profile_names


def _examples_root() -> Path:
    return bundled_example_root()


def scenario_registry(*, robot_profile: str | None = None) -> dict[str, ScenarioDefinition]:
    root = _examples_root()
    profile = get_robot_profile(robot_profile).robot_profile
    if profile == "monsterborg-4wd":
        return {
            "line-follower": ScenarioDefinition(
                name="line-follower",
                description="Follow a high-contrast floor line with the MonsterBorg front camera.",
                world=root / "monsterborg" / "line-follower" / "worlds" / "monsterborg_line_follower_benchmark.wbt",
                controller=root / "monsterborg" / "line-follower" / "controllers" / "monsterborg_line_follower_agent.py",
                target_robot_name="monsterborg-line-follower",
                target_robot_def="MONSTERBORG",
                robot_family="monsterborg",
                robot_profile="monsterborg-4wd",
                benchmark_kind="line-follower",
                default_camera="front_camera",
                required_sensor_keys=("camera_left_band", "camera_center_band", "camera_right_band"),
                required_metric_keys=("line_visible", "center_error", "ir_balance_error"),
                required_actuator_keys=("left_velocity", "right_velocity"),
                benchmark_thresholds={"line_loss_streak_fail": 30},
            ),
            "obstacle-avoidance": ScenarioDefinition(
                name="obstacle-avoidance",
                description="Avoid frontal obstacles with MonsterBorg range, IMU, and encoder telemetry.",
                world=root / "monsterborg" / "obstacle-avoidance" / "worlds" / "monsterborg_obstacle_avoidance_benchmark.wbt",
                controller=root / "monsterborg" / "obstacle-avoidance" / "controllers" / "monsterborg_obstacle_avoidance_agent.py",
                target_robot_name="monsterborg-obstacle-agent",
                target_robot_def="MONSTERBORG",
                robot_family="monsterborg",
                robot_profile="monsterborg-4wd",
                benchmark_kind="obstacle-avoidance",
                default_camera="front_camera",
                required_sensor_keys=("front_range", "heading", "yaw_rate", "left_encoder", "right_encoder"),
                required_metric_keys=(
                    "obstacle_pressure",
                    "mean_forward_speed",
                    "front_clearance_margin",
                    "clearance_violation",
                    "heading_recovery_events",
                    "stalled_steps",
                    "avoidance_state_code",
                ),
                required_actuator_keys=("left_velocity", "right_velocity"),
                benchmark_thresholds={
                    "max_collision_events": 1,
                    "min_travelled_distance": 0.25,
                    "min_mean_forward_speed": 1.0,
                },
            ),
            "waypoint-nav": ScenarioDefinition(
                name="waypoint-nav",
                description="Drive the MonsterBorg toward a fixed waypoint while exposing range, IMU, and encoder telemetry.",
                world=root / "monsterborg" / "waypoint-nav" / "worlds" / "monsterborg_waypoint_nav_benchmark.wbt",
                controller=root / "monsterborg" / "waypoint-nav" / "controllers" / "monsterborg_waypoint_nav_agent.py",
                target_robot_name="monsterborg-waypoint-agent",
                target_robot_def="MONSTERBORG",
                robot_family="monsterborg",
                robot_profile="monsterborg-4wd",
                benchmark_kind="waypoint-nav",
                default_camera="front_camera",
                required_sensor_keys=("front_range", "heading", "yaw_rate", "left_encoder", "right_encoder"),
                required_metric_keys=(
                    "obstacle_pressure",
                    "mean_forward_speed",
                    "progress_ratio",
                    "distance_to_goal_estimate",
                    "heading_alignment_error",
                    "path_deviation_score",
                    "waypoint_recovery_events",
                    "stalled_steps",
                ),
                required_actuator_keys=("left_velocity", "right_velocity"),
                benchmark_thresholds={
                    "target_position": (1.35, 0.0),
                    "target_tolerance": 0.18,
                    "max_collision_events": 0,
                    "min_travelled_distance": 0.05,
                    "min_mean_forward_speed": 1.2,
                },
            ),
        }
    return {
        "line-follower": ScenarioDefinition(
            name="line-follower",
            description="Follow a high-contrast floor line with a camera-based controller.",
            world=root / "line-follower" / "worlds" / "line_follower_benchmark.wbt",
            controller=root / "line-follower" / "controllers" / "line_follower_agent.py",
            target_robot_name="epuck-line-follower",
            target_robot_def="EPUCK",
            robot_family="e-puck",
            robot_profile="e-puck",
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
            robot_family="e-puck",
            robot_profile="e-puck",
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
            robot_family="e-puck",
            robot_profile="e-puck",
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


def get_scenario(name: str, robot_profile: str | None = None) -> ScenarioDefinition:
    registry = scenario_registry(robot_profile=robot_profile)
    if name not in registry:
        available = ", ".join(sorted(registry))
        raise KeyError(f"Unknown scenario '{name}'. Available scenarios: {available}")
    return registry[name]


def scenario_names() -> list[str]:
    all_names: set[str] = set()
    for profile in robot_profile_names():
        all_names.update(scenario_registry(robot_profile=profile))
    return sorted(all_names)
