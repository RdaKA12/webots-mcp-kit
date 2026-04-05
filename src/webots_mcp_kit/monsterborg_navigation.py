from __future__ import annotations

from dataclasses import dataclass
from math import copysign


CRUISE = 0
AVOID = 1
RECOVER = 2
ALIGN = 3
ADVANCE = 4
HOLD = 5

STATE_NAMES = {
    CRUISE: "cruise",
    AVOID: "avoid",
    RECOVER: "recover",
    ALIGN: "align",
    ADVANCE: "advance",
    HOLD: "hold",
}


@dataclass(slots=True)
class ObstacleMemory:
    state_code: int = CRUISE
    heading_recovery_events: int = 0
    stalled_steps: int = 0
    encoder_distance: float = 0.0
    search_direction: float = 1.0
    last_left_encoder: float | None = None
    last_right_encoder: float | None = None


@dataclass(slots=True)
class WaypointMemory:
    state_code: int = ALIGN
    waypoint_recovery_events: int = 0
    stalled_steps: int = 0
    encoder_distance: float = 0.0
    search_direction: float = 1.0
    last_left_encoder: float | None = None
    last_right_encoder: float | None = None


def clamp_value(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def state_name(state_code: int) -> str:
    return STATE_NAMES.get(int(state_code), "cruise")


def wrap_angle(angle: float) -> float:
    value = float(angle)
    while value > 3.141592653589793:
        value -= 6.283185307179586
    while value < -3.141592653589793:
        value += 6.283185307179586
    return value


def _encoder_step_distance(
    left_encoder: float | None,
    right_encoder: float | None,
    previous_left: float | None,
    previous_right: float | None,
) -> float:
    if previous_left is None or previous_right is None:
        return 0.0
    if left_encoder is None or right_encoder is None:
        return 0.0
    left_delta = float(left_encoder) - float(previous_left)
    right_delta = float(right_encoder) - float(previous_right)
    return abs((left_delta + right_delta) / 2.0) * 0.05


def obstacle_control_step(
    memory: ObstacleMemory,
    *,
    front_range: float,
    heading: float,
    yaw_rate: float,
    left_encoder: float | None,
    right_encoder: float | None,
    max_speed: float = 8.0,
    cruise_speed: float = 5.4,
    caution_range: float = 470.0,
    hard_stop_range: float = 280.0,
    range_limit: float = 900.0,
) -> tuple[ObstacleMemory, dict[str, float], tuple[float, float]]:
    next_memory = ObstacleMemory(
        state_code=memory.state_code,
        heading_recovery_events=memory.heading_recovery_events,
        stalled_steps=memory.stalled_steps,
        encoder_distance=memory.encoder_distance,
        search_direction=memory.search_direction,
        last_left_encoder=left_encoder,
        last_right_encoder=right_encoder,
    )
    progress_step = _encoder_step_distance(left_encoder, right_encoder, memory.last_left_encoder, memory.last_right_encoder)
    next_memory.encoder_distance += progress_step

    normalized_range = clamp_value(front_range / max(range_limit, 1.0), 0.0, 1.0)
    obstacle_pressure = 1.0 - normalized_range
    front_clearance_margin = (front_range - caution_range) / max(caution_range, 1.0)
    if front_range < hard_stop_range:
        target_state = RECOVER
    elif front_range < caution_range:
        target_state = AVOID
    else:
        target_state = CRUISE
    if target_state != memory.state_code and target_state == RECOVER:
        next_memory.heading_recovery_events += 1
    if abs(heading) > 0.05:
        next_memory.search_direction = -1.0 if heading > 0.0 else 1.0
    elif abs(yaw_rate) > 0.02:
        next_memory.search_direction = -1.0 if yaw_rate > 0.0 else 1.0
    next_memory.state_code = target_state

    if target_state == CRUISE:
        base_speed = cruise_speed * max(0.7, 1.0 - obstacle_pressure * 0.25)
        turn = clamp_value(heading * 1.1 + yaw_rate * 0.18, -2.4, 2.4)
    elif target_state == AVOID:
        base_speed = 2.6
        turn = 3.8 * next_memory.search_direction + yaw_rate * 0.35
    else:
        base_speed = 1.2
        turn = 4.8 * next_memory.search_direction

    left_speed = clamp_value(base_speed - turn, -max_speed, max_speed)
    right_speed = clamp_value(base_speed + turn, -max_speed, max_speed)
    mean_forward_speed = (left_speed + right_speed) / 2.0
    speed_saturation = float(abs(left_speed) >= max_speed - 0.05 or abs(right_speed) >= max_speed - 0.05)
    if abs(mean_forward_speed) > 1.0 and progress_step < 0.0015 and front_range < caution_range:
        next_memory.stalled_steps += 1

    metrics = {
        "obstacle_pressure": round(obstacle_pressure, 6),
        "mean_forward_speed": round(mean_forward_speed, 6),
        "front_clearance_margin": round(front_clearance_margin, 6),
        "clearance_violation": 1.0 if front_range < hard_stop_range else 0.0,
        "heading_recovery_events": float(next_memory.heading_recovery_events),
        "stalled_steps": float(next_memory.stalled_steps),
        "avoidance_state_code": float(next_memory.state_code),
        "speed_saturation": speed_saturation,
    }
    return next_memory, metrics, (left_speed, right_speed)


def waypoint_control_step(
    memory: WaypointMemory,
    *,
    front_range: float,
    heading: float,
    yaw_rate: float,
    left_encoder: float | None,
    right_encoder: float | None,
    target_distance: float = 2.4,
    target_heading: float = 0.0,
    max_speed: float = 8.0,
    cruise_speed: float = 6.4,
    caution_range: float = 170.0,
    hard_stop_range: float = 105.0,
    range_limit: float = 900.0,
) -> tuple[WaypointMemory, dict[str, float], tuple[float, float]]:
    next_memory = WaypointMemory(
        state_code=memory.state_code,
        waypoint_recovery_events=memory.waypoint_recovery_events,
        stalled_steps=memory.stalled_steps,
        encoder_distance=memory.encoder_distance,
        search_direction=memory.search_direction,
        last_left_encoder=left_encoder,
        last_right_encoder=right_encoder,
    )
    progress_step = _encoder_step_distance(left_encoder, right_encoder, memory.last_left_encoder, memory.last_right_encoder)
    next_memory.encoder_distance += progress_step
    normalized_range = clamp_value(front_range / max(range_limit, 1.0), 0.0, 1.0)
    obstacle_pressure = 1.0 - normalized_range
    heading_error = wrap_angle(target_heading - heading)
    heading_alignment_error = abs(heading_error)
    progress_ratio = clamp_value(next_memory.encoder_distance / max(target_distance, 1e-6), 0.0, 1.0)
    distance_to_goal_estimate = max(target_distance - next_memory.encoder_distance, 0.0)
    if front_range < hard_stop_range:
        target_state = RECOVER
    elif heading_alignment_error > 0.28:
        target_state = ALIGN
    else:
        target_state = ADVANCE
    if target_state != memory.state_code and target_state in {ALIGN, RECOVER}:
        next_memory.waypoint_recovery_events += 1
    if abs(heading_error) > 0.04:
        next_memory.search_direction = copysign(1.0, heading_error)
    elif abs(yaw_rate) > 0.02:
        next_memory.search_direction = -1.0 if yaw_rate > 0.0 else 1.0
    next_memory.state_code = target_state

    if target_state == ADVANCE:
        base_speed = cruise_speed * max(0.72, 1.0 - heading_alignment_error * 0.5)
        if front_range < caution_range:
            base_speed *= 0.82
        turn = clamp_value(heading_error * 3.2 - yaw_rate * 0.28, -2.8, 2.8)
    elif target_state == ALIGN:
        base_speed = 2.2
        turn = 4.0 * next_memory.search_direction
    elif target_state == RECOVER:
        base_speed = 0.8
        turn = 5.0 * next_memory.search_direction
    else:
        base_speed = 0.0
        turn = 0.0

    left_speed = clamp_value(base_speed - turn, -max_speed, max_speed)
    right_speed = clamp_value(base_speed + turn, -max_speed, max_speed)
    mean_forward_speed = (left_speed + right_speed) / 2.0
    speed_saturation = float(abs(left_speed) >= max_speed - 0.05 or abs(right_speed) >= max_speed - 0.05)
    if target_state in {ADVANCE, ALIGN} and abs(mean_forward_speed) > 1.0 and progress_step < 0.0015:
        next_memory.stalled_steps += 1
    path_deviation_score = heading_alignment_error * 0.8 + abs(yaw_rate) * 0.12 + obstacle_pressure * 0.2

    metrics = {
        "obstacle_pressure": round(obstacle_pressure, 6),
        "mean_forward_speed": round(mean_forward_speed, 6),
        "progress_ratio": round(progress_ratio, 6),
        "distance_to_goal_estimate": round(distance_to_goal_estimate, 6),
        "heading_alignment_error": round(heading_alignment_error, 6),
        "path_deviation_score": round(path_deviation_score, 6),
        "waypoint_recovery_events": float(next_memory.waypoint_recovery_events),
        "stalled_steps": float(next_memory.stalled_steps),
        "waypoint_state_code": float(next_memory.state_code),
        "speed_saturation": speed_saturation,
    }
    return next_memory, metrics, (left_speed, right_speed)
