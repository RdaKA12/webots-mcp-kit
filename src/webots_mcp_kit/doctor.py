from __future__ import annotations

import json
import sys
from pathlib import Path

from .environment import current_python, get_webots_environment


def run_doctor() -> dict[str, object]:
    webots = get_webots_environment()
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
    }
    return report


def format_doctor_report(report: dict[str, object]) -> str:
    lines = ["webots-mcp-kit doctor", ""]
    for key, value in report.items():
        lines.append(f"{key}: {value}")
    ok = bool(report["webots_executable_exists"]) and bool(report["controller_python_exists"])
    lines.append("")
    lines.append(f"status: {'ok' if ok else 'failed'}")
    return "\n".join(lines)


def write_doctor_report(path: Path) -> None:
    path.write_text(json.dumps(run_doctor(), indent=2), encoding="utf-8")
