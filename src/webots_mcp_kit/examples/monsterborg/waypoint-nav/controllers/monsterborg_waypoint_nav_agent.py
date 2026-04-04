from __future__ import annotations

from controller import Robot

from webots_mcp_kit.agent import ControllerAgent


MAX_SPEED = 8.0
CRUISE = 5.8
RANGE_LIMIT = 900.0
HEADING_GAIN = 0.25


# webots-kit region HELPERS start
def clamp(value: float) -> float:
    return max(-MAX_SPEED, min(MAX_SPEED, value))


def set_drive_velocity(left_velocity: float, right_velocity: float) -> None:
    front_left_motor.setVelocity(left_velocity)
    rear_left_motor.setVelocity(left_velocity)
    front_right_motor.setVelocity(right_velocity)
    rear_right_motor.setVelocity(right_velocity)
# webots-kit region HELPERS end


robot = Robot()
time_step = int(robot.getBasicTimeStep())

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
left_encoder.enable(time_step)
right_encoder.enable(time_step)

front_camera = robot.getDevice("front_camera")
front_camera.enable(time_step)

front_range = robot.getDevice("front_range")
front_range.enable(time_step)

imu = robot.getDevice("imu")
imu.enable(time_step)
# webots-kit region DEVICE_INIT end

agent = ControllerAgent.from_robot(robot, default_camera="front_camera")
previous_heading = 0.0

while robot.step(time_step) != -1:
    front_range_value = float(front_range.getValue())
    normalized_range = min(max(front_range_value / RANGE_LIMIT, 0.0), 1.0)
    heading = float(imu.getRollPitchYaw()[2])
    yaw_rate = (heading - previous_heading) / max(time_step / 1000.0, 1e-6)
    previous_heading = heading
    left_ticks = float(left_encoder.getValue())
    right_ticks = float(right_encoder.getValue())

    # webots-kit region CONTROL_POLICY start
    turn_bias = HEADING_GAIN * heading
    left_speed = clamp(CRUISE - normalized_range * 2.5 - turn_bias)
    right_speed = clamp(CRUISE - normalized_range * 2.5 + turn_bias)
    # webots-kit region CONTROL_POLICY end

    override = agent.begin_step()
    if override is not None:
        left_speed, right_speed = override

    set_drive_velocity(left_speed, right_speed)
    image = front_camera.getImage()

    # webots-kit region TELEMETRY_REPORT start
    sensors={
        "front_range": round(front_range_value, 6),
        "heading": round(heading, 6),
        "yaw_rate": round(yaw_rate, 6),
        "left_encoder": round(left_ticks, 6),
        "right_encoder": round(right_ticks, 6),
    }
    metrics={
        "obstacle_pressure": round(normalized_range, 6),
        "mean_forward_speed": round((left_speed + right_speed) / 2.0, 6),
        "line_visible": 0.0,
        "center_error": 0.0,
        "ir_balance_error": round((left_ticks - right_ticks) * 0.01, 6),
    }
    actuators={
        "left_velocity": round(left_speed, 6),
        "right_velocity": round(right_speed, 6),
    }
    camera_frames={"front_camera": {"image": image, "width": front_camera.getWidth(), "height": front_camera.getHeight()}}
    # webots-kit region TELEMETRY_REPORT end

    agent.report_step(
        sensors=sensors,
        metrics=metrics,
        actuators=actuators,
        camera_frames=camera_frames,
    )
