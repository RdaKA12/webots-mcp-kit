from __future__ import annotations

from controller import Robot

from webots_mcp_kit.agent import ControllerAgent
from webots_mcp_kit.monsterborg_navigation import WaypointMemory, waypoint_control_step


# webots-kit region HELPERS start
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
memory = WaypointMemory()
previous_heading = 0.0

while robot.step(time_step) != -1:
    front_range_value = float(front_range.getValue())
    heading = float(imu.getRollPitchYaw()[2])
    yaw_rate = (heading - previous_heading) / max(time_step / 1000.0, 1e-6)
    previous_heading = heading
    left_ticks = float(left_encoder.getValue())
    right_ticks = float(right_encoder.getValue())

    # webots-kit region CONTROL_POLICY start
    memory, policy_metrics, (left_speed, right_speed) = waypoint_control_step(
        memory,
        front_range=front_range_value,
        heading=heading,
        yaw_rate=yaw_rate,
        left_encoder=left_ticks,
        right_encoder=right_ticks,
    )
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
        "obstacle_pressure": policy_metrics["obstacle_pressure"],
        "mean_forward_speed": round((left_speed + right_speed) / 2.0, 6),
        "progress_ratio": policy_metrics["progress_ratio"],
        "distance_to_goal_estimate": policy_metrics["distance_to_goal_estimate"],
        "heading_alignment_error": policy_metrics["heading_alignment_error"],
        "path_deviation_score": policy_metrics["path_deviation_score"],
        "waypoint_recovery_events": policy_metrics["waypoint_recovery_events"],
        "stalled_steps": policy_metrics["stalled_steps"],
        "waypoint_state_code": policy_metrics["waypoint_state_code"],
        "speed_saturation": policy_metrics["speed_saturation"],
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
