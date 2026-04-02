from __future__ import annotations

import json
from pathlib import Path

from webots_mcp_kit.diagnostics import collect_runtime_diagnostics
from webots_mcp_kit.models import SessionManifest
from webots_mcp_kit.session_store import SessionStore


def _write_fake_webots_home(root: Path) -> Path:
    home = root / "Webots"
    executable = home / "msys64" / "mingw64" / "bin" / "webots.exe"
    controller_python = home / "lib" / "controller" / "python"
    controller_library = home / "lib" / "controller"
    version_file = home / "resources" / "version.txt"
    executable.parent.mkdir(parents=True, exist_ok=True)
    controller_python.mkdir(parents=True, exist_ok=True)
    controller_library.mkdir(parents=True, exist_ok=True)
    version_file.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("", encoding="utf-8")
    version_file.write_text("R2025a\n", encoding="utf-8")
    return home


def test_collect_runtime_diagnostics_without_session(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WEBOTS_HOME", str(_write_fake_webots_home(tmp_path)))
    monkeypatch.setenv("SESSIONNAME", "Console")
    store = SessionStore(root=tmp_path / "sessions")
    payload = collect_runtime_diagnostics(output_dir=tmp_path / "diag", store=store)
    assert payload["latest_session"] is None
    assert (tmp_path / "diag" / "session.json").exists()
    assert (tmp_path / "diag" / "inspect.json").exists()
    assert (tmp_path / "diag" / "log_inventory.json").exists()
    assert (tmp_path / "diag" / "log_summary.json").exists()
    assert (tmp_path / "diag" / "runtime_environment.json").exists()
    summary = json.loads((tmp_path / "diag" / "summary.json").read_text(encoding="utf-8"))
    assert summary["doctor"]["status"] == "ready"


def test_collect_runtime_diagnostics_with_session(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WEBOTS_HOME", str(_write_fake_webots_home(tmp_path)))
    monkeypatch.setenv("SESSIONNAME", "Console")
    store = SessionStore(root=tmp_path / "sessions")
    session_dir = store.create_session_dir("diagtest")
    manifest = SessionManifest(
        session_id="diagtest",
        host="127.0.0.1",
        port=12345,
        daemon_pid=111,
        status="stopped",
        scenario="line-follower",
        world="world.wbt",
        mode="fast",
        render=False,
        robot_controller="controller.py",
        target_robot_name="epuck-line-follower",
        target_robot_def="EPUCK",
        created_at="2026-03-31T00:00:00Z",
        session_dir=str(session_dir),
        artifacts_dir=str(session_dir / "artifacts"),
        environment={"python_executable": "python.exe", "webots_executable": "webots.exe"},
    )
    store.write_manifest(manifest)
    (session_dir / "artifacts" / "daemon.stdout.log").write_text("ok\n", encoding="utf-8")

    payload = collect_runtime_diagnostics(output_dir=tmp_path / "diag", store=store)
    assert payload["session_id"] == "diagtest"
    assert (tmp_path / "diag" / "inspect.json").exists()
    assert (tmp_path / "diag" / "runtime_environment.json").exists()
    assert payload["inspect"]["manifest"]["session_id"] == "diagtest"
    assert payload["runtime_environment"]["python_executable"] == "python.exe"
