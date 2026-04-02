from __future__ import annotations

import json

from webots_mcp_kit.diagnostics import collect_runtime_diagnostics
from webots_mcp_kit.models import SessionManifest
from webots_mcp_kit.session_store import SessionStore


def test_collect_runtime_diagnostics_without_session(tmp_path, monkeypatch) -> None:
    store = SessionStore(root=tmp_path / "sessions")
    monkeypatch.setattr("webots_mcp_kit.diagnostics.SessionStore", lambda: store)
    monkeypatch.setattr(
        "webots_mcp_kit.diagnostics.run_doctor",
        lambda: {"status": "ok", "runtime_readiness": {"runner_label": "interactive-webots"}},
    )
    payload = collect_runtime_diagnostics(output_dir=tmp_path / "diag")
    assert payload["latest_session"] is None
    summary = json.loads((tmp_path / "diag" / "summary.json").read_text(encoding="utf-8"))
    assert summary["doctor"]["status"] == "ok"


def test_collect_runtime_diagnostics_with_session(tmp_path, monkeypatch) -> None:
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
    )
    store.write_manifest(manifest)
    (session_dir / "artifacts" / "daemon.stdout.log").write_text("ok\n", encoding="utf-8")

    monkeypatch.setattr("webots_mcp_kit.diagnostics.SessionStore", lambda: store)
    monkeypatch.setattr(
        "webots_mcp_kit.diagnostics.run_doctor",
        lambda: {"status": "ok", "runtime_readiness": {"runner_label": "interactive-webots"}},
    )
    monkeypatch.setattr(
        "webots_mcp_kit.diagnostics.inspect_session",
        lambda session_id: {"manifest": manifest.to_dict(), "logs": [{"name": "daemon.stdout.log"}]},
    )

    payload = collect_runtime_diagnostics(output_dir=tmp_path / "diag")
    assert payload["session_id"] == "diagtest"
    assert (tmp_path / "diag" / "inspect.json").exists()
