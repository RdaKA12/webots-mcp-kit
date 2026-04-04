from __future__ import annotations

from controller import Camera, Robot

from webots_mcp_kit.agent import ControllerAgent


TIME_STEP = 32
MAX_SPEED = 8.0
CRUISE = 5.4
TURN_GAIN = 5.2


# webots-kit region HELPERS start
def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def set_drive_velocity(left_velocity: float, right_velocity: float) -> None:
    front_left_motor.setVelocity(left_velocity)
    rear_left_motor.setVelocity(left_velocity)
    front_right_motor.setVelocity(right_velocity)
    rear_right_motor.setVelocity(right_velocity)


def find_middle(values: list[int]) -> int:
    size = len(values)
    mean = sum(values) / max(size, 1)
    strong = [(index, value) for index, value in enumerate(values) if value > mean]
    if not strong:
        return size // 2
    strong.sort(key=lambda item: item[1], reverse=True)
    sample = strong[: max(size // 10, 1)]
    rough_center = sum(index for index, _ in sample) / len(sample)
    filtered = [index for index, _ in sample if abs(index - rough_center) <= size / 8]
    if not filtered:
        return size // 2
    return int(sum(filtered) / len(filtered))
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
previous_heading = 0.0

while robot.step(TIME_STEP) != -1:
    image = front_camera.getImage()
    blue = [255 - Camera.imageGetBlue(image, camera_width, x, 0) for x in range(camera_width)]
    middle = find_middle(blue)
    delta = middle - camera_width / 2.0
    line_visible = any(value > 15 for value in blue)
    camera_left = sum(blue[: camera_width // 3]) / max(camera_width // 3, 1)
    camera_center = sum(blue[camera_width // 3 : 2 * camera_width // 3]) / max(camera_width // 3, 1)
    camera_right = sum(blue[2 * camera_width // 3 :]) / max(camera_width - 2 * (camera_width // 3), 1)

    heading = float(imu.getRollPitchYaw()[2])
    yaw_rate = (heading - previous_heading) / max(TIME_STEP / 1000.0, 1e-6)
    previous_heading = heading
    front_range_value = float(front_range.getValue())
    left_ticks = float(left_encoder.getValue())
    right_ticks = float(right_encoder.getValue())

    # webots-kit region CONTROL_POLICY start
    left_speed = clamp(CRUISE - TURN_GAIN * (delta / max(camera_width / 2.0, 1.0)), -MAX_SPEED, MAX_SPEED)
    right_speed = clamp(CRUISE + TURN_GAIN * (delta / max(camera_width / 2.0, 1.0)), -MAX_SPEED, MAX_SPEED)
    # webots-kit region CONTROL_POLICY end

    override = agent.begin_step()
    if override is not None:
        left_speed, right_speed = override

    left_speed = clamp(left_speed, -MAX_SPEED, MAX_SPEED)
    right_speed = clamp(right_speed, -MAX_SPEED, MAX_SPEED)
    set_drive_velocity(left_speed, right_speed)

    # webots-kit region TELEMETRY_REPORT start
    sensors={
        "camera_left_band": round(camera_left, 3),
        "camera_center_band": round(camera_center, 3),
        "camera_right_band": round(camera_right, 3),
        "front_range": round(front_range_value, 6),
        "heading": round(heading, 6),
        "yaw_rate": round(yaw_rate, 6),
        "left_encoder": round(left_ticks, 6),
        "right_encoder": round(right_ticks, 6),
    }
    metrics={
        "line_visible": 1.0 if line_visible else 0.0,
        "center_error": round(delta / max(camera_width / 2.0, 1.0), 6),
        "ir_balance_error": round((camera_left - camera_right) / 255.0, 6),
        "mean_forward_speed": round((left_speed + right_speed) / 2.0, 6),
    }
    actuators={
        "left_velocity": round(left_speed, 6),
        "right_velocity": round(right_speed, 6),
    }
    camera_frames={"front_camera": {"image": image, "width": camera_width, "height": camera_height}}
    # webots-kit region TELEMETRY_REPORT end

    agent.report_step(
        sensors=sensors,
        metrics=metrics,
        actuators=actuators,
        camera_frames=camera_frames,
    )
