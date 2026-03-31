from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from .environment import build_process_env, repo_root
from .models import SessionManifest, repo_example_controller, repo_example_world
from .session_store import SessionStore
from .utils import choose_free_port, utc_now_iso


def resolve_world_path(world: str | None) -> Path:
    if not world:
        return repo_example_world()
    path = Path(world)
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def resolve_controller_path(controller: str | None) -> Path:
    if not controller or controller == "example":
        return repo_example_controller()
    path = Path(controller)
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def start_session(*, world: str | None, controller: str | None, mode: str, render: bool, timeout: float = 30.0) -> SessionManifest:
    store = SessionStore()
    session_dir = store.create_session_dir()
    session_id = session_dir.name
    artifacts_dir = session_dir / "artifacts"
    host = "127.0.0.1"
    port = choose_free_port(host)
    world_path = resolve_world_path(world)
    controller_path = resolve_controller_path(controller)
    manifest = SessionManifest(
        session_id=session_id,
        host=host,
        port=port,
        daemon_pid=0,
        status="starting",
        world=str(world_path),
        mode=mode,
        render=render,
        robot_controller=str(controller_path),
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

    deadline = time.time() + timeout
    while time.time() < deadline:
        current = store.load_manifest(session_id)
        if current.status == "ready":
            return current
        if current.status == "failed":
            raise RuntimeError(f"Session {session_id} failed to initialize.")
        time.sleep(0.25)
    raise TimeoutError(f"Timed out waiting for session {session_id} to become ready.")
