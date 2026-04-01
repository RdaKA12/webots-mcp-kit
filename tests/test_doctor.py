from __future__ import annotations

from webots_mcp_kit.doctor import format_doctor_report


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
            "runner_label": "webots",
            "workflow": "Windows Runtime Smoke",
            "recommended_session_timeout_s": 180,
            "requires_self_hosted_runner": True,
            "hosted_runtime_smoke_supported": False,
            "recommended_next_step": "Run runtime smoke",
            "runner_requirements": ["Windows machine"],
            "notes": ["Use self-hosted runner"],
        },
        "status": "ok",
    }
    formatted = format_doctor_report(report)
    assert "hosted_runtime_smoke_supported: False" in formatted
    assert "recommended_next_step: Run runtime smoke" in formatted
    assert "requirement: Windows machine" in formatted
