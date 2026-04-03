from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .benchmarks import get_scenario
from .controller_authoring import compile_cpp_controller, detect_controller_language, inspect_controller
from .errors import KitError


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


def validate_controller(
    path: Path,
    *,
    scenario: str | None = None,
    strict: bool = False,
    spec_path: Path | None = None,
) -> ControllerValidationResult:
    result = ControllerValidationResult(path=str(path), valid=False, integration_mode="unknown")
    resolved = path if path.is_absolute() else (Path.cwd() / path).resolve()
    if not resolved.exists():
        result.errors.append("Controller file does not exist.")
        return result

    language = detect_controller_language(resolved)
    if language not in {"python", "cpp"}:
        result.errors.append("Only Python and C++ controllers are supported by the validator.")
        return result

    inspection = inspect_controller(resolved, scenario=scenario, spec_path=spec_path)
    scenario_def = get_scenario(inspection.scenario) if inspection.scenario else None

    result.integration_mode = inspection.integration_mode
    result.details = {
        "language": inspection.language,
        "strict": strict,
        "scenario": inspection.scenario,
        "editable_regions": inspection.editable_regions,
        "markers_present": inspection.markers_present,
        "has_robot_init": inspection.has_robot_init,
        "has_step_loop": inspection.has_step_loop,
        "has_from_robot": inspection.has_from_robot,
        "default_camera": inspection.default_camera,
        "has_begin_step": inspection.has_begin_step,
        "has_report_step": inspection.has_report_step,
        "device_bindings": inspection.device_bindings,
        "device_access_inventory": inspection.device_access_inventory,
        "telemetry_sections": inspection.telemetry_sections,
        "telemetry_contract": inspection.telemetry_contract,
        "benchmark_readiness": inspection.benchmark_readiness,
        "benchmark_contract_gaps": inspection.benchmark_contract_gaps,
        "function_inventory": inspection.function_inventory,
        "editable_symbols": inspection.editable_symbols,
        "compile_readiness": inspection.compile_readiness,
        "runtime_readiness": inspection.runtime_readiness,
        "controller_fix_hints": inspection.controller_fix_hints,
    }

    result.errors.extend(inspection.issues)
    if scenario_def and scenario_def.default_camera:
        if not inspection.default_camera:
            result.errors.append(f"ControllerAgent.from_robot(...) must define default_camera='{scenario_def.default_camera}'.")
        elif inspection.default_camera != scenario_def.default_camera:
            result.errors.append(
                f"default_camera must be '{scenario_def.default_camera}' for scenario '{scenario_def.name}', got '{inspection.default_camera}'."
            )

    readiness_issues = inspection.benchmark_readiness.get("issues", [])
    for issue in readiness_issues:
        _record_issue(result, strict, issue)

    if scenario_def:
        expected_camera = scenario_def.default_camera
        if expected_camera and expected_camera not in inspection.device_bindings:
            _record_issue(result, strict, f"Default camera '{expected_camera}' is not part of the controller device bindings.")

    if language == "cpp" and inspection.valid_source and not result.errors:
        try:
            compile_result = compile_cpp_controller(resolved)
            result.details["compile_smoke"] = {
                "ok": True,
                "binary_path": compile_result["binary_path"],
            }
        except KitError as exc:
            _record_issue(result, strict, exc.message)
            result.details["compile_smoke"] = {
                "ok": False,
                "error": exc.to_dict(),
            }

    result.valid = not result.errors
    return result


def _record_issue(result: ControllerValidationResult, strict: bool, message: str) -> None:
    if strict:
        result.errors.append(message)
    else:
        result.warnings.append(message)


def format_validation_report(result: ControllerValidationResult) -> str:
    details = result.details
    summary = f"{len(result.errors)} errors, {len(result.warnings)} warnings"
    lines = [
        f"controller_validation: {'pass' if result.valid else 'fail'}",
        f"path: {result.path}",
        f"language: {details.get('language')}",
        f"scenario: {details.get('scenario')}",
        f"strict: {details.get('strict')}",
        f"integration_mode: {result.integration_mode}",
        f"editable_regions: {details.get('editable_regions')}",
        f"summary: {summary}",
        f"default_camera: {details.get('default_camera')}",
        f"device_bindings: {details.get('device_bindings')}",
        f"benchmark_readiness: {details.get('benchmark_readiness', {}).get('ready')}",
        f"benchmark_contract_gaps: {details.get('benchmark_contract_gaps')}",
    ]
    if result.errors:
        lines.append("errors:")
        lines.extend(f"- {error}" for error in result.errors)
    if result.warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in result.warnings)
    if details.get("controller_fix_hints"):
        lines.append(f"controller_fix_hints: {details.get('controller_fix_hints')}")
    if result.valid:
        lines.append(
            "next_step: Run `webots-kit benchmark run <scenario> --controller <path> ...`, inspect with `webots-kit controller inspect`, or expose MCP with `webots-kit mcp serve`."
        )
    else:
        lines.append("next_step: Fix the listed controller contract issues, then rerun validation with `--strict`.")
    return "\n".join(lines)
