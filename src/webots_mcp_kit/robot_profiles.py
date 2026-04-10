from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .monsterborg_dimensions import monsterborg_dimensions
from .models import bundled_example_root


@dataclass(frozen=True, slots=True)
class RobotProfile:
    robot_family: str
    robot_profile: str
    drive_model: str
    logical_drive_channels: tuple[str, ...]
    device_contract: dict[str, Any]
    default_camera: str | None
    default_templates: dict[str, str]
    footprint_radius: float
    supported_tasks: tuple[str, ...]
    world_proto: str | None
    import_hints: dict[str, Any] = field(default_factory=dict)
    runtime_targets: tuple[str, ...] = ("interactive-webots",)


def _examples_root() -> Path:
    return bundled_example_root()


def robot_profile_registry() -> dict[str, RobotProfile]:
    monsterborg = monsterborg_dimensions()
    return {
        "e-puck": RobotProfile(
            robot_family="e-puck",
            robot_profile="e-puck",
            drive_model="2wd-differential",
            logical_drive_channels=("left_drive", "right_drive"),
            device_contract={
                "motors": ["left wheel motor", "right wheel motor"],
                "encoders": [],
                "camera": "camera",
                "range": ["ps0", "ps1", "ps2", "ps3", "ps4", "ps5", "ps6", "ps7"],
                "imu": None,
            },
            default_camera="camera",
            default_templates={
                "line-follow": "epuck-line-track",
                "waypoint-nav": "epuck-waypoint",
                "obstacle-avoidance": "epuck-obstacle-course",
            },
            footprint_radius=0.045,
            supported_tasks=("line-follow", "waypoint-nav", "obstacle-avoidance"),
            world_proto="E-puck",
            import_hints={
                "node_types": ["E-puck"],
                "device_names": ["left wheel motor", "right wheel motor", "camera"],
            },
            runtime_targets=("interactive-webots",),
        ),
        "monsterborg-4wd": RobotProfile(
            robot_family="monsterborg",
            robot_profile="monsterborg-4wd",
            drive_model="4wd-skid-steer",
            logical_drive_channels=("left_drive", "right_drive"),
            device_contract={
                "motors": [
                    "front_left_motor",
                    "rear_left_motor",
                    "front_right_motor",
                    "rear_right_motor",
                ],
                "logical_drives": {
                    "left_drive": ["front_left_motor", "rear_left_motor"],
                    "right_drive": ["front_right_motor", "rear_right_motor"],
                },
                "encoders": ["left_encoder", "right_encoder"],
                "camera": "front_camera",
                "range": ["front_range"],
                "imu": ["imu"],
            },
            default_camera="front_camera",
            default_templates={
                "line-follow": "monsterborg-line-track",
                "waypoint-nav": "monsterborg-waypoint",
                "obstacle-avoidance": "monsterborg-obstacle-course",
            },
            footprint_radius=monsterborg.footprint_radius_m,
            supported_tasks=("line-follow", "waypoint-nav", "obstacle-avoidance"),
            world_proto="MonsterBorg4WD.proto",
            import_hints={
                "node_types": ["Robot", "MonsterBorg4WD"],
                "name_prefixes": ["monsterborg-"],
                "device_names": ["front_left_motor", "rear_left_motor", "front_camera", "front_range", "imu"],
            },
            runtime_targets=("interactive-webots", "monsterborg-physical"),
        ),
    }


def get_robot_profile(name: str | None = None) -> RobotProfile:
    registry = robot_profile_registry()
    key = (name or "e-puck").strip()
    if key not in registry:
        available = ", ".join(sorted(registry))
        raise KeyError(f"Unknown robot profile '{key}'. Available profiles: {available}")
    return registry[key]


def robot_profile_names() -> list[str]:
    return sorted(robot_profile_registry())


def robot_profile_from_template(template: str | None) -> str:
    if not template:
        return "e-puck"
    normalized = template.strip().lower()
    if normalized.startswith("monsterborg-"):
        return "monsterborg-4wd"
    return "e-puck"
