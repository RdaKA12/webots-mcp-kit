from __future__ import annotations

from webots_mcp_kit.controller_validation import ControllerValidationResult, format_validation_report


def test_validation_report_includes_summary_and_next_step() -> None:
    result = ControllerValidationResult(
        path="controller.py",
        valid=False,
        integration_mode="controller-agent",
        errors=["missing report_step"],
        warnings=["camera_frames omitted"],
        details={"scenario": "line-follower", "strict": True, "default_camera": "camera", "report_step_keywords": ["sensors"]},
    )
    formatted = format_validation_report(result)
    assert "summary: 1 errors, 1 warnings" in formatted
    assert "next_step:" in formatted
