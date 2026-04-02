from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .benchmarks import get_scenario
from .client import SessionClient
from .errors import KitError, error_dict
from .environment import build_process_env, describe_launch_environment, get_webots_environment, repo_root, software_opengl_requested
from .models import SessionManifest
from .session_store import SessionStore
from .utils import choose_free_port, utc_now_iso


def resolve_world_path(world: str | None, scenario: str) -> Path:
    if not world:
        return get_scenario(scenario).world
    path = Path(world)
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def resolve_controller_path(controller: str | None, scenario: str) -> Path:
    if not controller or controller == "example":
        return get_scenario(scenario).controller
    path = Path(controller)
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def start_session(
    *,
    world: str | None,
    controller: str | None,
    mode: str,
    render: bool,
    scenario: str = "line-follower",
    robot_name: str | None = None,
    robot_def: str | None = None,
    timeout: float = 30.0,
) -> SessionManifest:
    store = SessionStore()
    session_dir = store.create_session_dir()
    session_id = session_dir.name
    artifacts_dir = session_dir / "artifacts"
    host = "127.0.0.1"
    port = choose_free_port(host)
    scenario_def = get_scenario(scenario)
    world_path = resolve_world_path(world, scenario)
    controller_path = resolve_controller_path(controller, scenario)
    environment = build_environment_snapshot(world_path=world_path, controller_path=controller_path, scenario=scenario, mode=mode, render=render)
    manifest = SessionManifest(
        session_id=session_id,
        host=host,
        port=port,
        daemon_pid=0,
        status="starting",
        scenario=scenario,
        world=str(world_path),
        mode=mode,
        render=render,
        robot_controller=str(controller_path),
        target_robot_name=robot_name or scenario_def.target_robot_name,
        target_robot_def=robot_def or scenario_def.target_robot_def,
        created_at=utc_now_iso(),
        session_dir=str(session_dir),
        artifacts_dir=str(artifacts_dir),
        environment=environment,
    )
    manifest_path = store.write_manifest(manifest)

    env = build_process_env()
    env["WEBOTS_MCP_MANIFEST"] = str(manifest_path)

    daemon_stdout_path = artifacts_dir / "daemon.stdout.log"
    daemon_stderr_path = artifacts_dir / "daemon.stderr.log"
    daemon_stdout = daemon_stdout_path.open("w", encoding="utf-8")
    daemon_stderr = daemon_stderr_path.open("w", encoding="utf-8")

    args = [
        sys.executable,
        "-m",
        "webots_mcp_kit.daemon",
        "--session-file",
        str(manifest_path),
        "--world",
        str(world_path),
        "--robot-controller",
        str(controller_path),
        "--scenario",
        scenario,
        "--target-robot-name",
        manifest.target_robot_name,
        "--target-robot-def",
        manifest.target_robot_def,
        "--host",
        host,
        "--port",
        str(port),
        "--mode",
        mode,
        "--render",
        "on" if render else "off",
    ]
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(  # noqa: S603
            args,
            cwd=str(repo_root()),
            env=env,
            creationflags=creationflags,
            stdout=daemon_stdout,
            stderr=daemon_stderr,
        )
    finally:
        daemon_stdout.close()
        daemon_stderr.close()

    timeout = session_start_timeout(timeout)
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = store.load_manifest(session_id)
        if current.status == "ready":
            return current
        if current.status == "failed":
            raise error_from_manifest(current)
        time.sleep(0.25)
    current = store.load_manifest(session_id)
    diagnostics = timeout_diagnostics(store, current)
    timeout_error = classify_start_timeout(current, diagnostics)
    raise KitError(
        timeout_error["code"],
        timeout_error["message"],
        details=timeout_error["details"],
        retriable=True,
    )


def stop_session(session_id: str, timeout: float = 20.0) -> SessionManifest:
    store = SessionStore()
    manifest = store.load_manifest(session_id)
    if manifest.status not in {"stopped", "failed"}:
        try:
            SessionClient(manifest).request("stop", timeout=10.0)
        except Exception:
            pass
    return store.wait_for_status(session_id, {"stopped", "failed"}, timeout=timeout)


def inspect_session(session_id: str) -> dict[str, object]:
    store = SessionStore()
    manifest = store.load_manifest(session_id)
    payload: dict[str, object] = {
        "manifest": manifest.to_dict(),
        "session_state": {
            "status": manifest.status,
            "created_at": manifest.created_at,
            "stopped_at": manifest.stopped_at,
            "last_error_code": manifest.last_error_code,
            "last_error": manifest.last_error,
            "target_robot_name": manifest.target_robot_name,
            "scenario": manifest.scenario,
        },
        "artifacts": store.list_artifacts(session_id),
        "logs": store.log_inventory(session_id),
        "log_summary": store.log_summary(session_id),
    }
    if manifest.status in {"ready", "starting", "stopping"}:
        try:
            payload["runtime_state"] = SessionClient(manifest).request("get_state", timeout=5.0)
        except Exception as exc:
            payload["runtime_error"] = str(exc)
    return payload


def session_start_timeout(default: float) -> float:
    raw = os.environ.get("WEBOTS_KIT_SESSION_START_TIMEOUT")
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def timeout_diagnostics(store: SessionStore, manifest: SessionManifest) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifacts_dir": manifest.artifacts_dir,
        "artifacts": store.list_artifacts(manifest.session_id),
        "logs": store.log_inventory(manifest.session_id),
        "runtime_summary": manifest.runtime_summary,
        "environment": manifest.environment,
        "session_state": {
            "status": manifest.status,
            "last_error_code": manifest.last_error_code,
            "last_error": manifest.last_error,
        },
    }
    for log_name in ("daemon.stdout.log", "daemon.stderr.log", "webots.stdout.log", "webots.stderr.log"):
        log_path = store.artifacts_dir(manifest.session_id) / log_name
        if not log_path.exists():
            continue
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
            payload[f"{log_name}_tail"] = lines[-10:]
        except OSError:
            continue
    return payload


def classify_start_timeout(manifest: SessionManifest, diagnostics: dict[str, object]) -> dict[str, Any]:
    runtime_summary = manifest.runtime_summary if isinstance(manifest.runtime_summary, dict) else {}
    agent = runtime_summary.get("agent") if isinstance(runtime_summary.get("agent"), dict) else {}
    supervisor = runtime_summary.get("supervisor") if isinstance(runtime_summary.get("supervisor"), dict) else {}
    details = {
        "session_id": manifest.session_id,
        "status": manifest.status,
        "session_dir": manifest.session_dir,
        "artifacts_dir": manifest.artifacts_dir,
        "runtime_summary": runtime_summary,
        "diagnostics": diagnostics,
    }
    if supervisor.get("connected") and not agent.get("connected"):
        return error_dict(
            "agent-connect-timeout",
            f"Agent runtime did not connect before timeout for session {manifest.session_id}.",
            details=details,
            retriable=True,
        )
    if agent.get("connected") and not supervisor.get("connected"):
        return error_dict(
            "supervisor-connect-timeout",
            f"Supervisor runtime did not connect before timeout for session {manifest.session_id}.",
            details=details,
            retriable=True,
        )
    return error_dict(
        "session-start-timeout",
        f"Timed out waiting for session {manifest.session_id} to become ready.",
        details=details,
        retriable=True,
    )


def error_from_manifest(manifest: SessionManifest) -> KitError:
    return KitError(
        manifest.last_error_code or "session-start-failed",
        manifest.last_error or f"Session {manifest.session_id} failed to initialize.",
        details={
            "session_id": manifest.session_id,
            "status": manifest.status,
            "session_dir": manifest.session_dir,
            "artifacts_dir": manifest.artifacts_dir,
            "last_error_details": manifest.last_error_details,
            "runtime_summary": manifest.runtime_summary,
            "environment": manifest.environment,
        },
        retriable=(manifest.last_error_code or "").endswith("timeout"),
    )


def build_environment_snapshot(
    *,
    world_path: Path,
    controller_path: Path,
    scenario: str,
    mode: str,
    render: bool,
) -> dict[str, Any]:
    webots = get_webots_environment()
    return {
        "python_executable": sys.executable,
        "webots_home": str(webots.webots_home),
        "webots_executable": str(webots.webots_executable),
        "webots_version": webots.version,
        "controller_python_path": str(webots.controller_python_path),
        "scenario": scenario,
        "world_path": str(world_path),
        "controller_path": str(controller_path),
        "mode": mode,
        "render": render,
        "session_start_timeout_s": session_start_timeout(30.0),
        "launch_context": describe_launch_environment(prefer_software_opengl=(not render and software_opengl_requested())),
    }
