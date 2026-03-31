from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


TOOLKIT_AGENT_IMPORTS = {
    "webots_mcp_kit.agent": {"AgentBridge", "ControllerAgent"},
}


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


def validate_controller(path: Path) -> ControllerValidationResult:
    result = ControllerValidationResult(
        path=str(path),
        valid=False,
        integration_mode="unknown",
    )
    if not path.exists():
        result.errors.append("Controller file does not exist.")
        return result
    if path.suffix != ".py":
        result.errors.append("Only Python controllers are supported by the validator in v0.3.0.")
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

    imported_names: set[str] = set()
    has_robot_init = False
    has_step_loop = False
    has_publish = False
    has_begin_step = False

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in TOOLKIT_AGENT_IMPORTS:
                imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "Robot":
                has_robot_init = True
            if isinstance(node.func, ast.Attribute) and node.func.attr == "step":
                has_step_loop = True
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"publish_step", "report_step"}:
                has_publish = True
            if isinstance(node.func, ast.Attribute) and node.func.attr == "begin_step":
                has_begin_step = True

    uses_toolkit_agent = bool(imported_names.intersection({"AgentBridge", "ControllerAgent"}))
    if not has_robot_init:
        result.errors.append("No Webots Robot() initialization detected.")
    if not has_step_loop:
        result.errors.append("No robot.step(...) loop detected.")
    if not uses_toolkit_agent:
        result.errors.append("Controller does not import AgentBridge or ControllerAgent from webots_mcp_kit.agent.")
    if uses_toolkit_agent and not has_begin_step:
        result.warnings.append("Toolkit agent is imported but begin_step() was not detected.")
    if uses_toolkit_agent and not has_publish:
        result.warnings.append("Toolkit agent is imported but publish_step() was not detected.")

    result.integration_mode = "toolkit-agent" if uses_toolkit_agent else "plain-webots"
    result.details = {
        "has_robot_init": has_robot_init,
        "has_step_loop": has_step_loop,
        "uses_toolkit_agent": uses_toolkit_agent,
        "has_begin_step": has_begin_step,
        "has_publish_step": has_publish,
    }
    result.valid = not result.errors
    return result


def format_validation_report(result: ControllerValidationResult) -> str:
    lines = [
        f"path: {result.path}",
        f"valid: {result.valid}",
        f"integration_mode: {result.integration_mode}",
        f"details: {result.details}",
    ]
    if result.errors:
        lines.append(f"errors: {result.errors}")
    if result.warnings:
        lines.append(f"warnings: {result.warnings}")
    return "\n".join(lines)
