from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from .benchmarks import get_scenario
from .client import SessionClient
from .environment import build_process_env, repo_root
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
    )
    manifest_path = store.write_manifest(manifest)

    env = build_process_env()
    env["WEBOTS_MCP_MANIFEST"] = str(manifest_path)

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
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    subprocess.Popen(  # noqa: S603
        args,
        cwd=str(repo_root()),
        env=env,
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    timeout = session_start_timeout(timeout)
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = store.load_manifest(session_id)
        if current.status == "ready":
            return current
        if current.status == "failed":
            raise RuntimeError(current.last_error or f"Session {session_id} failed to initialize.")
        time.sleep(0.25)
    current = store.load_manifest(session_id)
    diagnostics = timeout_diagnostics(store, current)
    raise TimeoutError(
        f"Timed out waiting for session {session_id} to become ready after {timeout:.1f}s. "
        f"status={current.status} session_dir={current.session_dir} diagnostics={diagnostics}"
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
        "artifacts": store.list_artifacts(session_id),
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
    }
    webots_stdout = store.artifacts_dir(manifest.session_id) / "webots.stdout.log"
    if webots_stdout.exists():
        try:
            lines = webots_stdout.read_text(encoding="utf-8").splitlines()
            payload["webots_stdout_tail"] = lines[-10:]
        except OSError:
            pass
    return payload
