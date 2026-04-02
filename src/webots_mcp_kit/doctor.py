from __future__ import annotations

import json
import sys
from pathlib import Path

from .environment import current_python, detect_runner_mode, get_webots_environment


def run_doctor() -> dict[str, object]:
    webots = get_webots_environment()
    ok = webots.webots_executable.exists() and webots.controller_python_path.exists()
    readiness = {
        "status": "ready" if ok else "blocked",
        "runner_label": "interactive-webots",
        "runner_mode": detect_runner_mode(),
        "workflow": "Windows Runtime Smoke",
        "recommended_session_timeout_s": 180,
        "requires_self_hosted_runner": True,
        "hosted_runtime_smoke_supported": False,
        "interactive_session_required": True,
        "windows_service_runtime_supported": False,
        "recommended_next_step": "Run local runtime smoke or dispatch the self-hosted Windows Runtime Smoke workflow.",
        "runner_requirements": [
            "Windows machine",
            "Webots R2025a installed and visible through WEBOTS_HOME",
            "Python 3.11+",
            "GitHub Actions self-hosted runner labeled interactive-webots",
            "Runner must execute inside an interactive user session, not as a Windows service",
        ],
        "notes": [
            "Hosted GitHub Actions runners only cover unit, doctor, and MCP handshake smoke.",
            "Use a self-hosted Windows runner with Webots installed for runtime smoke and benchmark execution.",
            "Webots runtime smoke is not supported from a Windows service session because the rendering stack fails before controllers can connect.",
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
    runtime_state = report.get("runtime_readiness", {})
    readiness_status = runtime_state.get("status") if isinstance(runtime_state, dict) else None
    lines.append(f"runtime_status: {readiness_status}")
    lines.append("")
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
        runner_mode = readiness.get("runner_mode")
        if isinstance(runner_mode, dict):
            runner_mode_text = runner_mode.get("mode")
            if runner_mode.get("session_name"):
                runner_mode_text = f"{runner_mode_text} ({runner_mode.get('session_name')})"
        else:
            runner_mode_text = runner_mode
        lines.extend(
            [
                "",
                "runtime_readiness:",
                f"  status: {readiness.get('status')}",
                f"  runner_label: {readiness.get('runner_label')}",
                f"  runner_mode: {runner_mode_text}",
                f"  workflow: {readiness.get('workflow')}",
                f"  recommended_session_timeout_s: {readiness.get('recommended_session_timeout_s')}",
                f"  requires_self_hosted_runner: {readiness.get('requires_self_hosted_runner')}",
                f"  hosted_runtime_smoke_supported: {readiness.get('hosted_runtime_smoke_supported')}",
                f"  interactive_session_required: {readiness.get('interactive_session_required')}",
                f"  windows_service_runtime_supported: {readiness.get('windows_service_runtime_supported')}",
                f"  recommended_next_step: {readiness.get('recommended_next_step')}",
            ]
        )
        for requirement in readiness.get("runner_requirements", []):
            lines.append(f"  requirement: {requirement}")
        for note in readiness.get("notes", []):
            lines.append(f"  note: {note}")
    lines.extend(["", f"status: {report['status']}"])
    return "\n".join(lines)


def write_doctor_report(path: Path) -> None:
    path.write_text(json.dumps(run_doctor(), indent=2), encoding="utf-8")
