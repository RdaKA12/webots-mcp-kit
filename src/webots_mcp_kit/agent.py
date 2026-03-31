from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .runtime_io import RuntimeSocketClient, connect_runtime


DEVICE_CAPABILITY_MAP: dict[str, dict[str, Any]] = {
    "Accelerometer": {"category": "sensor", "capabilities": ["read-xyz"], "readable": True, "writable": False},
    "Camera": {"category": "sensor", "capabilities": ["read-image", "capture-image"], "readable": True, "writable": False},
    "DistanceSensor": {"category": "sensor", "capabilities": ["read-distance"], "readable": True, "writable": False},
    "Emitter": {"category": "communication", "capabilities": ["emit"], "readable": False, "writable": True},
    "Gyro": {"category": "sensor", "capabilities": ["read-angular-velocity"], "readable": True, "writable": False},
    "LED": {"category": "actuator", "capabilities": ["set-state"], "readable": False, "writable": True},
    "LightSensor": {"category": "sensor", "capabilities": ["read-light"], "readable": True, "writable": False},
    "Motor": {"category": "actuator", "capabilities": ["set-velocity", "set-position"], "readable": False, "writable": True},
    "PositionSensor": {"category": "sensor", "capabilities": ["read-position"], "readable": True, "writable": False},
    "Receiver": {"category": "communication", "capabilities": ["receive"], "readable": True, "writable": False},
    "Speaker": {"category": "actuator", "capabilities": ["speak"], "readable": False, "writable": True},
}


def save_rgba_to_ppm(path: Path, image: bytes, width: int, height: int) -> None:
    with path.open("wb") as handle:
        handle.write(f"P6\n{width} {height}\n255\n".encode("ascii"))
        for y in range(height):
            for x in range(width):
                index = 4 * (y * width + x)
                blue = image[index]
                green = image[index + 1]
                red = image[index + 2]
                handle.write(bytes((red, green, blue)))


class AgentBridge:
    def __init__(self, *, robot: Any, devices: dict[str, Any], default_camera: str):
        self.robot = robot
        self.devices = devices
        self.default_camera = default_camera
        self.client: RuntimeSocketClient = connect_runtime(
            os.environ["WEBOTS_MCP_HOST"],
            int(os.environ["WEBOTS_MCP_PORT"]),
            role="agent",
            name=robot.getName(),
            meta={"default_camera": default_camera},
        )
        self.device_info = [describe_device(name, device) for name, device in sorted(devices.items(), key=lambda item: item[0])]
        self.step_index = 0
        self.paused = False
        self.manual_override: dict[str, Any] | None = None
        self.pending_commands: list[dict[str, Any]] = []

    def begin_step(self) -> tuple[float, float] | None:
        for message in self.client.drain():
            if message.get("kind") != "command":
                continue
            action = message["action"]
            params = message.get("params", {})
            if action == "set_motor_velocity":
                self.manual_override = {
                    "left": float(params["left"]),
                    "right": float(params["right"]),
                    "remaining_steps": int(params.get("duration_steps", 1)),
                }
                self.client.send({"kind": "response", "request_id": message["request_id"], "ok": True, "result": self.manual_override})
            elif action == "clear_manual_override":
                self.manual_override = None
                self.client.send({"kind": "response", "request_id": message["request_id"], "ok": True, "result": {"cleared": True}})
            elif action == "set_paused":
                self.paused = bool(params.get("paused", True))
                self.client.send({"kind": "response", "request_id": message["request_id"], "ok": True, "result": {"paused": self.paused}})
            else:
                self.pending_commands.append(message)

        if self.paused:
            return (0.0, 0.0)
        if self.manual_override:
            override = (float(self.manual_override["left"]), float(self.manual_override["right"]))
            self.manual_override["remaining_steps"] -= 1
            if self.manual_override["remaining_steps"] <= 0:
                self.manual_override = None
            return override
        return None

    def publish_step(
        self,
        *,
        sensors: dict[str, Any],
        metrics: dict[str, Any],
        actuators: dict[str, Any],
        camera_frames: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        camera_frames = camera_frames or {}
        for command in self.pending_commands:
            request_id = command["request_id"]
            action = command["action"]
            params = command.get("params", {})
            try:
                if action == "list_devices":
                    result = self.device_info
                elif action == "get_sensors":
                    result = sensors
                elif action == "capture_camera":
                    camera_name = params.get("camera") or self.default_camera
                    frame = camera_frames[camera_name]
                    target = Path(params["path"])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    save_rgba_to_ppm(target, frame["image"], int(frame["width"]), int(frame["height"]))
                    result = {"path": str(target), "width": frame["width"], "height": frame["height"]}
                else:
                    raise ValueError(f"Unsupported agent command: {action}")
                self.client.send({"kind": "response", "request_id": request_id, "ok": True, "result": result})
            except Exception as exc:
                self.client.send({"kind": "response", "request_id": request_id, "ok": False, "error": str(exc)})
        self.pending_commands.clear()

        self.step_index += 1
        self.client.send(
            {
                "kind": "telemetry",
                "role": "agent",
                "name": self.robot.getName(),
                "devices": self.device_info,
                "state": {
                    "robot_time": round(float(self.robot.getTime()), 6),
                    "step_index": self.step_index,
                    "basic_time_step": int(self.robot.getBasicTimeStep()),
                },
                "sensors": sensors,
                "metrics": metrics,
                "actuators": actuators,
                "meta": {"paused": self.paused, "default_camera": self.default_camera},
            }
        )


class ControllerAgent(AgentBridge):
    """Public controller-side wrapper for Webots MCP integration."""

    @classmethod
    def from_robot(cls, robot: Any, *, default_camera: str, devices: dict[str, Any] | None = None) -> "ControllerAgent":
        return cls(robot=robot, devices=devices or robot.devices, default_camera=default_camera)

    def report_step(
        self,
        *,
        sensors: dict[str, Any],
        metrics: dict[str, Any],
        actuators: dict[str, Any],
        camera_frames: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.publish_step(
            sensors=sensors,
            metrics=metrics,
            actuators=actuators,
            camera_frames=camera_frames,
        )


def describe_device(name: str, device: Any) -> dict[str, Any]:
    device_type = device.__class__.__name__
    defaults = {"category": "unknown", "capabilities": [], "readable": False, "writable": False}
    descriptor = {**defaults, **DEVICE_CAPABILITY_MAP.get(device_type, {})}
    descriptor.update({"name": name, "type": device_type})
    return descriptor
