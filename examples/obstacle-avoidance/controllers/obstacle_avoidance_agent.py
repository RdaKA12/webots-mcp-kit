from __future__ import annotations

from controller import Robot

from webots_mcp_kit.agent import ControllerAgent


MAX_SPEED = 6.28
LEFT = 0
RIGHT = 1
DISTANCE_SENSORS = ("ps0", "ps1", "ps2", "ps3", "ps4", "ps5", "ps6", "ps7")
WEIGHTS = (
    (-1.3, -1.0),
    (-1.3, -1.0),
    (-0.5, 0.5),
    (0.0, 0.0),
    (0.0, 0.0),
    (0.05, -0.5),
    (-0.75, 0.0),
    (-0.75, 0.0),
)
OFFSETS = (0.5 * MAX_SPEED, 0.5 * MAX_SPEED)


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
    speeds = [0.0, 0.0]
    for side in (LEFT, RIGHT):
        weighted = 0.0
        for index, value in enumerate(sensor_values):
            weighted += value * WEIGHTS[index][side]
        speeds[side] = OFFSETS[side] + weighted * MAX_SPEED
        speeds[side] = max(-MAX_SPEED, min(MAX_SPEED, speeds[side]))

    override = agent.begin_step()
    if override is not None:
        speeds[LEFT], speeds[RIGHT] = override

    left_motor.setVelocity(speeds[LEFT])
    right_motor.setVelocity(speeds[RIGHT])

    obstacle_pressure = max(sensor_values)
    image = camera.getImage() if camera is not None else None
    agent.report_step(
        sensors={name: round(value, 6) for name, value in zip(DISTANCE_SENSORS, sensor_values)},
        metrics={
            "line_visible": False,
            "center_error": 0.0,
            "ir_balance_error": round(sensor_values[0] - sensor_values[7], 6),
            "obstacle_pressure": round(obstacle_pressure, 6),
            "mean_forward_speed": round((speeds[LEFT] + speeds[RIGHT]) / 2.0, 6),
        },
        actuators={
            "left_velocity": round(speeds[LEFT], 6),
            "right_velocity": round(speeds[RIGHT], 6),
        },
        camera_frames={"camera": {"image": image, "width": camera.getWidth(), "height": camera.getHeight()}} if image else None,
    )
