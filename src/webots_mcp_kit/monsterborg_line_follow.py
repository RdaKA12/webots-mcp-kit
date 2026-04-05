from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Iterable, Sequence


TRACK = 0
PREDICT = 1
SEARCH = 2
RECOVER = 3

TRACKING_STATE_NAMES = {
    TRACK: "track",
    PREDICT: "predict",
    SEARCH: "search",
    RECOVER: "recover",
}


@dataclass(slots=True)
class LineProfile:
    width: int
    left_band: float
    center_band: float
    right_band: float
    center_index: float
    center_error: float
    signal_strength_mean: float
    threshold: float
    confidence: float
    line_visible: bool


@dataclass(slots=True)
class LineFollowMemory:
    state_code: int = TRACK
    lost_steps: int = 0
    last_center_error: float = 0.0
    search_direction: float = 1.0


def tracking_state_name(state_code: int) -> str:
    return TRACKING_STATE_NAMES.get(state_code, "track")


def blend_rows(rows: Sequence[Sequence[float]]) -> list[float]:
    if not rows:
        return []
    width = len(rows[0])
    if width <= 0:
        return []
    return [mean(float(row[index]) for row in rows) for index in range(width)]


def smooth_scan(values: Sequence[float]) -> list[float]:
    raw = [float(value) for value in values]
    if len(raw) < 3:
        return raw
    smoothed = raw[:]
    for index in range(1, len(raw) - 1):
        smoothed[index] = (raw[index - 1] + raw[index] * 2.0 + raw[index + 1]) / 4.0
    return smoothed


def band_average(values: Sequence[float], start: int, end: int) -> float:
    if not values:
        return 0.0
    start = max(0, start)
    end = min(len(values), end)
    if start >= end:
        return 0.0
    return mean(float(value) for value in values[start:end])


def adaptive_threshold(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    values_list = [float(value) for value in values]
    baseline = mean(values_list)
    deviation = pstdev(values_list) if len(values_list) > 1 else 0.0
    return max(12.0, baseline + max(6.0, deviation * 0.35))


def analyze_scan_rows(rows: Sequence[Sequence[float]]) -> LineProfile:
    merged = blend_rows(rows)
    smoothed = smooth_scan(merged)
    width = len(smoothed)
    if width <= 0:
        return LineProfile(
            width=0,
            left_band=0.0,
            center_band=0.0,
            right_band=0.0,
            center_index=0.0,
            center_error=0.0,
            signal_strength_mean=0.0,
            threshold=0.0,
            confidence=0.0,
            line_visible=False,
        )

    threshold = adaptive_threshold(smoothed)
    active_weights = [(index, max(0.0, value - threshold)) for index, value in enumerate(smoothed)]
    weighted = [(index, weight) for index, weight in active_weights if weight > 0.0]
    if weighted:
        weight_sum = sum(weight for _, weight in weighted)
        center_index = sum(index * weight for index, weight in weighted) / max(weight_sum, 1e-6)
        active_ratio = len(weighted) / width
        peak = max(weight for _, weight in weighted)
        confidence = min(1.0, active_ratio * 1.75 + peak / max(threshold + 25.0, 40.0))
        line_visible = confidence >= 0.18 and active_ratio >= 0.02
    else:
        center_index = width / 2.0
        confidence = 0.0
        line_visible = False

    center_error = (center_index - width / 2.0) / max(width / 2.0, 1.0)
    third = max(width // 3, 1)
    left_band = band_average(smoothed, 0, third)
    center_band = band_average(smoothed, third, 2 * third)
    right_band = band_average(smoothed, 2 * third, width)
    return LineProfile(
        width=width,
        left_band=left_band,
        center_band=center_band,
        right_band=right_band,
        center_index=center_index,
        center_error=center_error,
        signal_strength_mean=mean(smoothed),
        threshold=threshold,
        confidence=confidence,
        line_visible=line_visible,
    )


def update_memory(memory: LineFollowMemory, profile: LineProfile) -> LineFollowMemory:
    next_memory = LineFollowMemory(
        state_code=memory.state_code,
        lost_steps=memory.lost_steps,
        last_center_error=memory.last_center_error,
        search_direction=memory.search_direction,
    )
    if profile.line_visible and profile.confidence >= 0.25:
        next_memory.search_direction = 1.0 if profile.center_error >= 0.0 else -1.0
        next_memory.state_code = RECOVER if memory.lost_steps >= 4 else TRACK
        next_memory.lost_steps = 0
    else:
        next_memory.lost_steps += 1
        if next_memory.lost_steps <= 3:
            next_memory.state_code = PREDICT
        elif next_memory.lost_steps <= 10:
            next_memory.state_code = SEARCH
        else:
            next_memory.state_code = RECOVER
    return next_memory


def compute_drive_targets(
    memory: LineFollowMemory,
    profile: LineProfile,
    *,
    max_speed: float,
    cruise_speed: float,
    minimum_cruise: float,
    turn_gain: float,
    curvature_gain: float,
    search_speed: float,
    recover_speed: float,
) -> tuple[float, float]:
    error = float(profile.center_error)
    curvature = error - float(memory.last_center_error)
    search_direction = 1.0 if memory.search_direction >= 0.0 else -1.0
    if memory.state_code == TRACK:
        throttle_scale = max(0.4, 1.0 - min(abs(error), 1.0) * 0.55 - min(abs(curvature), 1.0) * 0.15)
        base_speed = max(minimum_cruise, cruise_speed * (0.55 + 0.45 * profile.confidence) * throttle_scale)
        turn = turn_gain * error + curvature_gain * curvature
        left_speed = base_speed - turn
        right_speed = base_speed + turn
    elif memory.state_code == PREDICT:
        predicted_error = error if profile.line_visible else memory.last_center_error + search_direction * 0.12 * min(memory.lost_steps, 3)
        base_speed = max(minimum_cruise * 0.95, cruise_speed * 0.5)
        turn = turn_gain * predicted_error
        left_speed = base_speed - turn
        right_speed = base_speed + turn
    elif memory.state_code == SEARCH:
        base_speed = search_speed * 0.35
        turn = search_speed * (0.85 + min(memory.lost_steps, 10) * 0.05) * search_direction
        left_speed = base_speed - turn
        right_speed = base_speed + turn
    else:
        left_speed = recover_speed * search_direction
        right_speed = -recover_speed * search_direction

    left_speed = max(-max_speed, min(max_speed, left_speed))
    right_speed = max(-max_speed, min(max_speed, right_speed))
    return left_speed, right_speed


def clamp_velocity_pair(left_speed: float, right_speed: float, *, max_speed: float) -> tuple[float, float]:
    return (
        max(-max_speed, min(max_speed, float(left_speed))),
        max(-max_speed, min(max_speed, float(right_speed))),
    )


def camera_rows_from_image(
    image: object,
    *,
    width: int,
    height: int,
    blue_reader,
    row_indexes: Iterable[int] | None = None,
) -> list[list[float]]:
    if width <= 0 or height <= 0:
        return []
    if row_indexes is None:
        row_indexes = sorted({max(0, height // 4), max(0, height // 2), max(0, height - 1)})
    rows: list[list[float]] = []
    for row_index in row_indexes:
        y = max(0, min(height - 1, int(row_index)))
        rows.append([255.0 - float(blue_reader(image, width, x, y)) for x in range(width)])
    return rows

