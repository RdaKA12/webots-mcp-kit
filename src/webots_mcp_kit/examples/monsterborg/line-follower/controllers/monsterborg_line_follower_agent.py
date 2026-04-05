from __future__ import annotations

from controller import Camera, Robot

from webots_mcp_kit.agent import ControllerAgent
from webots_mcp_kit.monsterborg_line_follow import (
    LineFollowMemory,
    camera_rows_from_image,
    clamp_velocity_pair,
    compute_drive_targets,
    update_memory,
    analyze_scan_rows,
)


TIME_STEP = 32
MAX_SPEED = 8.0
CRUISE = 5.8
MIN_CRUISE = 2.6
TURN_GAIN = 5.6
CURVATURE_GAIN = 2.4
SEARCH_SPEED = 3.2
RECOVER_SPEED = 3.8


# webots-kit region HELPERS start
def set_drive_velocity(left_velocity: float, right_velocity: float) -> None:
    front_left_motor.setVelocity(left_velocity)
    rear_left_motor.setVelocity(left_velocity)
    front_right_motor.setVelocity(right_velocity)
    rear_right_motor.setVelocity(right_velocity)
# webots-kit region HELPERS end


robot = Robot()

# webots-kit region DEVICE_INIT start
front_left_motor = robot.getDevice("front_left_motor")
rear_left_motor = robot.getDevice("rear_left_motor")
front_right_motor = robot.getDevice("front_right_motor")
rear_right_motor = robot.getDevice("rear_right_motor")
for motor in (front_left_motor, rear_left_motor, front_right_motor, rear_right_motor):
    motor.setPosition(float("inf"))
    motor.setVelocity(0.0)

left_encoder = robot.getDevice("left_encoder")
right_encoder = robot.getDevice("right_encoder")
left_encoder.enable(TIME_STEP)
right_encoder.enable(TIME_STEP)

front_camera = robot.getDevice("front_camera")
front_camera.enable(TIME_STEP)
camera_width = front_camera.getWidth()
camera_height = front_camera.getHeight()

front_range = robot.getDevice("front_range")
front_range.enable(TIME_STEP)

imu = robot.getDevice("imu")
imu.enable(TIME_STEP)
# webots-kit region DEVICE_INIT end

agent = ControllerAgent.from_robot(robot, default_camera="front_camera")
memory = LineFollowMemory()
previous_heading = 0.0

while robot.step(TIME_STEP) != -1:
    image = front_camera.getImage()
    rows = camera_rows_from_image(
        image,
        width=camera_width,
        height=camera_height,
        blue_reader=Camera.imageGetBlue,
    )
    profile = analyze_scan_rows(rows)
    updated_memory = update_memory(memory, profile)

    heading = float(imu.getRollPitchYaw()[2])
    yaw_rate = (heading - previous_heading) / max(TIME_STEP / 1000.0, 1e-6)
    previous_heading = heading
    front_range_value = float(front_range.getValue())
    left_ticks = float(left_encoder.getValue())
    right_ticks = float(right_encoder.getValue())

    # webots-kit region CONTROL_POLICY start
    left_speed, right_speed = compute_drive_targets(
        updated_memory,
        profile,
        max_speed=MAX_SPEED,
        cruise_speed=CRUISE,
        minimum_cruise=MIN_CRUISE,
        turn_gain=TURN_GAIN,
        curvature_gain=CURVATURE_GAIN,
        search_speed=SEARCH_SPEED,
        recover_speed=RECOVER_SPEED,
    )
    # webots-kit region CONTROL_POLICY end

    override = agent.begin_step()
    if override is not None:
        left_speed, right_speed = override

    left_speed, right_speed = clamp_velocity_pair(left_speed, right_speed, max_speed=MAX_SPEED)
    set_drive_velocity(left_speed, right_speed)

    saturation = 1.0 if max(abs(left_speed), abs(right_speed)) >= MAX_SPEED * 0.98 else 0.0

    # webots-kit region TELEMETRY_REPORT start
    sensors = {
        "camera_left_band": round(profile.left_band, 3),
        "camera_center_band": round(profile.center_band, 3),
        "camera_right_band": round(profile.right_band, 3),
        "front_range": round(front_range_value, 6),
        "heading": round(heading, 6),
        "yaw_rate": round(yaw_rate, 6),
        "left_encoder": round(left_ticks, 6),
        "right_encoder": round(right_ticks, 6),
    }
    metrics = {
        "line_visible": 1.0 if profile.line_visible else 0.0,
        "line_confidence": round(profile.confidence, 6),
        "camera_signal_strength": round(profile.signal_strength_mean, 6),
        "center_error": round(profile.center_error, 6),
        "ir_balance_error": round((profile.left_band - profile.right_band) / 255.0, 6),
        "mean_forward_speed": round((left_speed + right_speed) / 2.0, 6),
        "tracking_state_code": float(updated_memory.state_code),
        "speed_saturation": saturation,
    }
    actuators = {
        "left_velocity": round(left_speed, 6),
        "right_velocity": round(right_speed, 6),
    }
    camera_frames = {"front_camera": {"image": image, "width": camera_width, "height": camera_height}}
    # webots-kit region TELEMETRY_REPORT end

    agent.report_step(
        sensors=sensors,
        metrics=metrics,
        actuators=actuators,
        camera_frames=camera_frames,
    )

    memory = LineFollowMemory(
        state_code=updated_memory.state_code,
        lost_steps=updated_memory.lost_steps,
        last_center_error=profile.center_error,
        search_direction=updated_memory.search_direction,
    )
