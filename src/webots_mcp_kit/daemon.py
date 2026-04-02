from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from .benchmarks import get_scenario
from .errors import error_dict
from .environment import build_process_env, current_python, get_webots_environment, repo_root, software_opengl_requested
from .models import RuntimeSnapshot, SessionManifest
from .protocol import encode_message, request_id
from .utils import atomic_write_text, choose_free_port, utc_now_iso


def distance_2d(position: list[float] | tuple[float, ...], target: list[float] | tuple[float, ...]) -> float:
    dx = float(position[0]) - float(target[0])
    dy = float(position[1]) - float(target[1])
    return (dx * dx + dy * dy) ** 0.5


def is_transient_runtime_reset_error(exc: Exception) -> bool:
    return "Connection lost" in str(exc)


class SessionDaemon:
    def __init__(
        self,
        *,
        manifest_path: Path,
        world: Path,
        robot_controller: Path,
        host: str,
        port: int,
        mode: str,
        render: bool,
    ) -> None:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.manifest_path = manifest_path
        self.manifest = SessionManifest(**data)
        self.world = world
        self.robot_controller = robot_controller
        self.host = host
        self.port = port
        self.mode = mode
        self.render = render
        self.scenario_def = get_scenario(self.manifest.scenario)
        self.server: asyncio.AbstractServer | None = None
        self.webots_process: asyncio.subprocess.Process | None = None
        self.controller_processes: dict[str, tuple[asyncio.subprocess.Process, Any, Any]] = {}
        self.runtime_connections: dict[str, asyncio.StreamWriter] = {}
        self.runtime_snapshots: dict[str, RuntimeSnapshot] = {
            "agent": RuntimeSnapshot(role="agent", name=self.manifest.target_robot_name),
            "supervisor": RuntimeSnapshot(role="supervisor", name="kit-supervisor"),
        }
        self.pending_requests: dict[str, asyncio.Future[Any]] = {}
        self.telemetry_event = asyncio.Event()
        self.stop_event = asyncio.Event()
        self.ready_roles = {"agent", "supervisor"}
        self.control_paused = False
        self.webots_port = choose_free_port()
        self.artifacts_dir = Path(self.manifest.artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.webots_stdout_path = self.artifacts_dir / "webots.stdout.log"
        self.webots_stderr_path = self.artifacts_dir / "webots.stderr.log"

    def write_manifest(
        self,
        *,
        status: str | None = None,
        last_error: str | None = None,
        last_error_code: str | None = None,
        last_error_details: dict[str, Any] | None = None,
    ) -> None:
        if status is not None:
            self.manifest.status = status
            if status in {"stopped", "failed"}:
                self.manifest.stopped_at = utc_now_iso()
        if last_error is not None:
            self.manifest.last_error = last_error
        if last_error_code is not None:
            self.manifest.last_error_code = last_error_code
        if last_error_details is not None:
            self.manifest.last_error_details = last_error_details
        self.manifest.daemon_pid = os.getpid()
        self.manifest.host = self.host
        self.manifest.port = self.port
        self.manifest.mode = self.mode
        self.manifest.render = self.render
        self.manifest.world = str(self.world)
        self.manifest.robot_controller = str(self.robot_controller)
        self.manifest.runtime_summary = self.runtime_summary()
        atomic_write_text(self.manifest_path, json.dumps(self.manifest.to_dict(), indent=2), encoding="utf-8")

    def runtime_summary(self) -> dict[str, Any]:
        return {
            role: {
                "name": snapshot.name,
                "connected": snapshot.connected,
                "meta": snapshot.meta,
                "state_keys": sorted(snapshot.state),
                "sensor_keys": sorted(snapshot.sensors),
                "metric_keys": sorted(snapshot.metrics),
                "actuator_keys": sorted(snapshot.actuators),
                "device_count": len(snapshot.devices),
            }
            for role, snapshot in self.runtime_snapshots.items()
        }

    async def run(self) -> None:
        self.write_manifest(status="starting")
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        stdout_task: asyncio.Task[Any] | None = None
        stderr_task: asyncio.Task[Any] | None = None
        try:
            await self.start_webots()
            stdout_task = asyncio.create_task(self.consume_webots_stdout())
            stderr_task = asyncio.create_task(self.consume_webots_stderr())
            await self.wait_for_stop()
        except Exception as exc:
            self.write_manifest(
                status="failed",
                last_error=str(exc),
                last_error_code="daemon-run-failed",
                last_error_details={"exception_type": exc.__class__.__name__},
            )
            raise
        finally:
            self.stop_event.set()
            for task in (stdout_task, stderr_task):
                if task:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
            await self.shutdown()

    async def wait_for_stop(self) -> None:
        assert self.webots_process is not None
        stop_task = asyncio.create_task(self.stop_event.wait())
        webots_task = asyncio.create_task(self.webots_process.wait())
        done, pending = await asyncio.wait({stop_task, webots_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        if webots_task in done and not self.stop_event.is_set():
            if self.manifest.status == "ready":
                error = error_dict(
                    "webots-unexpected-exit",
                    "Webots process exited unexpectedly after the session became ready.",
                    details={"webots_stderr_tail": self.read_log_tail(self.webots_stderr_path), "webots_stdout_tail": self.read_log_tail(self.webots_stdout_path)},
                )
                self.write_manifest(
                    status="stopped",
                    last_error=error["message"],
                    last_error_code=error["code"],
                    last_error_details=error["details"],
                )
            else:
                error = self.classify_early_webots_exit()
                self.write_manifest(
                    status="failed",
                    last_error=error["message"],
                    last_error_code=error["code"],
                    last_error_details=error["details"],
                )
        else:
            self.write_manifest(status="stopping")

    async def shutdown(self) -> None:
        for process, stdout_handle, stderr_handle in list(self.controller_processes.values()):
            with contextlib.suppress(ProcessLookupError):
                if process.returncode is None:
                    process.terminate()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(process.wait(), timeout=5.0)
            stdout_handle.close()
            stderr_handle.close()

        if self.webots_process and self.webots_process.returncode is None:
            self.webots_process.terminate()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.webots_process.wait(), timeout=8.0)

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        if self.manifest.status != "failed":
            self.write_manifest(status="stopped")

    async def start_webots(self) -> None:
        webots = get_webots_environment()
        webots_env = build_process_env(prefer_software_opengl=(not self.render and software_opengl_requested()))
        self.manifest.environment["webots_launch"] = {
            "qt_opengl": webots_env.get("QT_OPENGL"),
            "software_opengl_dir": webots_env.get("WEBOTS_KIT_SOFTWARE_OPENGL_DIR"),
            "runner_session_name": os.environ.get("SESSIONNAME"),
            "runner_user": os.environ.get("USERNAME"),
        }
        self.write_manifest()
        args = [
            str(webots.webots_executable),
            f"--port={self.webots_port}",
            "--batch",
            "--stdout",
            "--stderr",
            "--extern-urls",
            f"--mode={self.mode}",
        ]
        if not self.render:
            args.append("--no-rendering")
        args.append(str(self.world))
        self.webots_process = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(repo_root()),
            env=webots_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def consume_webots_stdout(self) -> None:
        assert self.webots_process is not None
        assert self.webots_process.stdout is not None
        with self.webots_stdout_path.open("w", encoding="utf-8") as log_file:
            while not self.webots_process.stdout.at_eof():
                line = await self.webots_process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                log_file.write(text + "\n")
                log_file.flush()
                if text.startswith("ipc://"):
                    await self.launch_runtime_for_url(text)

    async def consume_webots_stderr(self) -> None:
        assert self.webots_process is not None
        assert self.webots_process.stderr is not None
        with self.webots_stderr_path.open("w", encoding="utf-8") as log_file:
            while not self.webots_process.stderr.at_eof():
                line = await self.webots_process.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                log_file.write(text + "\n")
                log_file.flush()

    async def launch_runtime_for_url(self, url: str) -> None:
        name = next((part for part in reversed(url.split("/")) if part and ":" not in part), "")
        if name == self.manifest.target_robot_name:
            command = [current_python(), str(self.robot_controller)]
            cwd = str(self.robot_controller.parent)
        elif name == "kit-supervisor":
            command = [current_python(), "-m", "webots_mcp_kit.runtime.supervisor_main"]
            cwd = str(repo_root())
        else:
            return

        stdout_path = self.artifacts_dir / f"{name}.stdout.log"
        stderr_path = self.artifacts_dir / f"{name}.stderr.log"
        stdout_handle = stdout_path.open("w", encoding="utf-8")
        stderr_handle = stderr_path.open("w", encoding="utf-8")
        env = build_process_env()
        env.update(
            {
                "WEBOTS_CONTROLLER_URL": url,
                "WEBOTS_MCP_HOST": self.host,
                "WEBOTS_MCP_PORT": str(self.port),
                "WEBOTS_MCP_SESSION_ID": self.manifest.session_id,
                "WEBOTS_MCP_SESSION_DIR": self.manifest.session_dir,
                "WEBOTS_TARGET_ROBOT": self.manifest.target_robot_name,
                "WEBOTS_TARGET_DEF": self.manifest.target_robot_def,
                "WEBOTS_MCP_SCENARIO": self.manifest.scenario,
            }
        )
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=env,
            stdout=stdout_handle,
            stderr=stderr_handle,
        )
        self.controller_processes[name] = (process, stdout_handle, stderr_handle)

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = await reader.readline()
            if not line:
                return
            message = json.loads(line.decode("utf-8"))
            if message.get("kind") == "runtime_register":
                await self.handle_runtime_connection(message, reader, writer)
                return
            if message.get("kind") == "admin_request":
                response = await self.handle_admin_request(message)
                writer.write(encode_message(response))
                await writer.drain()
                return
            writer.write(encode_message({"kind": "admin_response", "ok": False, "error": "Unknown message kind"}))
            await writer.drain()
        finally:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()

    async def handle_runtime_connection(
        self,
        register_message: dict[str, Any],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        role = register_message["role"]
        snapshot = self.runtime_snapshots.get(role, RuntimeSnapshot(role=role, name=register_message["name"]))
        snapshot.name = register_message["name"]
        snapshot.connected = True
        snapshot.meta = register_message.get("meta", {})
        self.runtime_snapshots[role] = snapshot
        self.runtime_connections[role] = writer
        self.write_manifest()
        self.maybe_mark_ready()

        while True:
            line = await reader.readline()
            if not line:
                break
            message = json.loads(line.decode("utf-8"))
            if message.get("kind") == "telemetry":
                self.apply_telemetry(role, message)
            elif message.get("kind") == "response":
                future = self.pending_requests.pop(message["request_id"], None)
                if future and not future.done():
                    if message.get("ok", False):
                        future.set_result(message.get("result"))
                    else:
                        future.set_exception(RuntimeError(message.get("error", "Runtime command failed")))

        snapshot.connected = False
        self.runtime_snapshots[role] = snapshot
        self.runtime_connections.pop(role, None)
        self.write_manifest()

    def maybe_mark_ready(self) -> None:
        if self.ready_roles.issubset(self.runtime_connections):
            self.write_manifest(status="ready")

    def apply_telemetry(self, role: str, message: dict[str, Any]) -> None:
        snapshot = self.runtime_snapshots.get(role, RuntimeSnapshot(role=role, name=message.get("name", role)))
        snapshot.connected = True
        if "devices" in message:
            snapshot.devices = message["devices"]
        if "state" in message:
            snapshot.state = message["state"]
        if "sensors" in message:
            snapshot.sensors = message["sensors"]
        if "metrics" in message:
            snapshot.metrics = message["metrics"]
        if "actuators" in message:
            snapshot.actuators = message["actuators"]
        if "meta" in message:
            snapshot.meta = message["meta"]
        self.runtime_snapshots[role] = snapshot
        self.write_manifest()
        self.telemetry_event.set()

    async def send_runtime_command(self, role: str, action: str, params: dict[str, Any] | None = None, timeout: float = 10.0) -> Any:
        writer = self.runtime_connections.get(role)
        if writer is None:
            raise RuntimeError(f"Runtime '{role}' is not connected.")
        req_id = request_id()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self.pending_requests[req_id] = future
        writer.write(encode_message({"kind": "command", "request_id": req_id, "action": action, "params": params or {}}))
        await writer.drain()
        return await asyncio.wait_for(future, timeout=timeout)

    async def wait_for_steps(self, steps: int, timeout: float | None = None) -> dict[str, Any]:
        timeout = timeout or max(5.0, steps * 0.3)
        start = int(self.runtime_snapshots["agent"].state.get("step_index", 0))
        target = start + max(steps, 1)
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            current = int(self.runtime_snapshots["agent"].state.get("step_index", 0))
            if current >= target:
                return {"start_step": start, "end_step": current}
            self.telemetry_event.clear()
            remaining = deadline - asyncio.get_running_loop().time()
            await asyncio.wait_for(self.telemetry_event.wait(), timeout=max(0.1, remaining))
        raise TimeoutError(f"Timed out waiting for {steps} Webots steps.")

    async def handle_admin_request(self, message: dict[str, Any]) -> dict[str, Any]:
        action = message["action"]
        params = message.get("params", {})
        try:
            if action == "ping":
                result = {"status": self.manifest.status, "session_id": self.manifest.session_id}
            elif action == "stop":
                self.stop_event.set()
                result = {"session_id": self.manifest.session_id, "status": "stopping"}
            elif action == "list_robots":
                agent = self.runtime_snapshots["agent"]
                result = [{"name": agent.name, "def": self.manifest.target_robot_def, "connected": agent.connected}]
            elif action == "list_devices":
                result = {
                    "robot": self.manifest.target_robot_name,
                    "scenario": self.manifest.scenario,
                    "devices": self.runtime_snapshots["agent"].devices,
                }
            elif action == "get_state":
                result = {
                    "session": self.manifest.to_dict(),
                    "session_state": {
                        "status": self.manifest.status,
                        "scenario": self.manifest.scenario,
                        "target_robot_name": self.manifest.target_robot_name,
                        "last_error_code": self.manifest.last_error_code,
                        "last_error": self.manifest.last_error,
                    },
                    "control_paused": self.control_paused,
                    "runtime_summary": self.runtime_summary(),
                    "runtimes": {role: snapshot.to_dict() for role, snapshot in self.runtime_snapshots.items()},
                }
            elif action == "get_sensors":
                snapshot = self.runtime_snapshots["agent"]
                result = {
                    "robot": snapshot.name,
                    "scenario": self.manifest.scenario,
                    "state": snapshot.state,
                    "sensors": snapshot.sensors,
                    "metrics": snapshot.metrics,
                    "actuators": snapshot.actuators,
                    "meta": snapshot.meta,
                }
            elif action == "capture_camera":
                default_camera = self.runtime_snapshots["agent"].meta.get("default_camera", "camera")
                target = params.get("path") or str(self.artifacts_dir / f"capture-{request_id()}.ppm")
                result = await self.send_runtime_command(
                    "agent",
                    "capture_camera",
                    {"camera": params.get("camera") or default_camera, "path": target},
                )
            elif action == "set_motor_velocity":
                self.control_paused = False
                result = await self.send_runtime_command(
                    "agent",
                    "set_motor_velocity",
                    {
                        "left": float(params["left"]),
                        "right": float(params["right"]),
                        "duration_steps": int(params.get("duration_steps", 1)),
                    },
                )
            elif action == "pause_resume":
                self.control_paused = bool(params.get("paused", True))
                result = await self.send_runtime_command("agent", "set_paused", {"paused": self.control_paused})
            elif action == "reset":
                self.control_paused = False
                with contextlib.suppress(Exception):
                    await self.send_runtime_command("agent", "clear_manual_override", {})
                result = await self.send_runtime_command("supervisor", "reset", {}, timeout=15.0)
            elif action == "step":
                result = await self.wait_for_steps(int(params.get("steps", 1)))
            elif action == "run_benchmark":
                result = await self.run_benchmark(
                    benchmark=params.get("benchmark", self.manifest.scenario),
                    duration_s=float(params.get("duration_s", 20.0)),
                    fail_streak=int(params.get("line_loss_streak_fail", 25)),
                )
            else:
                raise ValueError(f"Unsupported admin action: {action}")
            return {"kind": "admin_response", "id": message["id"], "ok": True, "result": result}
        except Exception as exc:
            return {
                "kind": "admin_response",
                "id": message["id"],
                "ok": False,
                "error": error_dict(
                    "admin-request-failed",
                    str(exc),
                    details={"action": action, "exception_type": exc.__class__.__name__},
                ),
            }

    async def run_benchmark(self, *, benchmark: str, duration_s: float, fail_streak: int) -> dict[str, Any]:
        notes: list[str] = []
        scenario_name = benchmark if benchmark in {"line-follower", "obstacle-avoidance", "waypoint-nav"} else self.manifest.scenario
        scenario_def = get_scenario(scenario_name)
        thresholds = scenario_def.benchmark_thresholds
        try:
            await self.send_runtime_command("agent", "set_paused", {"paused": False})
            await self.send_runtime_command("agent", "clear_manual_override", {})
        except Exception as exc:
            if not is_transient_runtime_reset_error(exc):
                notes.append(f"agent-reset-warning: {exc}")
        try:
            await self.send_runtime_command("supervisor", "reset", {}, timeout=15.0)
        except Exception as exc:
            if not is_transient_runtime_reset_error(exc):
                notes.append(f"supervisor-reset-warning: {exc}")

        await self.wait_for_steps(5, timeout=10.0)
        snapshot = self.runtime_snapshots["agent"]
        start_time = float(snapshot.state.get("robot_time", 0.0))
        start_step = int(snapshot.state.get("step_index", 0))
        baseline_contact_points = int(self.runtime_snapshots["supervisor"].state.get("contact_points_count", 0))
        line_loss_events = 0
        current_streak = 0
        max_streak = 0
        center_sum = 0.0
        ir_sum = 0.0
        obstacle_pressure_sum = 0.0
        mean_forward_speed_sum = 0.0
        collision_events = 0
        sample_count = 0
        passed = True
        previous_collision = False
        previous_position = self.runtime_snapshots["supervisor"].state.get("robot_position")
        travelled_distance = 0.0
        target_distance = None
        target_position = thresholds.get("target_position")
        target_reached = False
        fail_streak = int(thresholds.get("line_loss_streak_fail", fail_streak))
        max_collision_events = int(thresholds.get("max_collision_events", 0))
        min_travelled_distance = float(thresholds.get("min_travelled_distance", 0.0))
        min_mean_forward_speed = float(thresholds.get("min_mean_forward_speed", 0.0))
        target_tolerance = float(thresholds.get("target_tolerance", 0.0))

        while True:
            self.telemetry_event.clear()
            await asyncio.wait_for(self.telemetry_event.wait(), timeout=max(5.0, duration_s / 2))
            snapshot = self.runtime_snapshots["agent"]
            metrics = snapshot.metrics
            supervisor_state = self.runtime_snapshots["supervisor"].state
            if scenario_name == "line-follower":
                line_visible = bool(metrics.get("line_visible", False))
                if line_visible:
                    current_streak = 0
                else:
                    current_streak += 1
                    if current_streak == 1:
                        line_loss_events += 1
                max_streak = max(max_streak, current_streak)
            else:
                contact_points_count = int(supervisor_state.get("contact_points_count", 0))
                has_collision = contact_points_count > baseline_contact_points + 2
                if has_collision and not previous_collision:
                    collision_events += 1
                previous_collision = has_collision
                position = supervisor_state.get("robot_position")
                if previous_position and position:
                    dx = float(position[0]) - float(previous_position[0])
                    dy = float(position[1]) - float(previous_position[1])
                    travelled_distance += (dx * dx + dy * dy) ** 0.5
                previous_position = position
                if scenario_name == "waypoint-nav" and position and target_position:
                    target_distance = distance_2d(position, target_position)
                    if target_distance <= target_tolerance:
                        target_reached = True
            center_sum += abs(float(metrics.get("center_error", 0.0)))
            ir_sum += abs(float(metrics.get("ir_balance_error", 0.0)))
            obstacle_pressure_sum += float(metrics.get("obstacle_pressure", 0.0))
            mean_forward_speed_sum += abs(float(metrics.get("mean_forward_speed", 0.0)))
            sample_count += 1

            sim_time = float(snapshot.state.get("robot_time", 0.0))
            if scenario_name == "line-follower" and max_streak >= fail_streak:
                passed = False
                notes.append("line-loss-threshold-reached")
                break
            if scenario_name in {"obstacle-avoidance", "waypoint-nav"} and collision_events > max_collision_events:
                passed = False
                notes.append("collision-detected")
                break
            if scenario_name == "waypoint-nav" and target_reached:
                notes.append("target-reached")
                break
            if sim_time - start_time >= duration_s:
                break

        if scenario_name == "obstacle-avoidance" and travelled_distance < min_travelled_distance:
            notes.append("low-travel-distance")
        if scenario_name == "waypoint-nav" and not target_reached and travelled_distance < min_travelled_distance:
            notes.append("low-travel-distance")
        mean_forward_speed = mean_forward_speed_sum / max(sample_count, 1)
        if scenario_name in {"obstacle-avoidance", "waypoint-nav"} and mean_forward_speed < min_mean_forward_speed:
            passed = False
            notes.append("insufficient-forward-speed")
        if scenario_name == "waypoint-nav" and not target_reached:
            passed = False
            notes.append("target-not-reached")

        return {
            "benchmark": scenario_name,
            "world": self.manifest.world,
            "controller": self.manifest.robot_controller,
            "session_mode": self.manifest.mode,
            "sim_time_s": round(float(self.runtime_snapshots["agent"].state.get("robot_time", 0.0)) - start_time, 3),
            "steps": int(self.runtime_snapshots["agent"].state.get("step_index", 0)) - start_step,
            "line_loss_events": line_loss_events,
            "max_line_loss_streak": max_streak,
            "mean_center_error": round(center_sum / max(sample_count, 1), 6),
            "ir_balance_error": round(ir_sum / max(sample_count, 1), 6),
            "pass": passed,
            "artifacts": {
                "stdout": str(self.webots_stdout_path),
                "stderr": str(self.webots_stderr_path),
                "frames_dir": str(self.artifacts_dir),
            },
            "notes": notes,
            "extra_metrics": {
                "collision_events": collision_events,
                "travelled_distance": round(travelled_distance, 6),
                "baseline_contact_points": baseline_contact_points,
                "mean_obstacle_pressure": round(obstacle_pressure_sum / max(sample_count, 1), 6),
                "mean_forward_speed": round(mean_forward_speed, 6),
                "contact_points_count": int(self.runtime_snapshots["supervisor"].state.get("contact_points_count", 0)),
                "target_position": list(target_position) if target_position else None,
                "target_distance": round(target_distance, 6) if target_distance is not None else None,
                "target_reached": target_reached,
            },
        }

    def read_log_tail(self, path: Path, tail: int = 10) -> list[str]:
        if not path.exists():
            return []
        try:
            return path.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]
        except OSError:
            return []

    def classify_early_webots_exit(self) -> dict[str, Any]:
        stderr_tail = self.read_log_tail(self.webots_stderr_path)
        stdout_tail = self.read_log_tail(self.webots_stdout_path)
        lower_stderr = "\n".join(stderr_tail).lower()
        runtime_summary = self.runtime_summary()
        if "failed to load and resolve wgl/opengl functions" in lower_stderr or "could not initialize the rendering system" in lower_stderr:
            return error_dict(
                "render-init-failed",
                "Webots could not initialize the rendering system before the runtimes connected.",
                details={"webots_stderr_tail": stderr_tail, "webots_stdout_tail": stdout_tail, "runtime_summary": runtime_summary},
            )
        if "requires opengl 3.3" in lower_stderr:
            return error_dict(
                "render-init-failed",
                "Webots requires an OpenGL 3.3 context, but the current runner session could not initialize one.",
                details={"webots_stderr_tail": stderr_tail, "webots_stdout_tail": stdout_tail, "runtime_summary": runtime_summary},
            )
        if self.runtime_connections.get("supervisor") and not self.runtime_connections.get("agent"):
            return error_dict(
                "agent-connect-timeout",
                "The agent runtime did not connect before Webots exited.",
                details={"webots_stderr_tail": stderr_tail, "webots_stdout_tail": stdout_tail, "runtime_summary": runtime_summary},
            )
        if self.runtime_connections.get("agent") and not self.runtime_connections.get("supervisor"):
            return error_dict(
                "supervisor-connect-timeout",
                "The supervisor runtime did not connect before Webots exited.",
                details={"webots_stderr_tail": stderr_tail, "webots_stdout_tail": stdout_tail, "runtime_summary": runtime_summary},
            )
        return error_dict(
            "controller-launch-failed",
            "Webots exited before the controller runtimes connected.",
            details={"webots_stderr_tail": stderr_tail, "webots_stdout_tail": stdout_tail, "runtime_summary": runtime_summary},
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-file", required=True)
    parser.add_argument("--world", required=True)
    parser.add_argument("--robot-controller", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--target-robot-name", required=True)
    parser.add_argument("--target-robot-def", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--mode", default="fast")
    parser.add_argument("--render", choices=["on", "off"], default="off")
    return parser.parse_args(argv)


async def async_main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    daemon = SessionDaemon(
        manifest_path=Path(args.session_file),
        world=Path(args.world),
        robot_controller=Path(args.robot_controller),
        host=args.host,
        port=args.port,
        mode=args.mode,
        render=args.render == "on",
    )
    await daemon.run()


def main(argv: list[str] | None = None) -> None:
    asyncio.run(async_main(argv))


if __name__ == "__main__":
    main(sys.argv[1:])
