from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from .benchmarks import get_scenario
from .environment import app_state_root
from .models import SessionManifest


class SessionStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or (app_state_root() / "sessions")
        self.root.mkdir(parents=True, exist_ok=True)

    def create_session_dir(self, session_id: str | None = None) -> Path:
        session_id = session_id or uuid.uuid4().hex[:12]
        session_dir = self.root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "artifacts").mkdir(exist_ok=True)
        return session_dir

    def manifest_path(self, session_id: str) -> Path:
        return self.root / session_id / "session.json"

    def session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def artifacts_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "artifacts"

    def write_manifest(self, manifest: SessionManifest) -> Path:
        path = self.manifest_path(manifest.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
        return path

    def load_manifest(self, session_id: str) -> SessionManifest:
        data = json.loads(self.manifest_path(session_id).read_text(encoding="utf-8"))
        data = self._normalize_manifest_data(data)
        return SessionManifest(**data)

    def list_manifests(self) -> list[SessionManifest]:
        manifests: list[SessionManifest] = []
        for path in self.root.glob("*/session.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data = self._normalize_manifest_data(data)
                manifests.append(SessionManifest(**data))
            except Exception:
                continue
        return sorted(manifests, key=lambda item: item.created_at, reverse=True)

    def latest_manifest(self) -> SessionManifest | None:
        manifests = self.list_manifests()
        return manifests[0] if manifests else None

    def list_artifacts(self, session_id: str) -> list[dict[str, str | int]]:
        artifacts_dir = self.artifacts_dir(session_id)
        if not artifacts_dir.exists():
            return []
        items: list[dict[str, str | int]] = []
        for path in sorted(artifacts_dir.glob("*")):
            if not path.is_file():
                continue
            items.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "size": path.stat().st_size,
                }
            )
        return items

    def wait_for_status(self, session_id: str, statuses: set[str], timeout: float = 20.0) -> SessionManifest:
        deadline = time.time() + timeout
        while time.time() < deadline:
            manifest = self.load_manifest(session_id)
            if manifest.status in statuses:
                return manifest
            time.sleep(0.2)
        raise TimeoutError(f"Timed out waiting for session {session_id} to reach one of: {sorted(statuses)}")

    def _normalize_manifest_data(self, data: dict[str, object]) -> dict[str, object]:
        scenario_name = str(data.get("scenario") or "line-follower")
        try:
            scenario = get_scenario(scenario_name)
        except KeyError:
            scenario = get_scenario("line-follower")
            scenario_name = scenario.name
        data.setdefault("scenario", scenario_name)
        data.setdefault("target_robot_name", scenario.target_robot_name)
        data.setdefault("target_robot_def", scenario.target_robot_def)
        data.setdefault("stopped_at", None)
        data.setdefault("last_error", None)
        return data
