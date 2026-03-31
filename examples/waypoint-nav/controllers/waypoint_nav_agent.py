from __future__ import annotations

from controller import Robot

from webots_mcp_kit.agent import ControllerAgent


MAX_SPEED = 6.28
CRUISE_SPEED = 4.2
DISTANCE_SENSORS = ("ps0", "ps1", "ps2", "ps3", "ps4", "ps5", "ps6", "ps7")


robot = Robot()
time_step = int(robot.getBasicTimeStep())

distance_sensors = []
for name in DISTANCE_SENSORS:
    sensor = robot.getDevice(name)
    sensor.enable(time_step)
    distance_sensors.append(sensor)

camera = robot.getDevice("camera")
if camera is not None:
    camera.enable(time_step)

left_motor = robot.getDevice("left wheel motor")
right_motor = robot.getDevice("right wheel motor")
left_motor.setPosition(float("inf"))
right_motor.setPosition(float("inf"))
left_motor.setVelocity(0.0)
right_motor.setVelocity(0.0)

agent = ControllerAgent.from_robot(robot, default_camera="camera")

while robot.step(time_step) != -1:
    sensor_values = [sensor.getValue() / 4096.0 for sensor in distance_sensors]
    left_speed = CRUISE_SPEED
    right_speed = CRUISE_SPEED

    front_pressure = max(sensor_values[0], sensor_values[7], sensor_values[1], sensor_values[6])
    if front_pressure > 0.12:
        left_speed = -2.0
        right_speed = 2.5

    override = agent.begin_step()
    if override is not None:
        left_speed, right_speed = override

    left_speed = max(-MAX_SPEED, min(MAX_SPEED, left_speed))
    right_speed = max(-MAX_SPEED, min(MAX_SPEED, right_speed))
    left_motor.setVelocity(left_speed)
    right_motor.setVelocity(right_speed)

    image = camera.getImage() if camera is not None else None
    agent.report_step(
        sensors={name: round(value, 6) for name, value in zip(DISTANCE_SENSORS, sensor_values)},
        metrics={
            "line_visible": False,
            "center_error": 0.0,
            "ir_balance_error": round(sensor_values[0] - sensor_values[7], 6),
            "obstacle_pressure": round(front_pressure, 6),
            "mean_forward_speed": round((left_speed + right_speed) / 2.0, 6),
        },
        actuators={
            "left_velocity": round(left_speed, 6),
            "right_velocity": round(right_speed, 6),
        },
        camera_frames={"camera": {"image": image, "width": camera.getWidth(), "height": camera.getHeight()}} if image else None,
    )
