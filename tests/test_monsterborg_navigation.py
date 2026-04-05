from __future__ import annotations

from webots_mcp_kit.monsterborg_navigation import (
    AVOID,
    ALIGN,
    ObstacleMemory,
    RECOVER,
    WaypointMemory,
    obstacle_control_step,
    waypoint_control_step,
)


def test_obstacle_control_enters_recovery_and_tracks_stalls() -> None:
    memory = ObstacleMemory()
    memory, metrics, speeds = obstacle_control_step(
        memory,
        front_range=220.0,
        heading=0.18,
        yaw_rate=0.02,
        left_encoder=0.0,
        right_encoder=0.0,
    )
    assert memory.state_code == RECOVER
    assert metrics["heading_recovery_events"] >= 1.0
    assert speeds[0] != speeds[1]

    stalled_memory = memory
    stalled_memory.last_left_encoder = 0.0
    stalled_memory.last_right_encoder = 0.0
    stalled_memory, stalled_metrics, _ = obstacle_control_step(
        stalled_memory,
        front_range=240.0,
        heading=0.1,
        yaw_rate=0.0,
        left_encoder=0.0,
        right_encoder=0.0,
    )
    assert stalled_memory.stalled_steps >= 1
    assert stalled_metrics["clearance_violation"] == 1.0


def test_obstacle_control_uses_avoid_mode_for_caution_clearance() -> None:
    memory = ObstacleMemory()
    memory, metrics, _ = obstacle_control_step(
        memory,
        front_range=360.0,
        heading=0.0,
        yaw_rate=0.0,
        left_encoder=0.4,
        right_encoder=0.42,
    )
    assert memory.state_code == AVOID
    assert metrics["front_clearance_margin"] < 0.0


def test_waypoint_control_reports_progress_and_alignment() -> None:
    memory = WaypointMemory()
    memory.last_left_encoder = 0.0
    memory.last_right_encoder = 0.0
    memory, metrics, speeds = waypoint_control_step(
        memory,
        front_range=650.0,
        heading=0.08,
        yaw_rate=0.01,
        left_encoder=2.0,
        right_encoder=2.0,
    )
    assert memory.state_code in {ALIGN, 4, 5}
    assert metrics["progress_ratio"] > 0.0
    assert metrics["distance_to_goal_estimate"] >= 0.0
    assert metrics["heading_alignment_error"] >= 0.0
    assert speeds[0] != speeds[1]


def test_waypoint_control_recovery_path_is_observable() -> None:
    memory = WaypointMemory()
    memory, metrics, _ = waypoint_control_step(
        memory,
        front_range=80.0,
        heading=0.4,
        yaw_rate=0.0,
        left_encoder=0.0,
        right_encoder=0.0,
    )
    assert memory.state_code == RECOVER
    assert metrics["waypoint_recovery_events"] >= 1.0
