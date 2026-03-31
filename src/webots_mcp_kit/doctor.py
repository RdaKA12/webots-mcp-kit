from __future__ import annotations

import json
import sys
from pathlib import Path

from .environment import current_python, get_webots_environment


def run_doctor() -> dict[str, object]:
    webots = get_webots_environment()
    ok = webots.webots_executable.exists() and webots.controller_python_path.exists()
    readiness = {
        "status": "ready" if ok else "blocked",
        "runner_label": "webots",
        "workflow": "Windows Runtime Smoke",
        "recommended_session_timeout_s": 180,
        "requires_self_hosted_runner": True,
        "notes": [
            "Hosted GitHub Actions runners only cover unit, doctor, and MCP handshake smoke.",
            "Use a self-hosted Windows runner with Webots installed for runtime smoke and benchmark execution.",
        ],
    }
    report = {
        "python": current_python(),
        "webots_home": str(webots.webots_home),
        "webots_executable": str(webots.webots_executable),
        "webots_version": webots.version,
        "controller_python_path": str(webots.controller_python_path),
        "controller_library_path": str(webots.controller_library_path),
        "webots_executable_exists": webots.webots_executable.exists(),
        "controller_python_exists": webots.controller_python_path.exists(),
        "platform": sys.platform,
        "status": "ok" if ok else "failed",
        "recommended_python": "3.11+",
        "supports_batch_mode": bool(ok),
        "runtime_readiness": readiness,
    }
    return report


def format_doctor_report(report: dict[str, object]) -> str:
    lines = ["webots-mcp-kit doctor", ""]
    for key in (
        "python",
        "platform",
        "webots_home",
        "webots_executable",
        "webots_version",
        "controller_python_path",
        "controller_library_path",
        "webots_executable_exists",
        "controller_python_exists",
        "recommended_python",
        "supports_batch_mode",
    ):
        lines.append(f"{key}: {report[key]}")
    readiness = report.get("runtime_readiness", {})
    if isinstance(readiness, dict):
        lines.extend(
            [
                "",
                "runtime_readiness:",
                f"  status: {readiness.get('status')}",
                f"  runner_label: {readiness.get('runner_label')}",
                f"  workflow: {readiness.get('workflow')}",
                f"  recommended_session_timeout_s: {readiness.get('recommended_session_timeout_s')}",
                f"  requires_self_hosted_runner: {readiness.get('requires_self_hosted_runner')}",
            ]
        )
        for note in readiness.get("notes", []):
            lines.append(f"  note: {note}")
    lines.extend(["", f"status: {report['status']}"])
    return "\n".join(lines)


def write_doctor_report(path: Path) -> None:
    path.write_text(json.dumps(run_doctor(), indent=2), encoding="utf-8")
