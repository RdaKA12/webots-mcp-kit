from __future__ import annotations

import json

from webots_mcp_kit.launcher import inspect_session
from webots_mcp_kit.models import SessionManifest
from webots_mcp_kit.session_store import SessionStore


def test_inspect_session_includes_environment_runtime_and_logs(tmp_path) -> None:
    store = SessionStore(root=tmp_path / "sessions")
    session_dir = store.create_session_dir("inspecttest")
    manifest = SessionManifest(
        session_id="inspecttest",
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
        last_error="render failed",
        last_error_code="render-init-failed",
        last_error_details={"detail": "gpu"},
        environment={"webots_version": "R2025a", "python_executable": "python"},
        runtime_summary={"agent": {"connected": False}},
    )
    store.write_manifest(manifest)
    (session_dir / "artifacts" / "daemon.stdout.log").write_text("daemon ok\n", encoding="utf-8")
    (session_dir / "artifacts" / "webots.stdout.log").write_text("webots ok\n", encoding="utf-8")

    payload = inspect_session("inspecttest", store=store)

    assert payload["manifest"]["environment"]["webots_version"] == "R2025a"
    assert payload["manifest"]["runtime_summary"]["agent"]["connected"] is False
    assert payload["session_state"]["last_error_code"] == "render-init-failed"
    assert any(item["name"] == "daemon.stdout.log" for item in payload["logs"])
    assert payload["log_summary"]["daemon.stdout.log"] == ["daemon ok"]
