from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .benchmarks import get_scenario


@dataclass(slots=True)
class ControllerValidationResult:
    path: str
    valid: bool
    integration_mode: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_controller(path: Path, *, scenario: str | None = None, strict: bool = False) -> ControllerValidationResult:
    result = ControllerValidationResult(path=str(path), valid=False, integration_mode="unknown")
    if not path.exists():
        result.errors.append("Controller file does not exist.")
        return result
    if path.suffix != ".py":
        result.errors.append("Only Python controllers are supported by the validator.")
        return result

    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        result.errors.append(f"Unable to read controller file: {exc}")
        return result

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        result.errors.append(f"Syntax error: {exc.msg} at line {exc.lineno}")
        return result

    scenario_def = get_scenario(scenario) if scenario else None
    analysis = _analyze_tree(tree)

    if not analysis["has_robot_init"]:
        result.errors.append("No Webots Robot() initialization detected.")
    if not analysis["has_step_loop"]:
        result.errors.append("No robot.step(...) loop detected.")
    if not analysis["uses_controller_agent"]:
        result.errors.append("Controller must import and use ControllerAgent from webots_mcp_kit.agent.")
    if not analysis["has_from_robot"]:
        result.errors.append("ControllerAgent.from_robot(...) was not detected.")
    if not analysis["has_begin_step"]:
        result.errors.append("ControllerAgent.begin_step() was not detected.")
    if not analysis["has_report_step"]:
        result.errors.append("ControllerAgent.report_step(...) was not detected.")

    default_camera = analysis["default_camera"]
    if scenario_def and scenario_def.default_camera:
        if not default_camera:
            result.errors.append(f"ControllerAgent.from_robot(...) must define default_camera='{scenario_def.default_camera}'.")
        elif default_camera != scenario_def.default_camera:
            result.errors.append(
                f"default_camera must be '{scenario_def.default_camera}' for scenario '{scenario_def.name}', got '{default_camera}'."
            )

    if analysis["has_report_step"]:
        report_keywords = analysis["report_step_keywords"]
        for keyword in ("sensors", "metrics", "actuators"):
            if keyword not in report_keywords:
                result.errors.append(f"report_step(...) must include the '{keyword}' keyword.")
        if scenario_def and scenario_def.default_camera and "camera_frames" not in report_keywords:
            _record_issue(result, strict, "report_step(...) should include camera_frames for scenario camera capture support.")

    if scenario_def:
        _validate_required_keys(
            result=result,
            strict=strict,
            keyword_name="sensors",
            expected=scenario_def.required_sensor_keys,
            literal_keys=analysis["report_step_literal_keys"].get("sensors"),
        )
        _validate_required_keys(
            result=result,
            strict=strict,
            keyword_name="metrics",
            expected=scenario_def.required_metric_keys,
            literal_keys=analysis["report_step_literal_keys"].get("metrics"),
        )
        _validate_required_keys(
            result=result,
            strict=strict,
            keyword_name="actuators",
            expected=scenario_def.required_actuator_keys,
            literal_keys=analysis["report_step_literal_keys"].get("actuators"),
        )

    result.integration_mode = "controller-agent" if analysis["uses_controller_agent"] else "plain-webots"
    result.details = {
        "strict": strict,
        "scenario": scenario_def.name if scenario_def else None,
        "has_robot_init": analysis["has_robot_init"],
        "has_step_loop": analysis["has_step_loop"],
        "uses_controller_agent": analysis["uses_controller_agent"],
        "has_from_robot": analysis["has_from_robot"],
        "default_camera": default_camera,
        "has_begin_step": analysis["has_begin_step"],
        "has_report_step": analysis["has_report_step"],
        "report_step_keywords": sorted(analysis["report_step_keywords"]),
        "report_step_literal_keys": {
            name: (sorted(values) if values is not None else None)
            for name, values in analysis["report_step_literal_keys"].items()
        },
    }
    result.valid = not result.errors
    return result


def _record_issue(result: ControllerValidationResult, strict: bool, message: str) -> None:
    if strict:
        result.errors.append(message)
    else:
        result.warnings.append(message)


def _validate_required_keys(
    *,
    result: ControllerValidationResult,
    strict: bool,
    keyword_name: str,
    expected: tuple[str, ...],
    literal_keys: set[str] | None,
) -> None:
    if not expected:
        return
    if literal_keys is None:
        _record_issue(
            result,
            strict,
            f"Unable to statically confirm {keyword_name} keys. Use a literal dict or validate with --strict after expanding telemetry.",
        )
        return
    missing = sorted(set(expected) - literal_keys)
    if missing:
        _record_issue(result, strict, f"Missing required {keyword_name} keys: {missing}")


def _analyze_tree(tree: ast.AST) -> dict[str, Any]:
    imported_controller_agent = False
    has_robot_init = False
    has_step_loop = False
    has_from_robot = False
    has_begin_step = False
    has_report_step = False
    default_camera: str | None = None
    report_step_keywords: set[str] = set()
    report_step_literal_keys: dict[str, set[str] | None] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "webots_mcp_kit.agent":
            if any(alias.name == "ControllerAgent" for alias in node.names):
                imported_controller_agent = True
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "Robot":
                has_robot_init = True
            if isinstance(node.func, ast.Attribute) and node.func.attr == "step":
                has_step_loop = True
            if isinstance(node.func, ast.Attribute) and node.func.attr == "from_robot":
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "ControllerAgent":
                    has_from_robot = True
                    default_camera = _string_keyword(node, "default_camera")
            if isinstance(node.func, ast.Attribute) and node.func.attr == "begin_step":
                has_begin_step = True
            if isinstance(node.func, ast.Attribute) and node.func.attr == "report_step":
                has_report_step = True
                for keyword in node.keywords:
                    if not keyword.arg:
                        continue
                    report_step_keywords.add(keyword.arg)
                    if keyword.arg in {"sensors", "metrics", "actuators", "camera_frames"}:
                        report_step_literal_keys[keyword.arg] = _literal_dict_keys(keyword.value)

    return {
        "uses_controller_agent": imported_controller_agent,
        "has_robot_init": has_robot_init,
        "has_step_loop": has_step_loop,
        "has_from_robot": has_from_robot,
        "default_camera": default_camera,
        "has_begin_step": has_begin_step,
        "has_report_step": has_report_step,
        "report_step_keywords": report_step_keywords,
        "report_step_literal_keys": report_step_literal_keys,
    }


def _string_keyword(node: ast.Call, name: str) -> str | None:
    for keyword in node.keywords:
        if keyword.arg != name:
            continue
        return _string_constant(keyword.value)
    return None


def _string_constant(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _literal_dict_keys(node: ast.AST) -> set[str] | None:
    if isinstance(node, ast.Dict):
        keys: set[str] = set()
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.add(key.value)
        return keys
    return None


def format_validation_report(result: ControllerValidationResult) -> str:
    details = result.details
    summary = f"{len(result.errors)} errors, {len(result.warnings)} warnings"
    lines = [
        f"controller_validation: {'pass' if result.valid else 'fail'}",
        f"path: {result.path}",
        f"scenario: {details.get('scenario')}",
        f"strict: {details.get('strict')}",
        f"integration_mode: {result.integration_mode}",
        f"summary: {summary}",
        f"default_camera: {details.get('default_camera')}",
        f"report_step_keywords: {details.get('report_step_keywords')}",
    ]
    if result.errors:
        lines.append("errors:")
        lines.extend(f"- {error}" for error in result.errors)
    if result.warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in result.warnings)
    if result.valid:
        lines.append("next_step: Run `webots-kit benchmark run <scenario> --controller <path> ...` or expose MCP with `webots-kit mcp serve`.")
    else:
        lines.append("next_step: Fix the listed controller contract issues, then rerun validation with `--strict`.")
    return "\n".join(lines)
