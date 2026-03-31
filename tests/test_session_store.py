from __future__ import annotations

from pathlib import Path

from webots_mcp_kit.models import SessionManifest
from webots_mcp_kit.session_store import SessionStore


def test_session_store_roundtrip(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    session_dir = store.create_session_dir("abc123")
    manifest = SessionManifest(
        session_id="abc123",
        host="127.0.0.1",
        port=9000,
        daemon_pid=1,
        status="ready",
        scenario="line-follower",
        world="world.wbt",
        mode="fast",
        render=False,
        robot_controller="controller.py",
        target_robot_name="epuck-line-follower",
        target_robot_def="EPUCK",
        created_at="2026-03-31T00:00:00+00:00",
        session_dir=str(session_dir),
        artifacts_dir=str(session_dir / "artifacts"),
    )
    store.write_manifest(manifest)
    loaded = store.load_manifest("abc123")
    assert loaded.session_id == "abc123"
    assert loaded.port == 9000
    assert loaded.status == "ready"
