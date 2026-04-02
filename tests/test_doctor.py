from __future__ import annotations

from pathlib import Path

from webots_mcp_kit.doctor import format_doctor_report, run_doctor
from webots_mcp_kit.environment import WebotsEnvironment


def test_doctor_report_includes_runtime_readiness_fields() -> None:
    report = {
        "python": "python",
        "platform": "win32",
        "webots_home": "C:\\Program Files\\Webots",
        "webots_executable": "webots.exe",
        "webots_version": "R2025a",
        "controller_python_path": "controller/python",
        "controller_library_path": "controller",
        "webots_executable_exists": True,
        "controller_python_exists": True,
        "recommended_python": "3.11+",
        "supports_batch_mode": True,
        "runtime_readiness": {
            "status": "ready",
            "runner_label": "interactive-webots",
            "runner_mode": {"mode": "interactive-session", "session_name": "Console"},
            "workflow": "Windows Runtime Smoke",
            "recommended_session_timeout_s": 180,
            "requires_self_hosted_runner": True,
            "hosted_runtime_smoke_supported": False,
            "interactive_session_required": True,
            "windows_service_runtime_supported": False,
            "recommended_next_step": "Run runtime smoke",
            "runner_requirements": ["Windows machine", "Interactive session"],
            "notes": ["Use self-hosted runner"],
        },
        "status": "ready",
    }
    formatted = format_doctor_report(report)
    assert "runtime_status: ready" in formatted
    assert "hosted_runtime_smoke_supported: False" in formatted
    assert "interactive_session_required: True" in formatted
    assert "recommended_next_step: Run runtime smoke" in formatted
    assert "requirement: Windows machine" in formatted
    assert "status: ready" in formatted


def test_run_doctor_marks_service_runner_as_misconfigured(tmp_path: Path, monkeypatch) -> None:
    webots_home = tmp_path / "Webots"
    executable = webots_home / "msys64" / "mingw64" / "bin" / "webots.exe"
    controller_python = webots_home / "lib" / "controller" / "python"
    controller_library = webots_home / "lib" / "controller"
    executable.parent.mkdir(parents=True, exist_ok=True)
    controller_python.mkdir(parents=True, exist_ok=True)
    controller_library.mkdir(parents=True, exist_ok=True)
    executable.write_text("", encoding="utf-8")
    fake_env = WebotsEnvironment(
        webots_home=webots_home,
        webots_executable=executable,
        controller_python_path=controller_python,
        controller_library_path=controller_library,
        version="R2025a",
    )
    monkeypatch.setattr("webots_mcp_kit.doctor.get_webots_environment", lambda: fake_env)
    monkeypatch.setattr("webots_mcp_kit.doctor.detect_runner_mode", lambda: {"mode": "windows-service", "session_name": "Services"})
    report = run_doctor()
    assert report["status"] == "misconfigured"
    assert report["runtime_readiness"]["status"] == "misconfigured"


def test_run_doctor_marks_missing_webots_as_blocked(monkeypatch) -> None:
    fake_env = WebotsEnvironment(
        webots_home=Path("C:/Missing/Webots"),
        webots_executable=Path("C:/Missing/Webots/msys64/mingw64/bin/webots.exe"),
        controller_python_path=Path("C:/Missing/Webots/lib/controller/python"),
        controller_library_path=Path("C:/Missing/Webots/lib/controller"),
        version=None,
    )
    monkeypatch.setattr("webots_mcp_kit.doctor.get_webots_environment", lambda: fake_env)
    monkeypatch.setattr("webots_mcp_kit.doctor.detect_runner_mode", lambda: {"mode": "unknown", "session_name": None})
    report = run_doctor()
    assert report["status"] == "blocked"
    assert report["runtime_readiness"]["status"] == "blocked"
