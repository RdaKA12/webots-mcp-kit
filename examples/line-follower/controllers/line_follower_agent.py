from __future__ import annotations

from controller import Camera, Robot

from webots_mcp_kit.agent import AgentBridge


TIME_STEP = 32
SPEED_UNIT = 0.00628
CRUISE = 200
TURN_GAIN = 4


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def find_middle(values: list[int]) -> int:
    size = len(values)
    mean = sum(values) / max(size, 1)
    strong = [(index, value) for index, value in enumerate(values) if value > mean]
    if not strong:
        return size // 2
    strong.sort(key=lambda item: item[1], reverse=True)
    sample = strong[: max(size // 10, 1)]
    rough_center = sum(index for index, _ in sample) / len(sample)
    filtered = [index for index, _ in sample if abs(index - rough_center) <= size / 10]
    if not filtered:
        return size // 2
    return int(sum(filtered) / len(filtered))


robot = Robot()

left_motor = robot.getDevice("left wheel motor")
right_motor = robot.getDevice("right wheel motor")
left_motor.setPosition(float("inf"))
right_motor.setPosition(float("inf"))
left_motor.setVelocity(0.0)
right_motor.setVelocity(0.0)

camera = robot.getDevice("camera")
camera.enable(TIME_STEP)
width = camera.getWidth()
height = camera.getHeight()

bridge = AgentBridge(robot=robot, devices=robot.devices, default_camera="camera")

while robot.step(TIME_STEP) != -1:
    image = camera.getImage()
    blue = [255 - Camera.imageGetBlue(image, width, x, 0) for x in range(width)]
    middle = find_middle(blue)
    delta = middle - width / 2.0
    line_visible = any(value > 15 for value in blue)
    camera_left = sum(blue[: width // 3]) / max(width // 3, 1)
    camera_center = sum(blue[width // 3 : 2 * width // 3]) / max(width // 3, 1)
    camera_right = sum(blue[2 * width // 3 :]) / max(width - 2 * (width // 3), 1)

    left_speed = SPEED_UNIT * (CRUISE - TURN_GAIN * abs(delta) + TURN_GAIN * delta)
    right_speed = SPEED_UNIT * (CRUISE - TURN_GAIN * abs(delta) - TURN_GAIN * delta)

    override = bridge.begin_step()
    if override is not None:
        left_speed, right_speed = override

    left_speed = clamp(left_speed, -6.28, 6.28)
    right_speed = clamp(right_speed, -6.28, 6.28)

    left_motor.setVelocity(left_speed)
    right_motor.setVelocity(right_speed)

    bridge.publish_step(
        sensors={
            "camera_left_band": round(camera_left, 3),
            "camera_center_band": round(camera_center, 3),
            "camera_right_band": round(camera_right, 3),
        },
        metrics={
            "line_visible": line_visible,
            "center_error": round(delta / max(width / 2.0, 1.0), 6),
            "ir_balance_error": round((camera_left - camera_right) / 255.0, 6),
        },
        actuators={
            "left_velocity": round(left_speed, 6),
            "right_velocity": round(right_speed, 6),
        },
        camera_frames={"camera": {"image": image, "width": width, "height": height}},
    )
