from __future__ import annotations

import json
from pathlib import Path

from webots_mcp_kit.controller_authoring import edit_controller, inspect_controller
from webots_mcp_kit.controller_scaffold import scaffold_controller
from webots_mcp_kit.controller_validation import validate_controller


def test_python_controller_inspect_reports_markers(tmp_path: Path) -> None:
    target = tmp_path / "generated_line_follower.py"
    scaffold_controller(path=target, scenario="line-follower", language="python")
    payload = inspect_controller(target, scenario="line-follower")
    assert payload.markers_present is True
    assert payload.editable_regions == ["DEVICE_INIT", "CONTROL_POLICY", "TELEMETRY_REPORT", "HELPERS"]
    assert "camera" in payload.device_bindings
    assert "find_middle" in payload.function_inventory
    assert "CRUISE" in payload.editable_symbols
    assert payload.device_access_inventory
    assert payload.telemetry_contract["expected"]["metrics"] == ["line_visible", "center_error", "ir_balance_error"]
    assert payload.benchmark_contract_gaps == []


def test_python_controller_edit_updates_constant(tmp_path: Path) -> None:
    target = tmp_path / "generated_line_follower.py"
    scaffold_controller(path=target, scenario="line-follower", language="python")
    plan_path = tmp_path / "controller-edit.json"
    plan_path.write_text(
        json.dumps({"schema_version": 1, "operations": [{"type": "update_control_constants", "constants": {"CRUISE": 180}}]}, indent=2),
        encoding="utf-8",
    )
    payload = edit_controller(target, plan_path=plan_path)
    assert "update_control_constants" in payload["applied_operations"]
    assert "CRUISE = 180" in target.read_text(encoding="utf-8")
    assert validate_controller(target, scenario="line-follower", strict=True).valid is True


def test_python_controller_edit_supports_symbol_body_and_import_operations(tmp_path: Path) -> None:
    target = tmp_path / "generated_line_follower.py"
    scaffold_controller(path=target, scenario="line-follower", language="python")
    plan_path = tmp_path / "controller-edit-generic.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operations": [
                    {"type": "add_import_or_include", "statement": "import math"},
                    {"type": "set_symbol_value", "symbol": "TURN_GAIN", "value": 6},
                    {"type": "replace_function_body", "function": "clamp", "body": "return value"},
                    {"type": "remove_import_or_include", "statement": "import math"},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = edit_controller(target, plan_path=plan_path)
    source = target.read_text(encoding="utf-8")
    inspection = inspect_controller(target, scenario="line-follower")

    assert "set_symbol_value" in payload["applied_operations"]
    assert "replace_function_body" in payload["applied_operations"]
    assert "TURN_GAIN = 6" in source
    assert "return value" in source
    assert "import math" not in source
    assert inspection.controller_fix_hints == []


def test_cpp_controller_scaffold_validates_non_strict(tmp_path: Path) -> None:
    target = tmp_path / "generated_waypoint.cpp"
    scaffold_controller(path=target, scenario="waypoint-nav", language="cpp")
    result = validate_controller(target, scenario="waypoint-nav", strict=False)
    assert result.valid is True
    assert result.integration_mode == "controller-agent"
    inspection = inspect_controller(target, scenario="waypoint-nav")
    assert inspection.function_inventory
    assert inspection.editable_symbols
    assert inspection.device_access_inventory
