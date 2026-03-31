from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .doctor import run_doctor
from .launcher import inspect_session
from .session_store import SessionStore
from .utils import atomic_write_text


def collect_runtime_diagnostics(*, output_dir: Path, session_id: str | None = None) -> dict[str, Any]:
    output = output_dir if output_dir.is_absolute() else (Path.cwd() / output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {"doctor": run_doctor(), "session_id": session_id}
    atomic_write_text(output / "doctor.json", json.dumps(payload["doctor"], indent=2), encoding="utf-8")

    store = SessionStore()
    manifest = store.load_manifest(session_id) if session_id else store.latest_manifest()
    if manifest is None:
        payload["latest_session"] = None
        atomic_write_text(output / "summary.json", json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    payload["session_id"] = manifest.session_id
    payload["latest_session"] = manifest.to_dict()
    payload["inspect"] = inspect_session(manifest.session_id)
    payload["log_inventory"] = store.log_inventory(manifest.session_id)
    payload["log_summary"] = store.log_summary(manifest.session_id)

    atomic_write_text(output / "session.json", json.dumps(payload["latest_session"], indent=2), encoding="utf-8")
    atomic_write_text(output / "inspect.json", json.dumps(payload["inspect"], indent=2), encoding="utf-8")
    atomic_write_text(output / "log_inventory.json", json.dumps(payload["log_inventory"], indent=2), encoding="utf-8")
    atomic_write_text(output / "log_summary.json", json.dumps(payload["log_summary"], indent=2), encoding="utf-8")
    atomic_write_text(output / "summary.json", json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--session")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = collect_runtime_diagnostics(output_dir=Path(args.output), session_id=args.session)
    print(json.dumps({"output": str(Path(args.output).resolve()), "session_id": payload.get("session_id")}, indent=2))


if __name__ == "__main__":
    main()
