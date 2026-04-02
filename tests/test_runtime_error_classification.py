from __future__ import annotations

import json
from pathlib import Path

from webots_mcp_kit.daemon import SessionDaemon
from webots_mcp_kit.errors import KitError, STABLE_RUNTIME_ERROR_CODES, error_dict, error_from_exception
from webots_mcp_kit.launcher import classify_start_timeout, error_from_manifest
from webots_mcp_kit.models import SessionManifest


def _manifest(session_dir: Path) -> SessionManifest:
    return SessionManifest(
        session_id="runtimeerr",
        host="127.0.0.1",
        port=12345,
        daemon_pid=111,
        status="starting",
        scenario="line-follower",
        world="world.wbt",
        mode="fast",
        render=False,
        robot_controller="controller.py",
        target_robot_name="epuck-line-follower",
        target_robot_def="EPUCK",
        created_at="2026-04-02T00:00:00Z",
        session_dir=str(session_dir),
        artifacts_dir=str(session_dir / "artifacts"),
    )


def test_classify_start_timeout_prefers_missing_agent() -> None:
    manifest = SessionManifest(
        session_id="s1",
        host="127.0.0.1",
        port=1,
        daemon_pid=1,
        status="starting",
        scenario="line-follower",
        world="world",
        mode="fast",
        render=False,
        robot_controller="controller.py",
        target_robot_name="robot",
        target_robot_def="ROBOT",
        created_at="2026-04-02T00:00:00Z",
        session_dir="session",
        artifacts_dir="artifacts",
        runtime_summary={"agent": {"connected": False}, "supervisor": {"connected": True}},
    )
    payload = classify_start_timeout(manifest, {"logs": []})
    assert payload["code"] == "agent-connect-timeout"


def test_error_from_manifest_uses_structured_fields() -> None:
    manifest = SessionManifest(
        session_id="s2",
        host="127.0.0.1",
        port=1,
        daemon_pid=1,
        status="failed",
        scenario="line-follower",
        world="world",
        mode="fast",
        render=False,
        robot_controller="controller.py",
        target_robot_name="robot",
        target_robot_def="ROBOT",
        created_at="2026-04-02T00:00:00Z",
        session_dir="session",
        artifacts_dir="artifacts",
        last_error="Render init failed.",
        last_error_code="render-init-failed",
        last_error_details={"webots_stderr_tail": ["OpenGL failed"]},
    )
    exc = error_from_manifest(manifest)
    assert exc.code == "render-init-failed"
    assert exc.details["last_error_details"]["webots_stderr_tail"] == ["OpenGL failed"]


def test_classify_early_webots_exit_detects_render_failure(tmp_path: Path) -> None:
    session_dir = tmp_path / "sessions" / "runtimeerr"
    (session_dir / "artifacts").mkdir(parents=True)
    manifest_path = session_dir / "session.json"
    manifest = _manifest(session_dir)
    manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    daemon = SessionDaemon(
        manifest_path=manifest_path,
        world=Path("world.wbt"),
        robot_controller=Path("controller.py"),
        host="127.0.0.1",
        port=5555,
        mode="fast",
        render=False,
    )
    daemon.webots_stderr_path.write_text("FATAL: Webots could not initialize the rendering system.\n", encoding="utf-8")
    payload = daemon.classify_early_webots_exit()
    assert payload["code"] == "render-init-failed"


def test_error_from_exception_preserves_structured_runtime_codes() -> None:
    payload = error_from_exception(
        RuntimeError(error_dict("render-init-failed", "Render init failed.", details={"session_id": "s1"})),
        fallback_code="admin-request-failed",
        fallback_message="Admin request failed.",
        details={"action": "capture_camera"},
    )
    assert payload["code"] == "render-init-failed"
    assert payload["details"]["session_id"] == "s1"
    assert payload["details"]["action"] == "capture_camera"


def test_error_from_exception_preserves_kit_error_codes() -> None:
    payload = error_from_exception(
        KitError("supervisor-connect-timeout", "Supervisor did not connect.", details={"session_id": "s2"}, retriable=True),
        fallback_code="admin-request-failed",
        fallback_message="Admin request failed.",
        details={"action": "reset"},
    )
    assert payload["code"] == "supervisor-connect-timeout"
    assert payload["retriable"] is True
    assert payload["details"]["session_id"] == "s2"
    assert payload["details"]["action"] == "reset"


def test_stable_runtime_error_codes_cover_public_runtime_contract() -> None:
    assert STABLE_RUNTIME_ERROR_CODES == (
        "render-init-failed",
        "controller-launch-failed",
        "supervisor-connect-timeout",
        "agent-connect-timeout",
        "session-start-timeout",
        "webots-unexpected-exit",
        "admin-request-failed",
        "mcp-tool-failed",
    )
