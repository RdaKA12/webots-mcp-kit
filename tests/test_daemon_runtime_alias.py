from __future__ import annotations

import json
from pathlib import Path

from webots_mcp_kit.daemon import SessionDaemon
from webots_mcp_kit.models import SessionManifest
from webots_mcp_kit.utils import utc_now_iso


def test_runtime_alias_maps_hashed_ipc_id_to_robot_name(tmp_path: Path) -> None:
    manifest = SessionManifest(
        session_id="session123",
        host="127.0.0.1",
        port=5555,
        daemon_pid=1,
        status="starting",
        scenario="waypoint-nav",
        world="world.wbt",
        mode="fast",
        render=False,
        robot_controller="controller.py",
        target_robot_name="epuck-generated-waypoint-agent",
        target_robot_def="EPUCK",
        created_at=utc_now_iso(),
        session_dir=str(tmp_path),
        artifacts_dir=str(tmp_path / "artifacts"),
    )
    manifest_path = tmp_path / "session.json"
    manifest_path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")

    daemon = SessionDaemon(
        manifest_path=manifest_path,
        world=tmp_path / "world.wbt",
        robot_controller=tmp_path / "controller.py",
        host="127.0.0.1",
        port=5555,
        mode="fast",
        render=False,
    )
    daemon._record_runtime_alias(
        "INFO: 'epuck-generated-waypoint-agent' extern controller: Waiting for local or remote connection on port 64511 targeting robot named 'epuck-generated-waypoint-agent' (874a1bde8f6d08c2ba070dd527)."
    )

    assert daemon.runtime_url_aliases["874a1bde8f6d08c2ba070dd527"] == "epuck-generated-waypoint-agent"
