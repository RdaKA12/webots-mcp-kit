from __future__ import annotations

import json
import uuid
from pathlib import Path

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

    def write_manifest(self, manifest: SessionManifest) -> Path:
        path = self.manifest_path(manifest.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
        return path

    def load_manifest(self, session_id: str) -> SessionManifest:
        data = json.loads(self.manifest_path(session_id).read_text(encoding="utf-8"))
        return SessionManifest(**data)

    def list_manifests(self) -> list[SessionManifest]:
        manifests: list[SessionManifest] = []
        for path in self.root.glob("*/session.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                manifests.append(SessionManifest(**data))
            except Exception:
                continue
        return sorted(manifests, key=lambda item: item.created_at, reverse=True)

    def latest_manifest(self) -> SessionManifest | None:
        manifests = self.list_manifests()
        return manifests[0] if manifests else None
