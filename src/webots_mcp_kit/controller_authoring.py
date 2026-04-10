from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import tree_sitter_cpp
from tree_sitter import Language, Node, Parser

from .benchmarks import get_scenario
from .environment import build_process_env, current_python, get_webots_environment
from .errors import KitError
from .robot_profiles import get_robot_profile, robot_profile_from_template

REGION_NAMES = ("DEVICE_INIT", "CONTROL_POLICY", "TELEMETRY_REPORT", "HELPERS")
CPP_SOURCE_SUFFIXES = {".cpp", ".cc", ".cxx"}
CONTROLLER_SOURCE_SUFFIXES = {".py", *CPP_SOURCE_SUFFIXES}
CPP_LANGUAGE = Language(tree_sitter_cpp.language())


@dataclass(slots=True)
class ControllerInspectionResult:
    path: str
    language: str
    scenario: str | None
    robot_family: str = "e-puck"
    robot_profile: str = "e-puck"
    integration_mode: str = "unknown"
    valid_source: bool = False
    editable_regions: list[str] = field(default_factory=list)
    markers_present: bool = False
    has_robot_init: bool = False
    has_step_loop: bool = False
    has_from_robot: bool = False
    has_begin_step: bool = False
    has_report_step: bool = False
    default_camera: str | None = None
    device_bindings: list[str] = field(default_factory=list)
    device_access_inventory: list[dict[str, Any]] = field(default_factory=list)
    telemetry_sections: dict[str, list[str]] = field(default_factory=dict)
    telemetry_contract: dict[str, Any] = field(default_factory=dict)
    benchmark_readiness: dict[str, Any] = field(default_factory=dict)
    benchmark_contract_gaps: list[str] = field(default_factory=list)
    line_follow_contract_gaps: list[str] = field(default_factory=list)
    camera_processing_readiness: dict[str, Any] = field(default_factory=dict)
    reacquisition_readiness: dict[str, Any] = field(default_factory=dict)
    obstacle_contract_gaps: list[str] = field(default_factory=list)
    obstacle_readiness: dict[str, Any] = field(default_factory=dict)
    clearance_recovery_readiness: dict[str, Any] = field(default_factory=dict)
    waypoint_contract_gaps: list[str] = field(default_factory=list)
    waypoint_progress_readiness: dict[str, Any] = field(default_factory=dict)
    waypoint_recovery_readiness: dict[str, Any] = field(default_factory=dict)
    function_inventory: list[str] = field(default_factory=list)
    editable_symbols: list[str] = field(default_factory=list)
    compile_readiness: dict[str, Any] = field(default_factory=dict)
    runtime_readiness: dict[str, Any] = field(default_factory=dict)
    controller_fix_hints: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    status: str = "misconfigured"
    summary: dict[str, Any] = field(default_factory=dict)
    support_tier: str = "experimental-foundation"
    next_step: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def controller_sdk_dir() -> Path:
    return Path(__file__).resolve().parent / "cpp"


def controller_sdk_header() -> Path:
    return controller_sdk_dir() / "controller_agent.hpp"


def detect_controller_language(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in CPP_SOURCE_SUFFIXES:
        return "cpp"
    if suffix == ".exe":
        return "cpp-binary"
    return "unknown"


def inspect_controller(
    path: Path,
    *,
    scenario: str | None = None,
    spec_path: Path | None = None,
    robot_profile: str | None = None,
) -> ControllerInspectionResult:
    resolved = path if path.is_absolute() else (Path.cwd() / path).resolve()
    language = detect_controller_language(resolved)
    scenario_name = scenario or _scenario_from_spec(spec_path)
    effective_robot_profile = robot_profile or _robot_profile_from_spec(spec_path)
    scenario_def = get_scenario(scenario_name, robot_profile=effective_robot_profile) if scenario_name else None
    if scenario_def:
        effective_robot_profile = scenario_def.robot_profile

    if not resolved.exists():
        return _finalize_inspection_result(
            ControllerInspectionResult(
                path=str(resolved),
                language=language,
                scenario=scenario_name,
                robot_family=get_robot_profile(effective_robot_profile).robot_family,
                robot_profile=get_robot_profile(effective_robot_profile).robot_profile,
                integration_mode="unknown",
                valid_source=False,
                issues=["Controller file does not exist."],
            )
        )

    if language not in {"python", "cpp"}:
        return _finalize_inspection_result(
            ControllerInspectionResult(
                path=str(resolved),
                language=language,
                scenario=scenario_name,
                robot_family=get_robot_profile(effective_robot_profile).robot_family,
                robot_profile=get_robot_profile(effective_robot_profile).robot_profile,
                integration_mode="unknown",
                valid_source=False,
                issues=["Unsupported controller source type."],
            )
        )

    try:
        source = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        return _finalize_inspection_result(
            ControllerInspectionResult(
                path=str(resolved),
                language=language,
                scenario=scenario_name,
                robot_family=get_robot_profile(effective_robot_profile).robot_family,
                robot_profile=get_robot_profile(effective_robot_profile).robot_profile,
                integration_mode="unknown",
                valid_source=False,
                issues=[f"Unable to read controller file: {exc}"],
            )
        )

    if language == "python":
        inspection = _inspect_python_source(resolved, source, scenario_name, effective_robot_profile)
    else:
        inspection = _inspect_cpp_source(resolved, source, scenario_name, effective_robot_profile)

    if scenario_def:
        benchmark_ready, benchmark_issues = _benchmark_readiness_from_sections(
            scenario_def.required_sensor_keys,
            scenario_def.required_metric_keys,
            scenario_def.required_actuator_keys,
            inspection.telemetry_sections,
        )
        telemetry_contract = _telemetry_contract(
            scenario_def.required_sensor_keys,
            scenario_def.required_metric_keys,
            scenario_def.required_actuator_keys,
            inspection.telemetry_sections,
        )
        inspection.benchmark_readiness = {
            "ready": benchmark_ready,
            "benchmark_name": scenario_def.name,
            "expected_default_camera": scenario_def.default_camera,
            "expected_sensor_keys": list(scenario_def.required_sensor_keys),
            "expected_metric_keys": list(scenario_def.required_metric_keys),
            "expected_actuator_keys": list(scenario_def.required_actuator_keys),
            "issues": benchmark_issues,
        }
        inspection.telemetry_contract = telemetry_contract
        inspection.benchmark_contract_gaps = _benchmark_contract_gaps(inspection, scenario_def, benchmark_issues)
    else:
        inspection.benchmark_readiness = {
            "ready": False,
            "benchmark_name": None,
            "expected_default_camera": None,
            "expected_sensor_keys": [],
            "expected_metric_keys": [],
            "expected_actuator_keys": [],
            "issues": ["No benchmark scenario context provided."],
        }
        inspection.telemetry_contract = {
            "expected": {"sensors": [], "metrics": [], "actuators": []},
            "reported": inspection.telemetry_sections,
            "missing": {"sensors": [], "metrics": [], "actuators": []},
            "extra": {"sensors": inspection.telemetry_sections.get("sensors", []), "metrics": inspection.telemetry_sections.get("metrics", []), "actuators": inspection.telemetry_sections.get("actuators", [])},
        }
        inspection.benchmark_contract_gaps = ["No benchmark scenario context provided."]
    inspection.line_follow_contract_gaps = _line_follow_contract_gaps(inspection)
    inspection.camera_processing_readiness = _camera_processing_readiness(inspection)
    inspection.reacquisition_readiness = _reacquisition_readiness(inspection)
    inspection.obstacle_contract_gaps = _obstacle_contract_gaps(inspection)
    inspection.obstacle_readiness = _obstacle_readiness(inspection)
    inspection.clearance_recovery_readiness = _clearance_recovery_readiness(inspection)
    inspection.waypoint_contract_gaps = _waypoint_contract_gaps(inspection)
    inspection.waypoint_progress_readiness = _waypoint_progress_readiness(inspection)
    inspection.waypoint_recovery_readiness = _waypoint_recovery_readiness(inspection)
    inspection.compile_readiness = _compile_readiness(inspection)
    inspection.runtime_readiness = _runtime_readiness(inspection)
    inspection.controller_fix_hints = _controller_fix_hints(inspection)
    return _finalize_inspection_result(inspection)


def scaffold_source(*, scenario: str, language: str, robot_profile: str = "e-puck") -> tuple[str, dict[str, Any]]:
    scenario_def = get_scenario(scenario, robot_profile=robot_profile)
    if language == "python":
        return _python_template_for_scenario(scenario, robot_profile=robot_profile), {
            "language": language,
            "scenario": scenario_def.name,
            "default_camera": scenario_def.default_camera,
            "robot_family": scenario_def.robot_family,
            "robot_profile": scenario_def.robot_profile,
        }
    if language == "cpp":
        return _cpp_template_for_scenario(scenario, robot_profile=robot_profile), {
            "language": language,
            "scenario": scenario_def.name,
            "default_camera": scenario_def.default_camera,
            "sdk_header": str(controller_sdk_header()),
            "robot_family": scenario_def.robot_family,
            "robot_profile": scenario_def.robot_profile,
        }
    raise KitError(
        "unsupported-controller-language",
        f"Unsupported controller language '{language}'.",
        details={"supported_languages": ["python", "cpp"]},
    )


def scaffold_controller_artifacts(path: Path, *, scenario: str, language: str, robot_profile: str = "e-puck", force: bool = False) -> dict[str, Any]:
    target = path if path.is_absolute() else (Path.cwd() / path).resolve()
    if target.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)

    source, metadata = scaffold_source(scenario=scenario, language=language, robot_profile=robot_profile)
    target.write_text(source, encoding="utf-8")

    copied_files: list[str] = []
    if language == "cpp":
        sdk_header_target = target.parent / controller_sdk_header().name
        shutil.copy2(controller_sdk_header(), sdk_header_target)
        copied_files.append(str(sdk_header_target))

    return {
        "path": str(target),
        "scenario": scenario,
        "language": language,
        "default_camera": metadata.get("default_camera"),
        "robot_family": metadata.get("robot_family"),
        "robot_profile": metadata.get("robot_profile"),
        "copied_files": copied_files,
        "editable_regions": list(REGION_NAMES),
    }


def edit_controller(path: Path, *, plan_path: Path | None = None, plan: dict[str, Any] | None = None, robot_profile: str | None = None) -> dict[str, Any]:
    target = path if path.is_absolute() else (Path.cwd() / path).resolve()
    if not target.exists():
        raise FileNotFoundError(f"Controller file does not exist: {target}")
    plan_payload = plan or _read_plan_json(plan_path)
    language = detect_controller_language(target)
    if language not in {"python", "cpp"}:
        raise KitError("unsupported-controller-language", f"Unsupported controller source type for edit: {target.suffix}")

    source = target.read_text(encoding="utf-8")
    operations = plan_payload.get("operations")
    if not isinstance(operations, list) or not operations:
        raise KitError("controller-edit-plan-invalid", "Controller edit plan must contain at least one operation.")

    updated = source
    applied: list[str] = []
    for operation in operations:
        if not isinstance(operation, dict):
            raise KitError("controller-edit-plan-invalid", "Controller edit operations must be objects.")
        op_type = str(operation.get("type") or "")
        if not op_type:
            raise KitError("controller-edit-plan-invalid", "Controller edit operations must define a type.")
        updated = _apply_controller_operation(updated, language=language, operation=operation)
        applied.append(op_type)

    if updated == source:
        raise KitError("controller-edit-noop", "Controller edit plan did not produce any source changes.")

    target.write_text(updated, encoding="utf-8")
    inspection = inspect_controller(
        target,
        scenario=plan_payload.get("scenario_context", {}).get("scenario"),
        robot_profile=robot_profile or plan_payload.get("scenario_context", {}).get("robot_profile"),
    )
    return {
        "path": str(target),
        "language": language,
        "robot_family": inspection.robot_family,
        "robot_profile": inspection.robot_profile,
        "applied_operations": applied,
        "editable_regions": inspection.editable_regions,
        "status": inspection.status,
        "summary": {
            "applied_operation_count": len(applied),
            "benchmark_ready": bool(inspection.benchmark_readiness.get("ready")),
            "benchmark_contract_gap_count": len(inspection.benchmark_contract_gaps),
            "line_follow_contract_gap_count": len(inspection.line_follow_contract_gaps),
            "obstacle_contract_gap_count": len(inspection.obstacle_contract_gaps),
            "waypoint_contract_gap_count": len(inspection.waypoint_contract_gaps),
            "issue_count": len(inspection.issues),
        },
        "benchmark_readiness": inspection.benchmark_readiness,
        "benchmark_contract_gaps": inspection.benchmark_contract_gaps,
        "line_follow_contract_gaps": inspection.line_follow_contract_gaps,
        "camera_processing_readiness": inspection.camera_processing_readiness,
        "reacquisition_readiness": inspection.reacquisition_readiness,
        "obstacle_contract_gaps": inspection.obstacle_contract_gaps,
        "obstacle_readiness": inspection.obstacle_readiness,
        "clearance_recovery_readiness": inspection.clearance_recovery_readiness,
        "waypoint_contract_gaps": inspection.waypoint_contract_gaps,
        "waypoint_progress_readiness": inspection.waypoint_progress_readiness,
        "waypoint_recovery_readiness": inspection.waypoint_recovery_readiness,
        "controller_fix_hints": inspection.controller_fix_hints,
        "support_tier": "experimental-foundation",
        "next_step": (
            f"Run `webots-kit benchmark run {inspection.scenario} --controller \"{target}\" ...`."
            if inspection.status == "ready" and inspection.scenario
            else f"Run `webots-kit controller validate \"{target}\" --strict --json`."
        ),
    }


def build_controller_runtime_command(
    path: Path,
    *,
    output_dir: Path | None = None,
) -> tuple[list[str], str, list[str]]:
    resolved = path if path.is_absolute() else (Path.cwd() / path).resolve()
    language = detect_controller_language(resolved)
    if language == "python":
        return [current_python(), str(resolved)], str(resolved.parent), []
    if language == "cpp":
        compile_result = compile_cpp_controller(resolved, output_dir=output_dir)
        return [str(compile_result["binary_path"])], str(Path(str(compile_result["binary_path"])).parent), compile_result["artifacts"]
    if language == "cpp-binary":
        return [str(resolved)], str(resolved.parent), []
    raise KitError(
        "unsupported-controller-language",
        f"Unsupported controller source type '{resolved.suffix}'.",
        details={"supported_suffixes": sorted(CONTROLLER_SOURCE_SUFFIXES | {'.exe'})},
    )


def compile_cpp_controller(path: Path, *, output_dir: Path | None = None) -> dict[str, Any]:
    source = path if path.is_absolute() else (Path.cwd() / path).resolve()
    if not source.exists():
        raise FileNotFoundError(f"C++ controller file does not exist: {source}")

    webots = get_webots_environment()
    compiler = getattr(webots, "cpp_compiler", webots.webots_home / "msys64" / "mingw64" / "bin" / "g++.exe")
    if not compiler.exists():
        raise KitError("cpp-compiler-missing", "Webots MinGW compiler was not found.", details={"compiler": str(compiler)})

    build_dir = output_dir if output_dir else Path(tempfile.mkdtemp(prefix="webots-kit-cpp-", dir=Path(tempfile.gettempdir())))
    build_dir.mkdir(parents=True, exist_ok=True)
    binary_path = build_dir / f"{source.stem}.exe"
    command = [
        str(compiler),
        "-std=c++17",
        "-O2",
        "-D_GLIBCXX_USE_CXX11_ABI=1",
        "-I",
        str(getattr(webots, "cpp_controller_include_path", webots.webots_home / "include" / "controller" / "cpp")),
        "-I",
        str(controller_sdk_dir()),
        "-I",
        str(source.parent),
        str(source),
        "-L",
        str(getattr(webots, "cpp_controller_library_path", webots.controller_library_path)),
        "-lCppController",
        "-lController",
        "-lws2_32",
        "-Wl,--enable-auto-import",
        "-mwindows",
        "-Wl,-subsystem,windows",
        "-o",
        str(binary_path),
    ]
    env = build_process_env(include_src=False)
    extra_path_entries = [str(compiler.parent)]
    runtime_bin = compiler.parent / "cpp"
    if runtime_bin.exists():
        extra_path_entries.append(str(runtime_bin))
    env["PATH"] = os.pathsep.join([*extra_path_entries, env.get("PATH", "")])
    result = subprocess.run(  # noqa: S603
        command,
        cwd=str(source.parent),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise KitError(
            "cpp-controller-build-failed",
            f"Failed to compile C++ controller '{source.name}'.",
            details={"stdout": result.stdout, "stderr": result.stderr, "command": command},
        )
    return {
        "language": "cpp",
        "source_path": str(source),
        "binary_path": str(binary_path),
        "artifacts": [str(binary_path)],
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def format_controller_inspection_report(result: ControllerInspectionResult) -> str:
    readiness = result.benchmark_readiness
    lines = [
        f"controller_inspect: {result.status}",
        f"path: {result.path}",
        f"language: {result.language}",
        f"scenario: {result.scenario}",
        f"robot_profile: {result.robot_profile}",
        f"integration_mode: {result.integration_mode}",
        f"summary: {result.summary}",
        f"editable_regions: {result.editable_regions}",
        f"default_camera: {result.default_camera}",
        f"device_bindings: {result.device_bindings}",
        f"benchmark_ready: {readiness.get('ready')}",
    ]
    if result.function_inventory:
        lines.append(f"function_inventory: {result.function_inventory}")
    if result.editable_symbols:
        lines.append(f"editable_symbols: {result.editable_symbols}")
    if result.telemetry_sections:
        lines.append(f"telemetry_sections: {result.telemetry_sections}")
    if result.benchmark_contract_gaps:
        lines.append(f"benchmark_contract_gaps: {result.benchmark_contract_gaps}")
    if result.line_follow_contract_gaps:
        lines.append(f"line_follow_contract_gaps: {result.line_follow_contract_gaps}")
    if result.camera_processing_readiness:
        lines.append(f"camera_processing_readiness: {result.camera_processing_readiness}")
    if result.reacquisition_readiness:
        lines.append(f"reacquisition_readiness: {result.reacquisition_readiness}")
    if result.obstacle_contract_gaps:
        lines.append(f"obstacle_contract_gaps: {result.obstacle_contract_gaps}")
    if result.obstacle_readiness:
        lines.append(f"obstacle_readiness: {result.obstacle_readiness}")
    if result.clearance_recovery_readiness:
        lines.append(f"clearance_recovery_readiness: {result.clearance_recovery_readiness}")
    if result.waypoint_contract_gaps:
        lines.append(f"waypoint_contract_gaps: {result.waypoint_contract_gaps}")
    if result.waypoint_progress_readiness:
        lines.append(f"waypoint_progress_readiness: {result.waypoint_progress_readiness}")
    if result.waypoint_recovery_readiness:
        lines.append(f"waypoint_recovery_readiness: {result.waypoint_recovery_readiness}")
    if result.controller_fix_hints:
        lines.append(f"controller_fix_hints: {result.controller_fix_hints}")
    if result.issues:
        lines.append("issues:")
        lines.extend(f"- {issue}" for issue in result.issues)
    lines.append(f"support_tier: {result.support_tier}")
    lines.append(f"next_step: {result.next_step}")
    return "\n".join(lines)


def format_controller_edit_report(payload: dict[str, Any]) -> str:
    lines = [
        f"controller_edit: {payload.get('status')}",
        f"path: {payload.get('path')}",
        f"language: {payload.get('language')}",
        f"robot_profile: {payload.get('robot_profile')}",
        f"summary: {payload.get('summary')}",
        f"editable_regions: {payload.get('editable_regions')}",
    ]
    if payload.get("benchmark_contract_gaps"):
        lines.append(f"benchmark_contract_gaps: {payload.get('benchmark_contract_gaps')}")
    if payload.get("line_follow_contract_gaps"):
        lines.append(f"line_follow_contract_gaps: {payload.get('line_follow_contract_gaps')}")
    if payload.get("camera_processing_readiness"):
        lines.append(f"camera_processing_readiness: {payload.get('camera_processing_readiness')}")
    if payload.get("reacquisition_readiness"):
        lines.append(f"reacquisition_readiness: {payload.get('reacquisition_readiness')}")
    if payload.get("obstacle_contract_gaps"):
        lines.append(f"obstacle_contract_gaps: {payload.get('obstacle_contract_gaps')}")
    if payload.get("obstacle_readiness"):
        lines.append(f"obstacle_readiness: {payload.get('obstacle_readiness')}")
    if payload.get("clearance_recovery_readiness"):
        lines.append(f"clearance_recovery_readiness: {payload.get('clearance_recovery_readiness')}")
    if payload.get("waypoint_contract_gaps"):
        lines.append(f"waypoint_contract_gaps: {payload.get('waypoint_contract_gaps')}")
    if payload.get("waypoint_progress_readiness"):
        lines.append(f"waypoint_progress_readiness: {payload.get('waypoint_progress_readiness')}")
    if payload.get("waypoint_recovery_readiness"):
        lines.append(f"waypoint_recovery_readiness: {payload.get('waypoint_recovery_readiness')}")
    if payload.get("controller_fix_hints"):
        lines.append(f"controller_fix_hints: {payload.get('controller_fix_hints')}")
    lines.append(f"support_tier: {payload.get('support_tier')}")
    lines.append(f"next_step: {payload.get('next_step')}")
    return "\n".join(lines)


def _read_plan_json(plan_path: Path | None) -> dict[str, Any]:
    if plan_path is None:
        raise KitError("controller-edit-plan-missing", "Controller edit requires a --plan JSON file.")
    resolved = plan_path if plan_path.is_absolute() else (Path.cwd() / plan_path).resolve()
    return json.loads(resolved.read_text(encoding="utf-8"))


def _scenario_from_spec(spec_path: Path | None) -> str | None:
    if spec_path is None:
        return None
    from .scenario_ops import load_scenario_spec

    spec = load_scenario_spec(spec_path)
    kind = str(spec.scenario.get("kind") or "")
    return {
        "line-follow": "line-follower",
        "waypoint-nav": "waypoint-nav",
        "obstacle-avoidance": "obstacle-avoidance",
    }.get(kind)


def _robot_profile_from_spec(spec_path: Path | None) -> str:
    if spec_path is None:
        return "e-puck"
    from .scenario_ops import load_scenario_spec

    spec = load_scenario_spec(spec_path)
    return robot_profile_from_template(str(spec.robot.get("template") or "e-puck"))


def _finalize_inspection_result(result: ControllerInspectionResult) -> ControllerInspectionResult:
    result.status = "ready" if result.valid_source and not result.issues else "misconfigured"
    result.summary = {
        "issue_count": len(result.issues),
        "function_count": len(result.function_inventory),
        "editable_symbol_count": len(result.editable_symbols),
        "device_binding_count": len(result.device_bindings),
        "benchmark_contract_gap_count": len(result.benchmark_contract_gaps),
        "line_follow_contract_gap_count": len(result.line_follow_contract_gaps),
        "obstacle_contract_gap_count": len(result.obstacle_contract_gaps),
        "waypoint_contract_gap_count": len(result.waypoint_contract_gaps),
        "benchmark_ready": bool(result.benchmark_readiness.get("ready")),
    }
    result.next_step = (
        "Run `webots-kit controller validate <path> --strict --json` or apply `webots-kit controller edit <path> --plan <plan.json>`."
        if result.status == "ready"
        else "Fix the listed inspection issues or benchmark contract gaps, then rerun `webots-kit controller validate --strict`."
    )
    return result


def _find_regions(source: str) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    for name in REGION_NAMES:
        start_match = re.search(rf"webots-kit region {re.escape(name)} start[^\n]*\n", source)
        end_match = re.search(rf"\n[^\n]*webots-kit region {re.escape(name)} end", source)
        if start_match and end_match and end_match.start() >= start_match.end():
            result[name] = (start_match.end(), end_match.start())
    return result


def _benchmark_readiness_from_sections(
    expected_sensors: tuple[str, ...],
    expected_metrics: tuple[str, ...],
    expected_actuators: tuple[str, ...],
    telemetry_sections: dict[str, list[str]],
) -> tuple[bool, list[str]]:
    issues: list[str] = []
    reported_sensors = set(telemetry_sections.get("sensors", []))
    reported_metrics = set(telemetry_sections.get("metrics", []))
    reported_actuators = set(telemetry_sections.get("actuators", []))
    if not set(expected_sensors).issubset(reported_sensors):
        issues.append("Sensor telemetry keys do not match benchmark expectations.")
    if not set(expected_metrics).issubset(reported_metrics):
        issues.append("Metric telemetry keys do not match benchmark expectations.")
    if not set(expected_actuators).issubset(reported_actuators):
        issues.append("Actuator telemetry keys do not match benchmark expectations.")
    return not issues, issues


def _telemetry_contract(
    expected_sensors: tuple[str, ...],
    expected_metrics: tuple[str, ...],
    expected_actuators: tuple[str, ...],
    telemetry_sections: dict[str, list[str]],
) -> dict[str, Any]:
    expected = {
        "sensors": list(expected_sensors),
        "metrics": list(expected_metrics),
        "actuators": list(expected_actuators),
    }
    reported = {
        "sensors": list(telemetry_sections.get("sensors", [])),
        "metrics": list(telemetry_sections.get("metrics", [])),
        "actuators": list(telemetry_sections.get("actuators", [])),
    }
    missing = {
        section: sorted(set(expected[section]) - set(reported[section]))
        for section in expected
    }
    extra = {
        section: sorted(set(reported[section]) - set(expected[section]))
        for section in expected
    }
    return {"expected": expected, "reported": reported, "missing": missing, "extra": extra}


def _benchmark_contract_gaps(
    inspection: ControllerInspectionResult,
    scenario_def: Any,
    readiness_issues: list[str],
) -> list[str]:
    gaps = list(readiness_issues)
    if scenario_def.default_camera and inspection.default_camera != scenario_def.default_camera:
        gaps.append(f"default_camera should be '{scenario_def.default_camera}'.")
    if scenario_def.default_camera and scenario_def.default_camera not in inspection.device_bindings:
        gaps.append(f"Default camera '{scenario_def.default_camera}' is not bound through getDevice(...).")
    if not inspection.has_begin_step:
        gaps.append("Missing begin_step() in control loop.")
    if not inspection.has_report_step:
        gaps.append("Missing report_step(...) telemetry emission.")
    return sorted(dict.fromkeys(gaps))


def _line_follow_contract_gaps(inspection: ControllerInspectionResult) -> list[str]:
    if inspection.scenario != "line-follower" or inspection.robot_profile != "monsterborg-4wd":
        return []
    metrics = set(inspection.telemetry_sections.get("metrics", []))
    gaps: list[str] = []
    for key in ("line_confidence", "camera_signal_strength", "tracking_state_code", "speed_saturation"):
        if key not in metrics:
            gaps.append(f"Missing line-follow metric '{key}'.")
    return sorted(dict.fromkeys(gaps))


def _camera_processing_readiness(inspection: ControllerInspectionResult) -> dict[str, Any]:
    if inspection.scenario != "line-follower" or inspection.robot_profile != "monsterborg-4wd":
        return {"ready": True, "issues": []}
    metrics = set(inspection.telemetry_sections.get("metrics", []))
    sensor_keys = set(inspection.telemetry_sections.get("sensors", []))
    issues: list[str] = []
    if not {"camera_left_band", "camera_center_band", "camera_right_band"}.issubset(sensor_keys):
        issues.append("camera_bands_missing")
    if "line_confidence" not in metrics:
        issues.append("line_confidence_missing")
    if "camera_signal_strength" not in metrics:
        issues.append("camera_signal_strength_missing")
    return {
        "ready": not issues,
        "issues": issues,
        "camera_band_keys": sorted(sensor_keys.intersection({"camera_left_band", "camera_center_band", "camera_right_band"})),
    }


def _reacquisition_readiness(inspection: ControllerInspectionResult) -> dict[str, Any]:
    if inspection.scenario != "line-follower" or inspection.robot_profile != "monsterborg-4wd":
        return {"ready": True, "issues": []}
    metrics = set(inspection.telemetry_sections.get("metrics", []))
    issues: list[str] = []
    if "tracking_state_code" not in metrics:
        issues.append("tracking_state_code_missing")
    if "speed_saturation" not in metrics:
        issues.append("speed_saturation_missing")
    if "line_confidence" not in metrics:
        issues.append("reacquisition_state_machine_missing")
    return {
        "ready": not issues,
        "issues": issues,
    }


def _obstacle_contract_gaps(inspection: ControllerInspectionResult) -> list[str]:
    if inspection.scenario != "obstacle-avoidance" or inspection.robot_profile != "monsterborg-4wd":
        return []
    metrics = set(inspection.telemetry_sections.get("metrics", []))
    gaps: list[str] = []
    for key in ("front_clearance_margin", "clearance_violation", "heading_recovery_events", "stalled_steps", "avoidance_state_code"):
        if key not in metrics:
            gaps.append(f"Missing obstacle metric '{key}'.")
    return sorted(dict.fromkeys(gaps))


def _obstacle_readiness(inspection: ControllerInspectionResult) -> dict[str, Any]:
    if inspection.scenario != "obstacle-avoidance" or inspection.robot_profile != "monsterborg-4wd":
        return {"ready": True, "issues": []}
    sensors = set(inspection.telemetry_sections.get("sensors", []))
    metrics = set(inspection.telemetry_sections.get("metrics", []))
    issues: list[str] = []
    if not {"front_range", "heading", "yaw_rate", "left_encoder", "right_encoder"}.issubset(sensors):
        issues.append("monsterborg_obstacle_sensor_contract_incomplete")
    if not {"obstacle_pressure", "mean_forward_speed", "front_clearance_margin", "stalled_steps"}.issubset(metrics):
        issues.append("monsterborg_obstacle_metric_contract_incomplete")
    return {"ready": not issues, "issues": issues}


def _clearance_recovery_readiness(inspection: ControllerInspectionResult) -> dict[str, Any]:
    if inspection.scenario != "obstacle-avoidance" or inspection.robot_profile != "monsterborg-4wd":
        return {"ready": True, "issues": []}
    metrics = set(inspection.telemetry_sections.get("metrics", []))
    issues: list[str] = []
    if "heading_recovery_events" not in metrics:
        issues.append("heading_recovery_events_missing")
    if "avoidance_state_code" not in metrics:
        issues.append("avoidance_state_code_missing")
    if "clearance_violation" not in metrics:
        issues.append("clearance_violation_missing")
    return {"ready": not issues, "issues": issues}


def _waypoint_contract_gaps(inspection: ControllerInspectionResult) -> list[str]:
    if inspection.scenario != "waypoint-nav" or inspection.robot_profile != "monsterborg-4wd":
        return []
    metrics = set(inspection.telemetry_sections.get("metrics", []))
    gaps: list[str] = []
    for key in ("progress_ratio", "distance_to_goal_estimate", "heading_alignment_error", "path_deviation_score", "waypoint_recovery_events", "stalled_steps"):
        if key not in metrics:
            gaps.append(f"Missing waypoint metric '{key}'.")
    return sorted(dict.fromkeys(gaps))


def _waypoint_progress_readiness(inspection: ControllerInspectionResult) -> dict[str, Any]:
    if inspection.scenario != "waypoint-nav" or inspection.robot_profile != "monsterborg-4wd":
        return {"ready": True, "issues": []}
    sensors = set(inspection.telemetry_sections.get("sensors", []))
    metrics = set(inspection.telemetry_sections.get("metrics", []))
    issues: list[str] = []
    if not {"front_range", "heading", "yaw_rate", "left_encoder", "right_encoder"}.issubset(sensors):
        issues.append("monsterborg_waypoint_sensor_contract_incomplete")
    if not {"progress_ratio", "distance_to_goal_estimate", "heading_alignment_error", "path_deviation_score", "mean_forward_speed"}.issubset(metrics):
        issues.append("monsterborg_waypoint_metric_contract_incomplete")
    return {"ready": not issues, "issues": issues}


def _waypoint_recovery_readiness(inspection: ControllerInspectionResult) -> dict[str, Any]:
    if inspection.scenario != "waypoint-nav" or inspection.robot_profile != "monsterborg-4wd":
        return {"ready": True, "issues": []}
    metrics = set(inspection.telemetry_sections.get("metrics", []))
    issues: list[str] = []
    if "waypoint_recovery_events" not in metrics:
        issues.append("waypoint_recovery_events_missing")
    if "waypoint_state_code" not in metrics:
        issues.append("waypoint_state_code_missing")
    if "stalled_steps" not in metrics:
        issues.append("waypoint_stalled_steps_missing")
    return {"ready": not issues, "issues": issues}


def _compile_readiness(inspection: ControllerInspectionResult) -> dict[str, Any]:
    if inspection.language != "cpp":
        return {"supported": False, "required": False, "ready": True, "issues": []}
    issues: list[str] = []
    if not inspection.has_from_robot:
        issues.append("ControllerAgent::from_robot(...) is missing.")
    if not inspection.has_report_step:
        issues.append("report_step(...) is missing.")
    return {"supported": True, "required": True, "ready": not issues, "issues": issues}


def _runtime_readiness(inspection: ControllerInspectionResult) -> dict[str, Any]:
    issues: list[str] = []
    if not inspection.has_robot_init:
        issues.append("Robot initialization missing.")
    if not inspection.has_step_loop:
        issues.append("step loop missing.")
    if not inspection.has_from_robot:
        issues.append("ControllerAgent integration missing.")
    if not inspection.has_begin_step:
        issues.append("begin_step() missing.")
    if not inspection.has_report_step:
        issues.append("report_step(...) missing.")
    return {"ready": not issues, "issues": issues}


def _controller_fix_hints(inspection: ControllerInspectionResult) -> list[str]:
    hints: list[str] = []
    contract = inspection.telemetry_contract
    missing = contract.get("missing") if isinstance(contract, dict) else {}
    if isinstance(missing, dict):
        for section, keys in missing.items():
            if keys:
                hints.append(f"Populate report_step {section} keys: {', '.join(keys)}.")
    for issue in inspection.benchmark_contract_gaps:
        if "default_camera" in issue or "camera" in issue:
            hints.append("Align ControllerAgent.from_robot default_camera with the benchmark scenario.")
        elif "Sensor telemetry keys" in issue:
            hints.append("Emit the required sensor telemetry keys in report_step(...).")
        elif "Metric telemetry keys" in issue:
            hints.append("Emit the required metric telemetry keys in report_step(...).")
        elif "Actuator telemetry keys" in issue:
            hints.append("Emit the required actuator telemetry keys in report_step(...).")
    if inspection.language == "cpp" and inspection.compile_readiness.get("issues"):
        hints.append("Resolve C++ compile-readiness issues before rerunning validation.")
    if not inspection.runtime_readiness.get("ready"):
        hints.append("Restore the Robot -> begin_step -> report_step control loop shape before rerunning.")
    for issue in inspection.line_follow_contract_gaps:
        if "line-follow metric" in issue:
            hints.append("Emit line_confidence, camera_signal_strength, tracking_state_code, and speed_saturation for MonsterBorg line-follow tuning.")
    if inspection.scenario == "line-follower":
        if not inspection.camera_processing_readiness.get("ready"):
            hints.append("Add multi-row camera processing and explicit confidence telemetry before rerunning the line-follow benchmark.")
        if not inspection.reacquisition_readiness.get("ready"):
            hints.append("Implement track/predict/search/recover state transitions so line reacquisition remains observable and tunable.")
    if inspection.scenario == "obstacle-avoidance":
        if inspection.obstacle_contract_gaps:
            hints.append("Emit front_clearance_margin, clearance_violation, heading_recovery_events, stalled_steps, and avoidance_state_code for MonsterBorg obstacle tuning.")
        if not inspection.obstacle_readiness.get("ready"):
            hints.append("Bind front_range, heading, yaw_rate, left_encoder, and right_encoder before rerunning the obstacle benchmark.")
        if not inspection.clearance_recovery_readiness.get("ready"):
            hints.append("Add an explicit clearance-recovery state machine so obstacle recovery and stalls remain observable.")
    if inspection.scenario == "waypoint-nav":
        if inspection.waypoint_contract_gaps:
            hints.append("Emit progress_ratio, distance_to_goal_estimate, heading_alignment_error, path_deviation_score, waypoint_recovery_events, and stalled_steps for MonsterBorg waypoint tuning.")
        if not inspection.waypoint_progress_readiness.get("ready"):
            hints.append("Expose forward progress and heading-alignment telemetry before rerunning the waypoint benchmark.")
        if not inspection.waypoint_recovery_readiness.get("ready"):
            hints.append("Add an explicit align/advance/recover waypoint state machine so recovery events stay tunable.")
    return sorted(dict.fromkeys(hints))


def _inspect_python_source(path: Path, source: str, scenario_name: str | None, robot_profile: str) -> ControllerInspectionResult:
    profile = get_robot_profile(robot_profile)
    result = ControllerInspectionResult(
        path=str(path),
        language="python",
        scenario=scenario_name,
        robot_family=profile.robot_family,
        robot_profile=profile.robot_profile,
        integration_mode="unknown",
        valid_source=True,
    )
    regions = _find_regions(source)
    result.editable_regions = [region for region in REGION_NAMES if region in regions]
    result.markers_present = bool(regions)
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        result.valid_source = False
        result.issues.append(f"Syntax error: {exc.msg} at line {exc.lineno}")
        return result

    imported_controller_agent = False
    literal_dict_assignments: dict[str, set[str]] = {}
    literal_keys: dict[str, list[str]] = {}
    editable_symbols: list[str] = []
    functions: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "webots_mcp_kit.agent":
            if any(alias.name == "ControllerAgent" for alias in node.names):
                imported_controller_agent = True
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            keys = _literal_dict_keys(node.value)
            if keys is not None:
                literal_dict_assignments[node.targets[0].id] = keys
            target_name = node.targets[0].id
            if target_name.isupper():
                editable_symbols.append(target_name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "Robot":
                result.has_robot_init = True
            if isinstance(node.func, ast.Attribute) and node.func.attr == "step":
                result.has_step_loop = True
            if isinstance(node.func, ast.Attribute) and node.func.attr == "from_robot":
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "ControllerAgent":
                    result.has_from_robot = True
                    result.default_camera = _string_keyword(node, "default_camera")
            if isinstance(node.func, ast.Attribute) and node.func.attr == "begin_step":
                result.has_begin_step = True
            if isinstance(node.func, ast.Attribute) and node.func.attr == "report_step":
                result.has_report_step = True
                for keyword in node.keywords:
                    if not keyword.arg:
                        continue
                    keys = _literal_dict_keys(keyword.value)
                    if keys is None and isinstance(keyword.value, ast.Name):
                        keys = literal_dict_assignments.get(keyword.value.id)
                    if keys is not None:
                        literal_keys[keyword.arg] = sorted(keys)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "getDevice" and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    result.device_bindings.append(first.value)
                    result.device_access_inventory.append(
                        {
                            "device": first.value,
                            "accessor": "getDevice",
                            "line": getattr(node, "lineno", None),
                        }
                    )

    result.integration_mode = "controller-agent" if imported_controller_agent else "plain-webots"
    result.function_inventory = sorted(dict.fromkeys(functions))
    result.editable_symbols = sorted(dict.fromkeys(editable_symbols))
    result.telemetry_sections = {
        section: literal_keys.get(section, [])
        for section in ("sensors", "metrics", "actuators")
        if literal_keys.get(section) is not None
    }
    if not result.has_robot_init:
        result.issues.append("No Webots Robot() initialization detected.")
    if not result.has_step_loop:
        result.issues.append("No robot.step(...) loop detected.")
    if not imported_controller_agent:
        result.issues.append("Controller must import and use ControllerAgent from webots_mcp_kit.agent.")
    if not result.has_from_robot:
        result.issues.append("ControllerAgent.from_robot(...) was not detected.")
    if not result.has_begin_step:
        result.issues.append("ControllerAgent.begin_step() was not detected.")
    if not result.has_report_step:
        result.issues.append("ControllerAgent.report_step(...) was not detected.")
    return result


def _inspect_cpp_source(path: Path, source: str, scenario_name: str | None, robot_profile: str) -> ControllerInspectionResult:
    profile = get_robot_profile(robot_profile)
    result = ControllerInspectionResult(
        path=str(path),
        language="cpp",
        scenario=scenario_name,
        robot_family=profile.robot_family,
        robot_profile=profile.robot_profile,
        integration_mode="unknown",
        valid_source=True,
    )
    regions = _find_regions(source)
    result.editable_regions = [region for region in REGION_NAMES if region in regions]
    result.markers_present = bool(regions)
    result.has_robot_init = bool(re.search(r"\bRobot\b", source))
    result.has_step_loop = bool(re.search(r"\bstep\s*\(", source))
    result.has_from_robot = "ControllerAgent::from_robot" in source
    result.has_begin_step = "begin_step(" in source
    result.has_report_step = "report_step(" in source
    result.integration_mode = "controller-agent" if result.has_from_robot else "plain-webots"

    default_camera_match = re.search(r'from_robot\s*\([^,]+,\s*"([^"]+)"', source)
    if default_camera_match:
        result.default_camera = default_camera_match.group(1)

    parser = Parser(CPP_LANGUAGE)
    tree = parser.parse(source.encode("utf-8"))
    function_inventory, editable_symbols = _cpp_inventory(tree.root_node, source.encode("utf-8"))
    result.function_inventory = function_inventory
    result.editable_symbols = editable_symbols

    device_entries = [
        {
            "device": match.group(2),
            "accessor": match.group(1),
            "line": source.count("\n", 0, match.start()) + 1,
        }
        for match in re.finditer(r'(getDevice|getCamera|getMotor|getDistanceSensor)\s*\(\s*"([^"]+)"\s*\)', source)
    ]
    result.device_access_inventory = [
        {"device": entry["device"], "accessor": entry["accessor"], "line": entry["line"]}
        for entry in device_entries
    ]
    result.device_bindings = sorted({entry["device"] for entry in device_entries})

    telemetry_sections: dict[str, list[str]] = {}
    for section in ("sensors", "metrics", "actuators"):
        match = re.search(rf"std::map<std::string,\s*double>\s+{section}\s*=\s*\{{(?P<body>.*?)\}};", source, re.DOTALL)
        if not match:
            continue
        telemetry_sections[section] = sorted(
            {
                key_match.group(1)
                for key_match in re.finditer(r'\{\s*"([^"]+)"\s*,', match.group("body"))
            }
        )
    result.telemetry_sections = telemetry_sections

    if not result.has_robot_init:
        result.issues.append("No Webots Robot initialization detected.")
    if not result.has_step_loop:
        result.issues.append("No robot.step(...) loop detected.")
    if not result.has_from_robot:
        result.issues.append("ControllerAgent::from_robot(...) was not detected.")
    if not result.has_begin_step:
        result.issues.append("ControllerAgent.begin_step() was not detected.")
    if not result.has_report_step:
        result.issues.append("ControllerAgent.report_step(...) was not detected.")
    return result


def _string_keyword(node: ast.Call, name: str) -> str | None:
    for keyword in node.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    return None


def _literal_dict_keys(node: ast.AST) -> set[str] | None:
    if isinstance(node, ast.Dict):
        keys: set[str] = set()
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.add(key.value)
        return keys
    return None


def _cpp_inventory(root: Node, source_bytes: bytes) -> tuple[list[str], list[str]]:
    functions: list[str] = []
    symbols: list[str] = []
    for node in _walk_cpp_nodes(root):
        if node.type == "function_definition":
            name = _cpp_function_name(node, source_bytes)
            if name:
                functions.append(name)
        elif node.type == "declaration":
            symbols.extend(_cpp_declared_symbols(node, source_bytes))
    return sorted(dict.fromkeys(functions)), sorted(dict.fromkeys(symbols))


def _walk_cpp_nodes(node: Node) -> list[Node]:
    nodes = [node]
    for child in node.children:
        nodes.extend(_walk_cpp_nodes(child))
    return nodes


def _cpp_function_name(node: Node, source_bytes: bytes) -> str | None:
    declarator = node.child_by_field_name("declarator")
    if declarator is None:
        return None
    return _cpp_identifier_from_declarator(declarator, source_bytes)


def _cpp_identifier_from_declarator(node: Node, source_bytes: bytes) -> str | None:
    if node.type == "identifier":
        return source_bytes[node.start_byte : node.end_byte].decode("utf-8")
    for child in node.children:
        name = _cpp_identifier_from_declarator(child, source_bytes)
        if name:
            return name
    return None


def _cpp_declared_symbols(node: Node, source_bytes: bytes) -> list[str]:
    names: list[str] = []
    for child in node.children:
        if child.type == "init_declarator":
            name = _cpp_identifier_from_declarator(child, source_bytes)
            if name:
                names.append(name)
    return names


def _replace_region(source: str, name: str, replacement: str) -> str:
    regions = _find_regions(source)
    if name not in regions:
        raise KitError("controller-edit-unsafe", f"Controller does not expose editable region '{name}'.")
    start, end = regions[name]
    replacement = replacement.rstrip()
    if replacement:
        replacement += "\n"
    return source[:start] + replacement + source[end:]


def _apply_controller_operation(source: str, *, language: str, operation: dict[str, Any]) -> str:
    op_type = str(operation["type"])
    if op_type == "set_symbol_value":
        symbol = operation.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise KitError("controller-edit-plan-invalid", "set_symbol_value requires symbol.")
        if "value" not in operation:
            raise KitError("controller-edit-plan-invalid", "set_symbol_value requires value.")
        return _set_symbol_value(source, language=language, symbol=symbol, value=operation["value"])
    if op_type == "replace_function_body":
        function = operation.get("function")
        body = operation.get("body") or operation.get("code")
        if not isinstance(function, str) or not function.strip():
            raise KitError("controller-edit-plan-invalid", "replace_function_body requires function.")
        if not isinstance(body, str) or not body.strip():
            raise KitError("controller-edit-plan-invalid", "replace_function_body requires a non-empty body/code string.")
        return _replace_function_body(source, language=language, function_name=function, body=body)
    if op_type == "add_import_or_include":
        statement = operation.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            raise KitError("controller-edit-plan-invalid", "add_import_or_include requires statement.")
        return _add_import_or_include(source, language=language, statement=statement)
    if op_type == "remove_import_or_include":
        statement = operation.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            raise KitError("controller-edit-plan-invalid", "remove_import_or_include requires statement.")
        return _remove_import_or_include(source, language=language, statement=statement)
    if op_type in {"replace_control_policy", "set_goal_logic", "set_line_follow_logic", "set_obstacle_avoidance_logic"}:
        body = operation.get("body") or operation.get("code")
        if not isinstance(body, str) or not body.strip():
            raise KitError("controller-edit-plan-invalid", f"{op_type} requires a non-empty body/code string.")
        return _replace_region(source, "CONTROL_POLICY", body)
    if op_type == "inject_helper_function":
        code = operation.get("code")
        if not isinstance(code, str) or not code.strip():
            raise KitError("controller-edit-plan-invalid", "inject_helper_function requires a non-empty code string.")
        return _replace_region(source, "HELPERS", code)
    if op_type == "remove_helper_function":
        return _replace_region(source, "HELPERS", "")
    if op_type == "set_device_bindings":
        body = operation.get("body") or operation.get("code")
        if not isinstance(body, str) or not body.strip():
            raise KitError("controller-edit-plan-invalid", "set_device_bindings requires a non-empty body/code string.")
        return _replace_region(source, "DEVICE_INIT", body)
    if op_type == "set_default_camera":
        default_camera = operation.get("default_camera")
        if not isinstance(default_camera, str) or not default_camera.strip():
            raise KitError("controller-edit-plan-invalid", "set_default_camera requires a default_camera string.")
        updated, count = re.subn(r'default_camera\s*=\s*"[^"]*"', f'default_camera="{default_camera}"', source, count=1)
        if count == 0:
            updated, count = re.subn(r'ControllerAgent::from_robot\s*\(([^,]+),\s*"[^"]+"\)', rf'ControllerAgent::from_robot(\1, "{default_camera}")', source, count=1)
        if count == 0:
            raise KitError("controller-edit-unsafe", "Unable to safely update default_camera in controller source.")
        return updated
    if op_type == "update_control_constants":
        assignments = operation.get("assignments") or operation.get("constants")
        if assignments is None:
            assignments = operation.get("constants")
        if not isinstance(assignments, dict) or not assignments:
            raise KitError("controller-edit-plan-invalid", "update_control_constants requires an assignments object.")
        updated = source
        for name, value in assignments.items():
            if not isinstance(name, str) or not name:
                raise KitError("controller-edit-plan-invalid", "Constant names must be non-empty strings.")
            pattern = rf"(?m)^({re.escape(name)}\s*=\s*).+$"
            replacement = rf"\g<1>{_python_literal(value)}"
            newer, count = re.subn(pattern, replacement, updated, count=1)
            if count == 0:
                pattern = rf"(?m)^(const\s+(?:double|int|float|bool)\s+{re.escape(name)}\s*=\s*).+;$"
                replacement = rf"\g<1>{_cpp_literal(value)};"
                newer, count = re.subn(pattern, replacement, updated, count=1)
            if count == 0:
                raise KitError("controller-edit-unsafe", f"Unable to safely update constant '{name}'.")
            updated = newer
        return updated
    if op_type == "update_report_step_keys":
        section = operation.get("section")
        entries = operation.get("entries")
        if not isinstance(section, str) or section not in {"sensors", "metrics", "actuators"}:
            raise KitError("controller-edit-plan-invalid", "update_report_step_keys requires section in sensors|metrics|actuators.")
        if not isinstance(entries, dict):
            raise KitError("controller-edit-plan-invalid", "update_report_step_keys requires an entries object.")
        return _replace_telemetry_section(source, language=language, section=section, entries=entries)
    if op_type == "set_manual_override_behavior":
        body = operation.get("body") or operation.get("code")
        if not isinstance(body, str) or not body.strip():
            raise KitError("controller-edit-plan-invalid", "set_manual_override_behavior requires a non-empty body/code string.")
        return _replace_region(source, "CONTROL_POLICY", body)
    raise KitError("unsupported-controller-edit-operation", f"Unsupported controller edit operation '{op_type}'.")


def _set_symbol_value(source: str, *, language: str, symbol: str, value: Any) -> str:
    if language == "python":
        pattern = rf"(?m)^({re.escape(symbol)}\s*=\s*).+$"
        replacement = rf"\g<1>{_python_literal(value)}"
        updated, count = re.subn(pattern, replacement, source, count=1)
        if count:
            return updated
    else:
        pattern = rf"(?m)^((?:const\s+)?(?:double|int|float|bool|auto)\s+{re.escape(symbol)}\s*=\s*).+;$"
        replacement = rf"\g<1>{_cpp_literal(value)};"
        updated, count = re.subn(pattern, replacement, source, count=1)
        if count:
            return updated
    raise KitError("controller-edit-unsafe", f"Unable to safely update symbol '{symbol}'.")


def _replace_function_body(source: str, *, language: str, function_name: str, body: str) -> str:
    if language == "python":
        return _replace_python_function_body(source, function_name=function_name, body=body)
    return _replace_cpp_function_body(source, function_name=function_name, body=body)


def _add_import_or_include(source: str, *, language: str, statement: str) -> str:
    normalized = statement.strip()
    if normalized in source:
        return source
    if language == "python":
        return _add_python_import(source, normalized)
    return _add_cpp_include(source, normalized)


def _remove_import_or_include(source: str, *, language: str, statement: str) -> str:
    normalized = statement.strip()
    if language == "python":
        updated, count = re.subn(rf"(?m)^{re.escape(normalized)}\n?", "", source, count=1)
    else:
        updated, count = re.subn(rf"(?m)^{re.escape(normalized)}\n?", "", source, count=1)
    if count == 0:
        raise KitError("controller-edit-unsafe", f"Unable to remove import/include '{normalized}'.")
    return updated


def _replace_telemetry_section(source: str, *, language: str, section: str, entries: dict[str, Any]) -> str:
    regions = _find_regions(source)
    if "TELEMETRY_REPORT" not in regions:
        raise KitError("controller-edit-unsafe", "Controller does not expose TELEMETRY_REPORT editable region.")
    start, end = regions["TELEMETRY_REPORT"]
    region_body = source[start:end]
    if language == "python":
        pattern = rf"{section}\s*=\s*\{{.*?\n\s*\}}"
        replacement = f"{section}={_python_dict(entries)}"
        updated, count = re.subn(pattern, replacement, region_body, count=1, flags=re.DOTALL)
    else:
        pattern = rf"std::map<std::string, double>\s+{section}\s*=\s*\{{.*?\n\s*\}};"
        replacement = f"std::map<std::string, double> {section} = {_cpp_map(entries)};"
        updated, count = re.subn(pattern, replacement, region_body, count=1, flags=re.DOTALL)
    if count == 0:
        raise KitError("controller-edit-unsafe", f"Unable to safely update telemetry section '{section}'.")
    return source[:start] + updated + source[end:]


def _replace_python_function_body(source: str, *, function_name: str, body: str) -> str:
    tree = ast.parse(source)
    target = next((node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == function_name), None)
    if target is None or not target.body:
        raise KitError("controller-edit-unsafe", f"Unable to locate Python function '{function_name}'.")
    lines = source.splitlines(keepends=True)
    start_line = target.body[0].lineno - 1
    end_line = target.end_lineno or target.body[-1].end_lineno or start_line + 1
    indent = " " * ((target.body[0].col_offset if target.body else target.col_offset + 4))
    replacement_lines = [f"{indent}{line.rstrip()}\n" if line.strip() else "\n" for line in body.strip().splitlines()]
    return "".join(lines[:start_line] + replacement_lines + lines[end_line:])


def _replace_cpp_function_body(source: str, *, function_name: str, body: str) -> str:
    parser = Parser(CPP_LANGUAGE)
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    for node in _walk_cpp_nodes(tree.root_node):
        if node.type != "function_definition":
            continue
        name = _cpp_function_name(node, source_bytes)
        if name != function_name:
            continue
        compound = next((child for child in node.children if child.type == "compound_statement"), None)
        if compound is None:
            break
        start = compound.start_byte + 1
        end = compound.end_byte - 1
        indented = "\n".join(f"  {line.rstrip()}" if line.strip() else "" for line in body.strip().splitlines())
        replacement = f"\n{indented}\n"
        return source_bytes[:start].decode("utf-8") + replacement + source_bytes[end:].decode("utf-8")
    raise KitError("controller-edit-unsafe", f"Unable to locate C++ function '{function_name}'.")


def _add_python_import(source: str, statement: str) -> str:
    lines = source.splitlines(keepends=True)
    insert_at = 0
    if lines and lines[0].startswith('"""'):
        for index in range(1, len(lines)):
            if lines[index].startswith('"""'):
                insert_at = index + 1
                break
    while insert_at < len(lines) and (lines[insert_at].startswith("from __future__") or lines[insert_at].startswith("import ") or lines[insert_at].startswith("from ")):
        insert_at += 1
    return "".join(lines[:insert_at] + [statement + "\n"] + lines[insert_at:])


def _add_cpp_include(source: str, statement: str) -> str:
    lines = source.splitlines(keepends=True)
    insert_at = 0
    while insert_at < len(lines) and lines[insert_at].startswith("#include"):
        insert_at += 1
    return "".join(lines[:insert_at] + [statement + "\n"] + lines[insert_at:])


def _python_literal(value: Any) -> str:
    return repr(value)


def _cpp_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


def _python_dict(entries: dict[str, Any]) -> str:
    body = ",\n        ".join(f'"{key}": {_python_literal(value)}' for key, value in entries.items())
    return "{\n        " + body + ",\n    }"


def _cpp_map(entries: dict[str, Any]) -> str:
    body = ",\n    ".join(f'{{"{key}", {_cpp_literal(value)}}}' for key, value in entries.items())
    return "{\n    " + body + "\n  }"


def _python_template_for_scenario(scenario: str, *, robot_profile: str = "e-puck") -> str:
    if robot_profile == "monsterborg-4wd":
        templates = {
            "line-follower": _python_monsterborg_line_follower_template,
            "obstacle-avoidance": _python_monsterborg_obstacle_template,
            "waypoint-nav": _python_monsterborg_waypoint_template,
        }
        return templates[scenario]()
    templates = {
        "line-follower": _python_line_follower_template,
        "obstacle-avoidance": _python_obstacle_template,
        "waypoint-nav": _python_waypoint_template,
    }
    return templates[scenario]()


def _cpp_template_for_scenario(scenario: str, *, robot_profile: str = "e-puck") -> str:
    if robot_profile == "monsterborg-4wd":
        templates = {
            "line-follower": _cpp_monsterborg_line_follower_template,
            "obstacle-avoidance": _cpp_monsterborg_obstacle_template,
            "waypoint-nav": _cpp_monsterborg_waypoint_template,
        }
        return templates[scenario]()
    templates = {
        "line-follower": _cpp_line_follower_template,
        "obstacle-avoidance": _cpp_obstacle_template,
        "waypoint-nav": _cpp_waypoint_template,
    }
    return templates[scenario]()


def _python_line_follower_template() -> str:
    return '''from __future__ import annotations

from controller import Camera, Robot

from webots_mcp_kit.agent import ControllerAgent


TIME_STEP = 32
SPEED_UNIT = 0.00628
CRUISE = 200
TURN_GAIN = 4


# webots-kit region HELPERS start
def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def find_middle(values: list[int]) -> int:
    size = len(values)
    mean = sum(values) / max(size, 1)
    strong = [(index, value) for index, value in enumerate(values) if value > mean]
    if not strong:
        return size // 2
    strong.sort(key=lambda item: item[1], reverse=True)
    sample = strong[: max(size // 10, 1)]
    rough_center = sum(index for index, _ in sample) / len(sample)
    filtered = [index for index, _ in sample if abs(index - rough_center) <= size / 10]
    if not filtered:
        return size // 2
    return int(sum(filtered) / len(filtered))
# webots-kit region HELPERS end


robot = Robot()

# webots-kit region DEVICE_INIT start
left_motor = robot.getDevice("left wheel motor")
right_motor = robot.getDevice("right wheel motor")
left_motor.setPosition(float("inf"))
right_motor.setPosition(float("inf"))
left_motor.setVelocity(0.0)
right_motor.setVelocity(0.0)

camera = robot.getDevice("camera")
camera.enable(TIME_STEP)
width = camera.getWidth()
height = camera.getHeight()
# webots-kit region DEVICE_INIT end

agent = ControllerAgent.from_robot(robot, default_camera="camera")

while robot.step(TIME_STEP) != -1:
    image = camera.getImage()
    blue = [255 - Camera.imageGetBlue(image, width, x, 0) for x in range(width)]
    middle = find_middle(blue)
    delta = middle - width / 2.0
    line_visible = any(value > 15 for value in blue)
    camera_left = sum(blue[: width // 3]) / max(width // 3, 1)
    camera_center = sum(blue[width // 3 : 2 * width // 3]) / max(width // 3, 1)
    camera_right = sum(blue[2 * width // 3 :]) / max(width - 2 * (width // 3), 1)

    # webots-kit region CONTROL_POLICY start
    left_speed = SPEED_UNIT * (CRUISE - TURN_GAIN * abs(delta) + TURN_GAIN * delta)
    right_speed = SPEED_UNIT * (CRUISE - TURN_GAIN * abs(delta) - TURN_GAIN * delta)
    # webots-kit region CONTROL_POLICY end

    override = agent.begin_step()
    if override is not None:
        left_speed, right_speed = override

    left_speed = clamp(left_speed, -6.28, 6.28)
    right_speed = clamp(right_speed, -6.28, 6.28)
    left_motor.setVelocity(left_speed)
    right_motor.setVelocity(right_speed)

    # webots-kit region TELEMETRY_REPORT start
    sensors={
        "camera_left_band": round(camera_left, 3),
        "camera_center_band": round(camera_center, 3),
        "camera_right_band": round(camera_right, 3),
    }
    metrics={
        "line_visible": 1.0 if line_visible else 0.0,
        "center_error": round(delta / max(width / 2.0, 1.0), 6),
        "ir_balance_error": round((camera_left - camera_right) / 255.0, 6),
    }
    actuators={
        "left_velocity": round(left_speed, 6),
        "right_velocity": round(right_speed, 6),
    }
    camera_frames={"camera": {"image": image, "width": width, "height": height}}
    # webots-kit region TELEMETRY_REPORT end

    agent.report_step(
        sensors=sensors,
        metrics=metrics,
        actuators=actuators,
        camera_frames=camera_frames,
    )
'''


def _python_obstacle_template() -> str:
    return '''from __future__ import annotations

from controller import Robot

from webots_mcp_kit.agent import ControllerAgent


MAX_SPEED = 6.28
LEFT = 0
RIGHT = 1
DISTANCE_SENSORS = ("ps0", "ps1", "ps2", "ps3", "ps4", "ps5", "ps6", "ps7")
WEIGHTS = (
    (-1.3, -1.0),
    (-1.3, -1.0),
    (-0.5, 0.5),
    (0.0, 0.0),
    (0.0, 0.0),
    (0.05, -0.5),
    (-0.75, 0.0),
    (-0.75, 0.0),
)
OFFSETS = (0.5 * MAX_SPEED, 0.5 * MAX_SPEED)


# webots-kit region HELPERS start
def clamp(value: float) -> float:
    return max(-MAX_SPEED, min(MAX_SPEED, value))
# webots-kit region HELPERS end


robot = Robot()
time_step = int(robot.getBasicTimeStep())

# webots-kit region DEVICE_INIT start
distance_sensors = []
for name in DISTANCE_SENSORS:
    sensor = robot.getDevice(name)
    sensor.enable(time_step)
    distance_sensors.append(sensor)

camera = robot.getDevice("camera")
if camera is not None:
    camera.enable(time_step)

left_motor = robot.getDevice("left wheel motor")
right_motor = robot.getDevice("right wheel motor")
left_motor.setPosition(float("inf"))
right_motor.setPosition(float("inf"))
left_motor.setVelocity(0.0)
right_motor.setVelocity(0.0)
# webots-kit region DEVICE_INIT end

agent = ControllerAgent.from_robot(robot, default_camera="camera")

while robot.step(time_step) != -1:
    sensor_values = [sensor.getValue() / 4096.0 for sensor in distance_sensors]

    # webots-kit region CONTROL_POLICY start
    speeds = [0.0, 0.0]
    for side in (LEFT, RIGHT):
        weighted = 0.0
        for index, value in enumerate(sensor_values):
            weighted += value * WEIGHTS[index][side]
        speeds[side] = clamp(OFFSETS[side] + weighted * MAX_SPEED)
    # webots-kit region CONTROL_POLICY end

    override = agent.begin_step()
    if override is not None:
        speeds[LEFT], speeds[RIGHT] = override

    left_motor.setVelocity(speeds[LEFT])
    right_motor.setVelocity(speeds[RIGHT])

    image = camera.getImage() if camera is not None else None
    obstacle_pressure = max(sensor_values)

    # webots-kit region TELEMETRY_REPORT start
    sensors={name: round(value, 6) for name, value in zip(DISTANCE_SENSORS, sensor_values)}
    metrics={
        "line_visible": 0.0,
        "center_error": 0.0,
        "ir_balance_error": round(sensor_values[0] - sensor_values[7], 6),
        "obstacle_pressure": round(obstacle_pressure, 6),
        "mean_forward_speed": round((speeds[LEFT] + speeds[RIGHT]) / 2.0, 6),
    }
    actuators={
        "left_velocity": round(speeds[LEFT], 6),
        "right_velocity": round(speeds[RIGHT], 6),
    }
    camera_frames={"camera": {"image": image, "width": camera.getWidth(), "height": camera.getHeight()}} if image else None
    # webots-kit region TELEMETRY_REPORT end

    agent.report_step(
        sensors=sensors,
        metrics=metrics,
        actuators=actuators,
        camera_frames=camera_frames,
    )
'''


def _python_waypoint_template() -> str:
    return '''from __future__ import annotations

from controller import Robot

from webots_mcp_kit.agent import ControllerAgent


MAX_SPEED = 6.28
CRUISE_SPEED = 4.2
DISTANCE_SENSORS = ("ps0", "ps1", "ps2", "ps3", "ps4", "ps5", "ps6", "ps7")


# webots-kit region HELPERS start
def clamp(value: float) -> float:
    return max(-MAX_SPEED, min(MAX_SPEED, value))
# webots-kit region HELPERS end


robot = Robot()
time_step = int(robot.getBasicTimeStep())

# webots-kit region DEVICE_INIT start
distance_sensors = []
for name in DISTANCE_SENSORS:
    sensor = robot.getDevice(name)
    sensor.enable(time_step)
    distance_sensors.append(sensor)

camera = robot.getDevice("camera")
if camera is not None:
    camera.enable(time_step)

left_motor = robot.getDevice("left wheel motor")
right_motor = robot.getDevice("right wheel motor")
left_motor.setPosition(float("inf"))
right_motor.setPosition(float("inf"))
left_motor.setVelocity(0.0)
right_motor.setVelocity(0.0)
# webots-kit region DEVICE_INIT end

agent = ControllerAgent.from_robot(robot, default_camera="camera")

while robot.step(time_step) != -1:
    sensor_values = [sensor.getValue() / 4096.0 for sensor in distance_sensors]

    # webots-kit region CONTROL_POLICY start
    front_pressure = max(sensor_values[0], sensor_values[7], sensor_values[1], sensor_values[6])
    left_speed = clamp(CRUISE_SPEED - front_pressure * 2.0)
    right_speed = clamp(CRUISE_SPEED - front_pressure * 2.0)
    # webots-kit region CONTROL_POLICY end

    override = agent.begin_step()
    if override is not None:
        left_speed, right_speed = override

    left_motor.setVelocity(left_speed)
    right_motor.setVelocity(right_speed)

    image = camera.getImage() if camera is not None else None

    # webots-kit region TELEMETRY_REPORT start
    sensors={name: round(value, 6) for name, value in zip(DISTANCE_SENSORS, sensor_values)}
    metrics={
        "line_visible": 0.0,
        "center_error": 0.0,
        "ir_balance_error": round(sensor_values[0] - sensor_values[7], 6),
        "obstacle_pressure": round(front_pressure, 6),
        "mean_forward_speed": round((left_speed + right_speed) / 2.0, 6),
    }
    actuators={
        "left_velocity": round(left_speed, 6),
        "right_velocity": round(right_speed, 6),
    }
    camera_frames={"camera": {"image": image, "width": camera.getWidth(), "height": camera.getHeight()}} if image else None
    # webots-kit region TELEMETRY_REPORT end

    agent.report_step(
        sensors=sensors,
        metrics=metrics,
        actuators=actuators,
        camera_frames=camera_frames,
    )
'''


def _python_monsterborg_line_follower_template() -> str:
    return '''from __future__ import annotations

from controller import Camera, Robot

from webots_mcp_kit.agent import ControllerAgent
from webots_mcp_kit.monsterborg_line_follow import (
    LineFollowMemory,
    analyze_scan_rows,
    camera_rows_from_image,
    clamp_velocity_pair,
    compute_drive_targets,
    update_memory,
)


TIME_STEP = 32
MAX_SPEED = 8.0
CRUISE = 4.2
MIN_CRUISE = 1.8
TURN_GAIN = 3.2
CURVATURE_GAIN = 1.1
SEARCH_SPEED = 2.0
RECOVER_SPEED = 2.6


# webots-kit region HELPERS start
def set_drive_velocity(left_velocity: float, right_velocity: float) -> None:
    front_left_motor.setVelocity(left_velocity)
    rear_left_motor.setVelocity(left_velocity)
    front_right_motor.setVelocity(right_velocity)
    rear_right_motor.setVelocity(right_velocity)
# webots-kit region HELPERS end


robot = Robot()

# webots-kit region DEVICE_INIT start
front_left_motor = robot.getDevice("front_left_motor")
rear_left_motor = robot.getDevice("rear_left_motor")
front_right_motor = robot.getDevice("front_right_motor")
rear_right_motor = robot.getDevice("rear_right_motor")
for motor in (front_left_motor, rear_left_motor, front_right_motor, rear_right_motor):
    motor.setPosition(float("inf"))
    motor.setVelocity(0.0)

left_encoder = robot.getDevice("left_encoder")
right_encoder = robot.getDevice("right_encoder")
left_encoder.enable(TIME_STEP)
right_encoder.enable(TIME_STEP)

front_camera = robot.getDevice("front_camera")
front_camera.enable(TIME_STEP)
camera_width = front_camera.getWidth()
camera_height = front_camera.getHeight()

front_range = robot.getDevice("front_range")
front_range.enable(TIME_STEP)

imu = robot.getDevice("imu")
imu.enable(TIME_STEP)
# webots-kit region DEVICE_INIT end

agent = ControllerAgent.from_robot(robot, default_camera="front_camera")
memory = LineFollowMemory()
previous_heading = 0.0

while robot.step(TIME_STEP) != -1:
    image = front_camera.getImage()
    rows = camera_rows_from_image(
        image,
        width=camera_width,
        height=camera_height,
        blue_reader=Camera.imageGetBlue,
    )
    profile = analyze_scan_rows(rows)
    updated_memory = update_memory(memory, profile)

    heading = float(imu.getRollPitchYaw()[2])
    yaw_rate = (heading - previous_heading) / max(TIME_STEP / 1000.0, 1e-6)
    previous_heading = heading
    front_range_value = float(front_range.getValue())
    left_ticks = float(left_encoder.getValue())
    right_ticks = float(right_encoder.getValue())

    # webots-kit region CONTROL_POLICY start
    left_speed, right_speed = compute_drive_targets(
        updated_memory,
        profile,
        max_speed=MAX_SPEED,
        cruise_speed=CRUISE,
        minimum_cruise=MIN_CRUISE,
        turn_gain=TURN_GAIN,
        curvature_gain=CURVATURE_GAIN,
        search_speed=SEARCH_SPEED,
        recover_speed=RECOVER_SPEED,
    )
    # webots-kit region CONTROL_POLICY end

    override = agent.begin_step()
    if override is not None:
        left_speed, right_speed = override

    left_speed, right_speed = clamp_velocity_pair(left_speed, right_speed, max_speed=MAX_SPEED)
    set_drive_velocity(left_speed, right_speed)
    saturation = 1.0 if max(abs(left_speed), abs(right_speed)) >= MAX_SPEED * 0.98 else 0.0

    # webots-kit region TELEMETRY_REPORT start
    sensors={
        "camera_left_band": round(profile.left_band, 3),
        "camera_center_band": round(profile.center_band, 3),
        "camera_right_band": round(profile.right_band, 3),
        "front_range": round(front_range_value, 6),
        "heading": round(heading, 6),
        "yaw_rate": round(yaw_rate, 6),
        "left_encoder": round(left_ticks, 6),
        "right_encoder": round(right_ticks, 6),
    }
    metrics={
        "line_visible": 1.0 if profile.line_visible else 0.0,
        "line_confidence": round(profile.confidence, 6),
        "camera_signal_strength": round(profile.signal_strength_mean, 6),
        "center_error": round(profile.center_error, 6),
        "ir_balance_error": round((profile.left_band - profile.right_band) / 255.0, 6),
        "mean_forward_speed": round((left_speed + right_speed) / 2.0, 6),
        "tracking_state_code": float(updated_memory.state_code),
        "speed_saturation": saturation,
    }
    actuators={
        "left_velocity": round(left_speed, 6),
        "right_velocity": round(right_speed, 6),
    }
    camera_frames={"front_camera": {"image": image, "width": camera_width, "height": camera_height}}
    # webots-kit region TELEMETRY_REPORT end

    agent.report_step(
        sensors=sensors,
        metrics=metrics,
        actuators=actuators,
        camera_frames=camera_frames,
    )

    memory = LineFollowMemory(
        state_code=updated_memory.state_code,
        lost_steps=updated_memory.lost_steps,
        last_center_error=profile.center_error,
        search_direction=updated_memory.search_direction,
    )
'''


def _python_monsterborg_obstacle_template() -> str:
    return '''from __future__ import annotations

from controller import Robot

from webots_mcp_kit.agent import ControllerAgent
from webots_mcp_kit.monsterborg_navigation import ObstacleMemory, obstacle_control_step


# webots-kit region HELPERS start
def set_drive_velocity(left_velocity: float, right_velocity: float) -> None:
    front_left_motor.setVelocity(left_velocity)
    rear_left_motor.setVelocity(left_velocity)
    front_right_motor.setVelocity(right_velocity)
    rear_right_motor.setVelocity(right_velocity)
# webots-kit region HELPERS end


robot = Robot()
time_step = int(robot.getBasicTimeStep())

# webots-kit region DEVICE_INIT start
front_left_motor = robot.getDevice("front_left_motor")
rear_left_motor = robot.getDevice("rear_left_motor")
front_right_motor = robot.getDevice("front_right_motor")
rear_right_motor = robot.getDevice("rear_right_motor")
for motor in (front_left_motor, rear_left_motor, front_right_motor, rear_right_motor):
    motor.setPosition(float("inf"))
    motor.setVelocity(0.0)

left_encoder = robot.getDevice("left_encoder")
right_encoder = robot.getDevice("right_encoder")
left_encoder.enable(time_step)
right_encoder.enable(time_step)

front_camera = robot.getDevice("front_camera")
front_camera.enable(time_step)

front_range = robot.getDevice("front_range")
front_range.enable(time_step)

imu = robot.getDevice("imu")
imu.enable(time_step)
# webots-kit region DEVICE_INIT end

agent = ControllerAgent.from_robot(robot, default_camera="front_camera")
memory = ObstacleMemory()
previous_heading = 0.0

while robot.step(time_step) != -1:
    front_range_value = float(front_range.getValue())
    heading = float(imu.getRollPitchYaw()[2])
    yaw_rate = (heading - previous_heading) / max(time_step / 1000.0, 1e-6)
    previous_heading = heading
    left_ticks = float(left_encoder.getValue())
    right_ticks = float(right_encoder.getValue())

    # webots-kit region CONTROL_POLICY start
    memory, policy_metrics, (left_speed, right_speed) = obstacle_control_step(
        memory,
        front_range=front_range_value,
        heading=heading,
        yaw_rate=yaw_rate,
        left_encoder=left_ticks,
        right_encoder=right_ticks,
    )
    # webots-kit region CONTROL_POLICY end

    override = agent.begin_step()
    if override is not None:
        left_speed, right_speed = override

    set_drive_velocity(left_speed, right_speed)
    image = front_camera.getImage()

    # webots-kit region TELEMETRY_REPORT start
    sensors={
        "front_range": round(front_range_value, 6),
        "heading": round(heading, 6),
        "yaw_rate": round(yaw_rate, 6),
        "left_encoder": round(left_ticks, 6),
        "right_encoder": round(right_ticks, 6),
    }
    metrics={
        "obstacle_pressure": policy_metrics["obstacle_pressure"],
        "mean_forward_speed": round((left_speed + right_speed) / 2.0, 6),
        "front_clearance_margin": policy_metrics["front_clearance_margin"],
        "clearance_violation": policy_metrics["clearance_violation"],
        "heading_recovery_events": policy_metrics["heading_recovery_events"],
        "stalled_steps": policy_metrics["stalled_steps"],
        "avoidance_state_code": policy_metrics["avoidance_state_code"],
        "speed_saturation": policy_metrics["speed_saturation"],
        "line_visible": 0.0,
        "center_error": 0.0,
        "ir_balance_error": round((left_ticks - right_ticks) * 0.01, 6),
    }
    actuators={
        "left_velocity": round(left_speed, 6),
        "right_velocity": round(right_speed, 6),
    }
    camera_frames={"front_camera": {"image": image, "width": front_camera.getWidth(), "height": front_camera.getHeight()}}
    # webots-kit region TELEMETRY_REPORT end

    agent.report_step(
        sensors=sensors,
        metrics=metrics,
        actuators=actuators,
        camera_frames=camera_frames,
    )
'''


def _python_monsterborg_waypoint_template() -> str:
    return '''from __future__ import annotations

from controller import Robot

from webots_mcp_kit.agent import ControllerAgent
from webots_mcp_kit.monsterborg_navigation import WaypointMemory, waypoint_control_step


# webots-kit region HELPERS start
def set_drive_velocity(left_velocity: float, right_velocity: float) -> None:
    front_left_motor.setVelocity(left_velocity)
    rear_left_motor.setVelocity(left_velocity)
    front_right_motor.setVelocity(right_velocity)
    rear_right_motor.setVelocity(right_velocity)
# webots-kit region HELPERS end


robot = Robot()
time_step = int(robot.getBasicTimeStep())

# webots-kit region DEVICE_INIT start
front_left_motor = robot.getDevice("front_left_motor")
rear_left_motor = robot.getDevice("rear_left_motor")
front_right_motor = robot.getDevice("front_right_motor")
rear_right_motor = robot.getDevice("rear_right_motor")
for motor in (front_left_motor, rear_left_motor, front_right_motor, rear_right_motor):
    motor.setPosition(float("inf"))
    motor.setVelocity(0.0)

left_encoder = robot.getDevice("left_encoder")
right_encoder = robot.getDevice("right_encoder")
left_encoder.enable(time_step)
right_encoder.enable(time_step)

front_camera = robot.getDevice("front_camera")
front_camera.enable(time_step)

front_range = robot.getDevice("front_range")
front_range.enable(time_step)

imu = robot.getDevice("imu")
imu.enable(time_step)
# webots-kit region DEVICE_INIT end

agent = ControllerAgent.from_robot(robot, default_camera="front_camera")
memory = WaypointMemory()
previous_heading = 0.0

while robot.step(time_step) != -1:
    front_range_value = float(front_range.getValue())
    heading = float(imu.getRollPitchYaw()[2])
    yaw_rate = (heading - previous_heading) / max(time_step / 1000.0, 1e-6)
    previous_heading = heading
    left_ticks = float(left_encoder.getValue())
    right_ticks = float(right_encoder.getValue())

    # webots-kit region CONTROL_POLICY start
    memory, policy_metrics, (left_speed, right_speed) = waypoint_control_step(
        memory,
        front_range=front_range_value,
        heading=heading,
        yaw_rate=yaw_rate,
        left_encoder=left_ticks,
        right_encoder=right_ticks,
    )
    # webots-kit region CONTROL_POLICY end

    override = agent.begin_step()
    if override is not None:
        left_speed, right_speed = override

    set_drive_velocity(left_speed, right_speed)
    image = front_camera.getImage()

    # webots-kit region TELEMETRY_REPORT start
    sensors={
        "front_range": round(front_range_value, 6),
        "heading": round(heading, 6),
        "yaw_rate": round(yaw_rate, 6),
        "left_encoder": round(left_ticks, 6),
        "right_encoder": round(right_ticks, 6),
    }
    metrics={
        "obstacle_pressure": policy_metrics["obstacle_pressure"],
        "mean_forward_speed": round((left_speed + right_speed) / 2.0, 6),
        "progress_ratio": policy_metrics["progress_ratio"],
        "distance_to_goal_estimate": policy_metrics["distance_to_goal_estimate"],
        "heading_alignment_error": policy_metrics["heading_alignment_error"],
        "path_deviation_score": policy_metrics["path_deviation_score"],
        "waypoint_recovery_events": policy_metrics["waypoint_recovery_events"],
        "stalled_steps": policy_metrics["stalled_steps"],
        "waypoint_state_code": policy_metrics["waypoint_state_code"],
        "speed_saturation": policy_metrics["speed_saturation"],
        "line_visible": 0.0,
        "center_error": 0.0,
        "ir_balance_error": round((left_ticks - right_ticks) * 0.01, 6),
    }
    actuators={
        "left_velocity": round(left_speed, 6),
        "right_velocity": round(right_speed, 6),
    }
    camera_frames={"front_camera": {"image": image, "width": front_camera.getWidth(), "height": front_camera.getHeight()}}
    # webots-kit region TELEMETRY_REPORT end

    agent.report_step(
        sensors=sensors,
        metrics=metrics,
        actuators=actuators,
        camera_frames=camera_frames,
    )
'''


def _cpp_line_follower_template() -> str:
    return r'''#include "controller_agent.hpp"

#include <webots/Camera.hpp>
#include <webots/Motor.hpp>
#include <webots/Robot.hpp>

#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <string>
#include <vector>

using webots::Camera;
using webots::Robot;
using webots_mcp_kit::CameraFrame;
using webots_mcp_kit::ControllerAgent;

const int TIME_STEP = 32;
const double SPEED_UNIT = 0.00628;
const double CRUISE = 200.0;
const double TURN_GAIN = 4.0;

// webots-kit region HELPERS start
static double clamp_value(double value, double minimum, double maximum) {
  return std::max(minimum, std::min(maximum, value));
}

static int find_middle(const std::vector<int>& values) {
  const int size = static_cast<int>(values.size());
  if (size <= 0)
    return 0;
  double mean = 0.0;
  for (int value : values)
    mean += value;
  mean /= size;
  std::vector<std::pair<int, int>> strong;
  for (int index = 0; index < size; ++index) {
    if (values[index] > mean)
      strong.emplace_back(index, values[index]);
  }
  if (strong.empty())
    return size / 2;
  std::sort(strong.begin(), strong.end(), [](const auto& left, const auto& right) { return left.second > right.second; });
  const int sample_size = std::max(size / 10, 1);
  strong.resize(std::min(sample_size, static_cast<int>(strong.size())));
  double rough_center = 0.0;
  for (const auto& entry : strong)
    rough_center += entry.first;
  rough_center /= strong.size();
  std::vector<int> filtered;
  for (const auto& entry : strong) {
    if (std::fabs(entry.first - rough_center) <= size / 10.0)
      filtered.push_back(entry.first);
  }
  if (filtered.empty())
    return size / 2;
  double middle = 0.0;
  for (int index : filtered)
    middle += index;
  middle /= filtered.size();
  return static_cast<int>(middle);
}
// webots-kit region HELPERS end

int main() {
  Robot robot;

  // webots-kit region DEVICE_INIT start
  auto* left_motor = robot.getMotor("left wheel motor");
  auto* right_motor = robot.getMotor("right wheel motor");
  left_motor->setPosition(std::numeric_limits<double>::infinity());
  right_motor->setPosition(std::numeric_limits<double>::infinity());
  left_motor->setVelocity(0.0);
  right_motor->setVelocity(0.0);

  auto* camera = robot.getCamera("camera");
  camera->enable(TIME_STEP);
  const int width = camera->getWidth();
  const int height = camera->getHeight();
  // webots-kit region DEVICE_INIT end

  auto agent = ControllerAgent::from_robot(&robot, "camera");

  while (robot.step(TIME_STEP) != -1) {
    const unsigned char* image = camera->getImage();
    std::vector<int> blue(width, 0);
    for (int x = 0; x < width; ++x)
      blue[x] = 255 - Camera::imageGetBlue(image, width, x, 0);
    const int middle = find_middle(blue);
    const double delta = middle - width / 2.0;
    bool line_visible = false;
    for (int value : blue) {
      if (value > 15) {
        line_visible = true;
        break;
      }
    }
    double camera_left = 0.0;
    double camera_center = 0.0;
    double camera_right = 0.0;
    const int third = std::max(width / 3, 1);
    for (int x = 0; x < width; ++x) {
      if (x < third)
        camera_left += blue[x];
      else if (x < 2 * third)
        camera_center += blue[x];
      else
        camera_right += blue[x];
    }
    camera_left /= third;
    camera_center /= third;
    camera_right /= std::max(width - 2 * third, 1);

    // webots-kit region CONTROL_POLICY start
    double left_speed = SPEED_UNIT * (CRUISE - TURN_GAIN * std::fabs(delta) + TURN_GAIN * delta);
    double right_speed = SPEED_UNIT * (CRUISE - TURN_GAIN * std::fabs(delta) - TURN_GAIN * delta);
    // webots-kit region CONTROL_POLICY end

    auto override = agent.begin_step();
    if (override.has_value()) {
      left_speed = override->first;
      right_speed = override->second;
    }

    left_speed = clamp_value(left_speed, -6.28, 6.28);
    right_speed = clamp_value(right_speed, -6.28, 6.28);
    left_motor->setVelocity(left_speed);
    right_motor->setVelocity(right_speed);

    // webots-kit region TELEMETRY_REPORT start
    std::map<std::string, double> sensors = {
      {"camera_left_band", camera_left},
      {"camera_center_band", camera_center},
      {"camera_right_band", camera_right}
    };
    std::map<std::string, double> metrics = {
      {"line_visible", line_visible ? 1.0 : 0.0},
      {"center_error", delta / std::max(width / 2.0, 1.0)},
      {"ir_balance_error", (camera_left - camera_right) / 255.0}
    };
    std::map<std::string, double> actuators = {
      {"left_velocity", left_speed},
      {"right_velocity", right_speed}
    };
    std::vector<CameraFrame> camera_frames = {
      CameraFrame{"camera", image, width, height}
    };
    // webots-kit region TELEMETRY_REPORT end

    agent.report_step(sensors, metrics, actuators, camera_frames);
  }
  return 0;
}
'''


def _cpp_obstacle_template() -> str:
    return r'''#include "controller_agent.hpp"

#include <webots/Camera.hpp>
#include <webots/DistanceSensor.hpp>
#include <webots/Motor.hpp>
#include <webots/Robot.hpp>

#include <algorithm>
#include <limits>
#include <map>
#include <string>
#include <vector>

using webots::Robot;
using webots_mcp_kit::CameraFrame;
using webots_mcp_kit::ControllerAgent;

const double MAX_SPEED = 6.28;
const int LEFT = 0;
const int RIGHT = 1;
const char* DISTANCE_SENSORS[] = {"ps0", "ps1", "ps2", "ps3", "ps4", "ps5", "ps6", "ps7"};
const double WEIGHTS[8][2] = {
  {-1.3, -1.0},
  {-1.3, -1.0},
  {-0.5, 0.5},
  {0.0, 0.0},
  {0.0, 0.0},
  {0.05, -0.5},
  {-0.75, 0.0},
  {-0.75, 0.0},
};
const double OFFSETS[2] = {0.5 * MAX_SPEED, 0.5 * MAX_SPEED};

// webots-kit region HELPERS start
static double clamp_value(double value) {
  return std::max(-MAX_SPEED, std::min(MAX_SPEED, value));
}
// webots-kit region HELPERS end

int main() {
  Robot robot;
  const int time_step = static_cast<int>(robot.getBasicTimeStep());

  // webots-kit region DEVICE_INIT start
  std::vector<webots::DistanceSensor*> distance_sensors;
  for (const char* name : DISTANCE_SENSORS) {
    auto* sensor = robot.getDistanceSensor(name);
    sensor->enable(time_step);
    distance_sensors.push_back(sensor);
  }

  auto* camera = robot.getCamera("camera");
  if (camera != nullptr)
    camera->enable(time_step);

  auto* left_motor = robot.getMotor("left wheel motor");
  auto* right_motor = robot.getMotor("right wheel motor");
  left_motor->setPosition(std::numeric_limits<double>::infinity());
  right_motor->setPosition(std::numeric_limits<double>::infinity());
  left_motor->setVelocity(0.0);
  right_motor->setVelocity(0.0);
  // webots-kit region DEVICE_INIT end

  auto agent = ControllerAgent::from_robot(&robot, "camera");

  while (robot.step(time_step) != -1) {
    std::vector<double> sensor_values;
    sensor_values.reserve(distance_sensors.size());
    for (auto* sensor : distance_sensors)
      sensor_values.push_back(sensor->getValue() / 4096.0);

    // webots-kit region CONTROL_POLICY start
    double speeds[2] = {0.0, 0.0};
    for (int side = 0; side < 2; ++side) {
      double weighted = 0.0;
      for (size_t index = 0; index < sensor_values.size(); ++index)
        weighted += sensor_values[index] * WEIGHTS[index][side];
      speeds[side] = clamp_value(OFFSETS[side] + weighted * MAX_SPEED);
    }
    // webots-kit region CONTROL_POLICY end

    auto override = agent.begin_step();
    if (override.has_value()) {
      speeds[LEFT] = override->first;
      speeds[RIGHT] = override->second;
    }

    left_motor->setVelocity(speeds[LEFT]);
    right_motor->setVelocity(speeds[RIGHT]);

    const unsigned char* image = camera != nullptr ? camera->getImage() : nullptr;
    double obstacle_pressure = 0.0;
    for (double value : sensor_values)
      obstacle_pressure = std::max(obstacle_pressure, value);

    // webots-kit region TELEMETRY_REPORT start
    std::map<std::string, double> sensors = {
      {"ps0", sensor_values[0]},
      {"ps1", sensor_values[1]},
      {"ps2", sensor_values[2]},
      {"ps3", sensor_values[3]},
      {"ps4", sensor_values[4]},
      {"ps5", sensor_values[5]},
      {"ps6", sensor_values[6]},
      {"ps7", sensor_values[7]}
    };
    std::map<std::string, double> metrics = {
      {"line_visible", 0.0},
      {"center_error", 0.0},
      {"ir_balance_error", sensor_values[0] - sensor_values[7]},
      {"obstacle_pressure", obstacle_pressure},
      {"mean_forward_speed", (speeds[LEFT] + speeds[RIGHT]) / 2.0}
    };
    std::map<std::string, double> actuators = {
      {"left_velocity", speeds[LEFT]},
      {"right_velocity", speeds[RIGHT]}
    };
    std::vector<CameraFrame> camera_frames;
    if (image != nullptr)
      camera_frames.push_back(CameraFrame{"camera", image, camera->getWidth(), camera->getHeight()});
    // webots-kit region TELEMETRY_REPORT end

    agent.report_step(sensors, metrics, actuators, camera_frames);
  }
  return 0;
}
'''


def _cpp_waypoint_template() -> str:
    return r'''#include "controller_agent.hpp"

#include <webots/Camera.hpp>
#include <webots/DistanceSensor.hpp>
#include <webots/Motor.hpp>
#include <webots/Robot.hpp>

#include <algorithm>
#include <limits>
#include <map>
#include <string>
#include <vector>

using webots::Robot;
using webots_mcp_kit::CameraFrame;
using webots_mcp_kit::ControllerAgent;

const double MAX_SPEED = 6.28;
const double CRUISE_SPEED = 4.2;
const char* DISTANCE_SENSORS[] = {"ps0", "ps1", "ps2", "ps3", "ps4", "ps5", "ps6", "ps7"};

// webots-kit region HELPERS start
static double clamp_value(double value) {
  return std::max(-MAX_SPEED, std::min(MAX_SPEED, value));
}
// webots-kit region HELPERS end

int main() {
  Robot robot;
  const int time_step = static_cast<int>(robot.getBasicTimeStep());

  // webots-kit region DEVICE_INIT start
  std::vector<webots::DistanceSensor*> distance_sensors;
  for (const char* name : DISTANCE_SENSORS) {
    auto* sensor = robot.getDistanceSensor(name);
    sensor->enable(time_step);
    distance_sensors.push_back(sensor);
  }

  auto* camera = robot.getCamera("camera");
  if (camera != nullptr)
    camera->enable(time_step);

  auto* left_motor = robot.getMotor("left wheel motor");
  auto* right_motor = robot.getMotor("right wheel motor");
  left_motor->setPosition(std::numeric_limits<double>::infinity());
  right_motor->setPosition(std::numeric_limits<double>::infinity());
  left_motor->setVelocity(0.0);
  right_motor->setVelocity(0.0);
  // webots-kit region DEVICE_INIT end

  auto agent = ControllerAgent::from_robot(&robot, "camera");

  while (robot.step(time_step) != -1) {
    std::vector<double> sensor_values;
    sensor_values.reserve(distance_sensors.size());
    for (auto* sensor : distance_sensors)
      sensor_values.push_back(sensor->getValue() / 4096.0);

    // webots-kit region CONTROL_POLICY start
    double front_pressure = std::max(std::max(sensor_values[0], sensor_values[7]), std::max(sensor_values[1], sensor_values[6]));
    double left_speed = clamp_value(CRUISE_SPEED - front_pressure * 2.0);
    double right_speed = clamp_value(CRUISE_SPEED - front_pressure * 2.0);
    // webots-kit region CONTROL_POLICY end

    auto override = agent.begin_step();
    if (override.has_value()) {
      left_speed = override->first;
      right_speed = override->second;
    }

    left_motor->setVelocity(left_speed);
    right_motor->setVelocity(right_speed);

    const unsigned char* image = camera != nullptr ? camera->getImage() : nullptr;

    // webots-kit region TELEMETRY_REPORT start
    std::map<std::string, double> sensors = {
      {"ps0", sensor_values[0]},
      {"ps1", sensor_values[1]},
      {"ps2", sensor_values[2]},
      {"ps3", sensor_values[3]},
      {"ps4", sensor_values[4]},
      {"ps5", sensor_values[5]},
      {"ps6", sensor_values[6]},
      {"ps7", sensor_values[7]}
    };
    std::map<std::string, double> metrics = {
      {"line_visible", 0.0},
      {"center_error", 0.0},
      {"ir_balance_error", sensor_values[0] - sensor_values[7]},
      {"obstacle_pressure", front_pressure},
      {"mean_forward_speed", (left_speed + right_speed) / 2.0}
    };
    std::map<std::string, double> actuators = {
      {"left_velocity", left_speed},
      {"right_velocity", right_speed}
    };
    std::vector<CameraFrame> camera_frames;
    if (image != nullptr)
      camera_frames.push_back(CameraFrame{"camera", image, camera->getWidth(), camera->getHeight()});
    // webots-kit region TELEMETRY_REPORT end

    agent.report_step(sensors, metrics, actuators, camera_frames);
  }
  return 0;
}
'''


def _cpp_monsterborg_line_follower_template() -> str:
    return r'''#include "controller_agent.hpp"

#include <webots/Camera.hpp>
#include <webots/DistanceSensor.hpp>
#include <webots/InertialUnit.hpp>
#include <webots/Motor.hpp>
#include <webots/PositionSensor.hpp>
#include <webots/Robot.hpp>

#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <string>
#include <tuple>
#include <vector>

using webots::Camera;
using webots::Robot;
using webots_mcp_kit::CameraFrame;
using webots_mcp_kit::ControllerAgent;

const int TIME_STEP = 32;
const double MAX_SPEED = 8.0;
const double CRUISE = 4.8;
const double TURN_GAIN = 3.8;
const double SEARCH_GAIN = 3.1;
const double RECOVER_GAIN = 4.2;

enum TrackingState {
  TRACK = 0,
  PREDICT = 1,
  SEARCH = 2,
  RECOVER = 3,
};

struct LineObservation {
  bool line_visible = false;
  double normalized_error = 0.0;
  double confidence = 0.0;
  double signal_strength = 0.0;
  double left_band = 0.0;
  double center_band = 0.0;
  double right_band = 0.0;
};

struct FollowMemory {
  TrackingState state = SEARCH;
  double filtered_error = 0.0;
  double last_error = 0.0;
  double last_turn_sign = 1.0;
  int lost_steps = 0;
};

// webots-kit region HELPERS start
static double clamp_value(double value, double minimum, double maximum) {
  return std::max(minimum, std::min(maximum, value));
}

static void set_drive_velocity(webots::Motor* front_left_motor,
                               webots::Motor* rear_left_motor,
                               webots::Motor* front_right_motor,
                               webots::Motor* rear_right_motor,
                               double left_velocity,
                               double right_velocity) {
  front_left_motor->setVelocity(left_velocity);
  rear_left_motor->setVelocity(left_velocity);
  front_right_motor->setVelocity(right_velocity);
  rear_right_motor->setVelocity(right_velocity);
}

static double band_average(const std::vector<double>& values, int start, int end) {
  start = std::max(0, start);
  end = std::min(static_cast<int>(values.size()), end);
  if (end <= start)
    return 0.0;
  double total = 0.0;
  for (int index = start; index < end; ++index)
    total += values[index];
  return total / std::max(end - start, 1);
}

static LineObservation analyze_line_frame(const unsigned char* image, int width, int height) {
  const std::vector<double> row_weights = {0.55, 0.3, 0.15};
  const std::vector<double> row_ratios = {0.64, 0.78, 0.9};
  double weighted_error = 0.0;
  double weighted_confidence = 0.0;
  double total_visible_weight = 0.0;
  double left_band = 0.0;
  double center_band = 0.0;
  double right_band = 0.0;
  double signal_strength = 0.0;
  for (size_t row_index = 0; row_index < row_ratios.size(); ++row_index) {
    const int row = std::max(0, std::min(height - 1, static_cast<int>(std::round(row_ratios[row_index] * (height - 1)))));
    std::vector<double> values(width, 0.0);
    double row_total = 0.0;
    double max_value = 0.0;
    double min_value = 255.0;
    for (int x = 0; x < width; ++x) {
      double sample = 255.0 - static_cast<double>(Camera::imageGetBlue(image, width, x, row));
      if (x > 0 && x + 1 < width) {
        sample = (sample + (255.0 - static_cast<double>(Camera::imageGetBlue(image, width, x - 1, row))) +
                  (255.0 - static_cast<double>(Camera::imageGetBlue(image, width, x + 1, row)))) /
                 3.0;
      }
      values[x] = sample;
      row_total += sample;
      max_value = std::max(max_value, sample);
      min_value = std::min(min_value, sample);
    }
    const double row_mean = row_total / std::max(width, 1);
    const double threshold = std::max(14.0, row_mean * 0.95);
    double weighted_sum = 0.0;
    double total_weight = 0.0;
    for (int x = 0; x < width; ++x) {
      const double score = std::max(0.0, values[x] - threshold);
      if (score <= 0.0)
        continue;
      weighted_sum += score * static_cast<double>(x);
      total_weight += score;
    }
    const bool visible = total_weight > static_cast<double>(width) * 1.75;
    const double center = visible ? (weighted_sum / std::max(total_weight, 1e-6)) : static_cast<double>(width - 1) / 2.0;
    const double normalized_error = (center - static_cast<double>(width) / 2.0) / std::max(static_cast<double>(width) / 2.0, 1.0);
    const double row_confidence = visible ? clamp_value(total_weight / std::max(static_cast<double>(width) * 22.0, 1.0), 0.0, 1.0) : 0.0;
    const int third = std::max(width / 3, 1);
    left_band += band_average(values, 0, third) * row_weights[row_index];
    center_band += band_average(values, third, 2 * third) * row_weights[row_index];
    right_band += band_average(values, 2 * third, width) * row_weights[row_index];
    signal_strength += (max_value - min_value) * row_weights[row_index];
    if (visible) {
      weighted_error += normalized_error * row_weights[row_index];
      weighted_confidence += row_confidence * row_weights[row_index];
      total_visible_weight += row_weights[row_index];
    }
  }
  if (total_visible_weight > 0.0)
    weighted_error /= total_visible_weight;
  return LineObservation{
      total_visible_weight > 0.0,
      clamp_value(weighted_error, -1.0, 1.0),
      clamp_value(weighted_confidence, 0.0, 1.0),
      std::max(signal_strength / 255.0, 0.0),
      left_band,
      center_band,
      right_band,
  };
}

static void update_memory(FollowMemory& memory, const LineObservation& observation) {
  if (observation.line_visible) {
    memory.state = memory.lost_steps > 0 ? RECOVER : TRACK;
    memory.filtered_error = 0.7 * memory.filtered_error + 0.3 * observation.normalized_error;
    memory.last_error = observation.normalized_error;
    memory.lost_steps = 0;
    if (std::fabs(observation.normalized_error) > 0.05)
      memory.last_turn_sign = observation.normalized_error >= 0.0 ? 1.0 : -1.0;
    return;
  }
  memory.lost_steps += 1;
  if (memory.lost_steps <= 3)
    memory.state = PREDICT;
  else if (memory.lost_steps <= 9)
    memory.state = SEARCH;
  else
    memory.state = RECOVER;
  memory.filtered_error = 0.82 * memory.filtered_error + 0.18 * memory.last_error;
}

static std::tuple<double, double, bool> compute_drive_targets(const FollowMemory& memory, const LineObservation& observation) {
  double base_speed = CRUISE;
  double turn = TURN_GAIN * memory.filtered_error;
  if (observation.line_visible && std::fabs(memory.filtered_error) > 0.35)
    base_speed *= 0.72;
  if (observation.line_visible && observation.confidence < 0.3)
    base_speed *= 0.75;
  if (memory.state == PREDICT) {
    base_speed *= 0.68;
    turn = TURN_GAIN * 0.85 * memory.filtered_error;
  } else if (memory.state == SEARCH) {
    base_speed = 2.2;
    turn = SEARCH_GAIN * memory.last_turn_sign;
  } else if (memory.state == RECOVER) {
    base_speed = 1.4;
    turn = RECOVER_GAIN * memory.last_turn_sign;
  }
  const double left_speed = clamp_value(base_speed - turn, -MAX_SPEED, MAX_SPEED);
  const double right_speed = clamp_value(base_speed + turn, -MAX_SPEED, MAX_SPEED);
  const bool saturated = std::fabs(left_speed) >= (MAX_SPEED - 0.05) || std::fabs(right_speed) >= (MAX_SPEED - 0.05);
  return std::make_tuple(left_speed, right_speed, saturated);
}
// webots-kit region HELPERS end

int main() {
  Robot robot;

  // webots-kit region DEVICE_INIT start
  auto* front_left_motor = robot.getMotor("front_left_motor");
  auto* rear_left_motor = robot.getMotor("rear_left_motor");
  auto* front_right_motor = robot.getMotor("front_right_motor");
  auto* rear_right_motor = robot.getMotor("rear_right_motor");
  for (auto* motor : {front_left_motor, rear_left_motor, front_right_motor, rear_right_motor}) {
    motor->setPosition(std::numeric_limits<double>::infinity());
    motor->setVelocity(0.0);
  }

  auto* left_encoder = robot.getPositionSensor("left_encoder");
  auto* right_encoder = robot.getPositionSensor("right_encoder");
  left_encoder->enable(TIME_STEP);
  right_encoder->enable(TIME_STEP);

  auto* front_camera = robot.getCamera("front_camera");
  front_camera->enable(TIME_STEP);
  const int width = front_camera->getWidth();
  const int height = front_camera->getHeight();

  auto* front_range = robot.getDistanceSensor("front_range");
  front_range->enable(TIME_STEP);

  auto* imu = robot.getInertialUnit("imu");
  imu->enable(TIME_STEP);
  // webots-kit region DEVICE_INIT end

  auto agent = ControllerAgent::from_robot(&robot, "front_camera");
  double previous_heading = 0.0;
  FollowMemory memory;

  while (robot.step(TIME_STEP) != -1) {
    const unsigned char* image = front_camera->getImage();
    const LineObservation observation = analyze_line_frame(image, width, height);
    update_memory(memory, observation);

    const double* rpy = imu->getRollPitchYaw();
    const double heading = rpy[2];
    const double yaw_rate = (heading - previous_heading) / std::max(TIME_STEP / 1000.0, 1e-6);
    previous_heading = heading;
    const double front_range_value = front_range->getValue();
    const double left_ticks = left_encoder->getValue();
    const double right_ticks = right_encoder->getValue();

    // webots-kit region CONTROL_POLICY start
    auto targets = compute_drive_targets(memory, observation);
    double left_speed = std::get<0>(targets);
    double right_speed = std::get<1>(targets);
    bool speed_saturation = std::get<2>(targets);
    // webots-kit region CONTROL_POLICY end

    auto override = agent.begin_step();
    if (override.has_value()) {
      left_speed = override->first;
      right_speed = override->second;
      speed_saturation = std::fabs(left_speed) >= (MAX_SPEED - 0.05) || std::fabs(right_speed) >= (MAX_SPEED - 0.05);
    }

    set_drive_velocity(front_left_motor, rear_left_motor, front_right_motor, rear_right_motor, left_speed, right_speed);

    // webots-kit region TELEMETRY_REPORT start
    std::map<std::string, double> sensors = {
      {"camera_left_band", observation.left_band},
      {"camera_center_band", observation.center_band},
      {"camera_right_band", observation.right_band},
      {"front_range", front_range_value},
      {"heading", heading},
      {"yaw_rate", yaw_rate},
      {"left_encoder", left_ticks},
      {"right_encoder", right_ticks}
    };
    std::map<std::string, double> metrics = {
      {"line_visible", observation.line_visible ? 1.0 : 0.0},
      {"center_error", memory.filtered_error},
      {"ir_balance_error", (observation.left_band - observation.right_band) / 255.0},
      {"line_confidence", observation.confidence},
      {"camera_signal_strength", observation.signal_strength},
      {"tracking_state_code", static_cast<double>(memory.state)},
      {"speed_saturation", speed_saturation ? 1.0 : 0.0},
      {"mean_forward_speed", (left_speed + right_speed) / 2.0}
    };
    std::map<std::string, double> actuators = {
      {"left_velocity", left_speed},
      {"right_velocity", right_speed}
    };
    std::vector<CameraFrame> camera_frames = {
      CameraFrame{"front_camera", image, width, height}
    };
    // webots-kit region TELEMETRY_REPORT end

    agent.report_step(sensors, metrics, actuators, camera_frames);
  }
  return 0;
}
'''


def _cpp_monsterborg_obstacle_template() -> str:
    return r'''#include "controller_agent.hpp"

#include <webots/Camera.hpp>
#include <webots/DistanceSensor.hpp>
#include <webots/InertialUnit.hpp>
#include <webots/Motor.hpp>
#include <webots/PositionSensor.hpp>
#include <webots/Robot.hpp>

#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <string>
#include <vector>

using webots::Robot;
using webots_mcp_kit::CameraFrame;
using webots_mcp_kit::ControllerAgent;

const double MAX_SPEED = 8.0;
const double CRUISE = 5.4;
const double RANGE_LIMIT = 900.0;
const double CAUTION_RANGE = 470.0;
const double HARD_STOP_RANGE = 280.0;

enum ObstacleState {
  CRUISE_STATE = 0,
  AVOID_STATE = 1,
  RECOVER_STATE = 2,
};

// webots-kit region HELPERS start
static double clamp_value(double value) {
  return std::max(-MAX_SPEED, std::min(MAX_SPEED, value));
}

static void set_drive_velocity(webots::Motor* front_left_motor,
                               webots::Motor* rear_left_motor,
                               webots::Motor* front_right_motor,
                               webots::Motor* rear_right_motor,
                               double left_velocity,
                               double right_velocity) {
  front_left_motor->setVelocity(left_velocity);
  rear_left_motor->setVelocity(left_velocity);
  front_right_motor->setVelocity(right_velocity);
  rear_right_motor->setVelocity(right_velocity);
}

static double progress_step(double left_ticks, double right_ticks, double previous_left, double previous_right, bool initialized) {
  if (!initialized)
    return 0.0;
  return std::abs(((left_ticks - previous_left) + (right_ticks - previous_right)) / 2.0) * 0.05;
}
// webots-kit region HELPERS end

int main() {
  Robot robot;
  const int time_step = static_cast<int>(robot.getBasicTimeStep());

  // webots-kit region DEVICE_INIT start
  auto* front_left_motor = robot.getMotor("front_left_motor");
  auto* rear_left_motor = robot.getMotor("rear_left_motor");
  auto* front_right_motor = robot.getMotor("front_right_motor");
  auto* rear_right_motor = robot.getMotor("rear_right_motor");
  for (auto* motor : {front_left_motor, rear_left_motor, front_right_motor, rear_right_motor}) {
    motor->setPosition(std::numeric_limits<double>::infinity());
    motor->setVelocity(0.0);
  }

  auto* left_encoder = robot.getPositionSensor("left_encoder");
  auto* right_encoder = robot.getPositionSensor("right_encoder");
  left_encoder->enable(time_step);
  right_encoder->enable(time_step);

  auto* front_camera = robot.getCamera("front_camera");
  front_camera->enable(time_step);

  auto* front_range = robot.getDistanceSensor("front_range");
  front_range->enable(time_step);

  auto* imu = robot.getInertialUnit("imu");
  imu->enable(time_step);
  // webots-kit region DEVICE_INIT end

  auto agent = ControllerAgent::from_robot(&robot, "front_camera");
  double previous_heading = 0.0;
  int state_code = CRUISE_STATE;
  int heading_recovery_events = 0;
  int stalled_steps = 0;
  double search_direction = 1.0;
  bool encoders_initialized = false;
  double previous_left_ticks = 0.0;
  double previous_right_ticks = 0.0;

  while (robot.step(time_step) != -1) {
    const double front_range_value = front_range->getValue();
    const double normalized_range = std::min(std::max(front_range_value / RANGE_LIMIT, 0.0), 1.0);
    const double* rpy = imu->getRollPitchYaw();
    const double heading = rpy[2];
    const double yaw_rate = (heading - previous_heading) / std::max(time_step / 1000.0, 1e-6);
    previous_heading = heading;
    const double left_ticks = left_encoder->getValue();
    const double right_ticks = right_encoder->getValue();
    const double step_distance = progress_step(left_ticks, right_ticks, previous_left_ticks, previous_right_ticks, encoders_initialized);
    previous_left_ticks = left_ticks;
    previous_right_ticks = right_ticks;
    encoders_initialized = true;

    // webots-kit region CONTROL_POLICY start
    const double pressure = 1.0 - normalized_range;
    if (std::abs(heading) > 0.05)
      search_direction = heading > 0.0 ? -1.0 : 1.0;
    else if (std::abs(yaw_rate) > 0.02)
      search_direction = yaw_rate > 0.0 ? -1.0 : 1.0;
    int next_state = CRUISE_STATE;
    if (front_range_value < HARD_STOP_RANGE)
      next_state = RECOVER_STATE;
    else if (front_range_value < CAUTION_RANGE)
      next_state = AVOID_STATE;
    if (next_state != state_code && next_state == RECOVER_STATE)
      heading_recovery_events += 1;
    state_code = next_state;
    double base_speed = CRUISE;
    double turn = 0.0;
    if (state_code == CRUISE_STATE) {
      base_speed = CRUISE * std::max(0.7, 1.0 - pressure * 0.25);
      turn = std::max(-2.4, std::min(2.4, heading * 1.1 + yaw_rate * 0.18));
    } else if (state_code == AVOID_STATE) {
      base_speed = 2.6;
      turn = 3.8 * search_direction + yaw_rate * 0.35;
    } else {
      base_speed = 1.2;
      turn = 4.8 * search_direction;
    }
    double left_speed = clamp_value(base_speed - turn);
    double right_speed = clamp_value(base_speed + turn);
    // webots-kit region CONTROL_POLICY end

    auto override = agent.begin_step();
    if (override.has_value()) {
      left_speed = override->first;
      right_speed = override->second;
    }

    set_drive_velocity(front_left_motor, rear_left_motor, front_right_motor, rear_right_motor, left_speed, right_speed);
    const unsigned char* image = front_camera->getImage();
    const double mean_forward_speed = (left_speed + right_speed) / 2.0;
    if (std::abs(mean_forward_speed) > 1.0 && step_distance < 0.0015 && front_range_value < CAUTION_RANGE)
      stalled_steps += 1;
    const double speed_saturation = (std::abs(left_speed) >= MAX_SPEED - 0.05 || std::abs(right_speed) >= MAX_SPEED - 0.05) ? 1.0 : 0.0;

    // webots-kit region TELEMETRY_REPORT start
    std::map<std::string, double> sensors = {
      {"front_range", front_range_value},
      {"heading", heading},
      {"yaw_rate", yaw_rate},
      {"left_encoder", left_ticks},
      {"right_encoder", right_ticks}
    };
    std::map<std::string, double> metrics = {
      {"obstacle_pressure", pressure},
      {"mean_forward_speed", mean_forward_speed},
      {"front_clearance_margin", (front_range_value - CAUTION_RANGE) / CAUTION_RANGE},
      {"clearance_violation", front_range_value < HARD_STOP_RANGE ? 1.0 : 0.0},
      {"heading_recovery_events", static_cast<double>(heading_recovery_events)},
      {"stalled_steps", static_cast<double>(stalled_steps)},
      {"avoidance_state_code", static_cast<double>(state_code)},
      {"speed_saturation", speed_saturation},
      {"line_visible", 0.0},
      {"center_error", 0.0},
      {"ir_balance_error", (left_ticks - right_ticks) * 0.01}
    };
    std::map<std::string, double> actuators = {
      {"left_velocity", left_speed},
      {"right_velocity", right_speed}
    };
    std::vector<CameraFrame> camera_frames = {
      CameraFrame{"front_camera", image, front_camera->getWidth(), front_camera->getHeight()}
    };
    // webots-kit region TELEMETRY_REPORT end

    agent.report_step(sensors, metrics, actuators, camera_frames);
  }
  return 0;
}
'''


def _cpp_monsterborg_waypoint_template() -> str:
    return r'''#include "controller_agent.hpp"

#include <webots/Camera.hpp>
#include <webots/DistanceSensor.hpp>
#include <webots/InertialUnit.hpp>
#include <webots/Motor.hpp>
#include <webots/PositionSensor.hpp>
#include <webots/Robot.hpp>

#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <string>
#include <vector>

using webots::Robot;
using webots_mcp_kit::CameraFrame;
using webots_mcp_kit::ControllerAgent;

const double MAX_SPEED = 8.0;
const double CRUISE = 5.8;
const double RANGE_LIMIT = 900.0;
const double CAUTION_RANGE = 420.0;
const double HARD_STOP_RANGE = 260.0;
const double TARGET_DISTANCE = 1.35;

enum WaypointState {
  RECOVER_STATE = 2,
  ALIGN_STATE = 3,
  ADVANCE_STATE = 4,
  HOLD_STATE = 5,
};

// webots-kit region HELPERS start
static double clamp_value(double value) {
  return std::max(-MAX_SPEED, std::min(MAX_SPEED, value));
}

static void set_drive_velocity(webots::Motor* front_left_motor,
                               webots::Motor* rear_left_motor,
                               webots::Motor* front_right_motor,
                               webots::Motor* rear_right_motor,
                               double left_velocity,
                               double right_velocity) {
  front_left_motor->setVelocity(left_velocity);
  rear_left_motor->setVelocity(left_velocity);
  front_right_motor->setVelocity(right_velocity);
  rear_right_motor->setVelocity(right_velocity);
}

static double wrap_angle(double value) {
  while (value > 3.141592653589793)
    value -= 6.283185307179586;
  while (value < -3.141592653589793)
    value += 6.283185307179586;
  return value;
}

static double progress_step(double left_ticks, double right_ticks, double previous_left, double previous_right, bool initialized) {
  if (!initialized)
    return 0.0;
  return std::abs(((left_ticks - previous_left) + (right_ticks - previous_right)) / 2.0) * 0.05;
}
// webots-kit region HELPERS end

int main() {
  Robot robot;
  const int time_step = static_cast<int>(robot.getBasicTimeStep());

  // webots-kit region DEVICE_INIT start
  auto* front_left_motor = robot.getMotor("front_left_motor");
  auto* rear_left_motor = robot.getMotor("rear_left_motor");
  auto* front_right_motor = robot.getMotor("front_right_motor");
  auto* rear_right_motor = robot.getMotor("rear_right_motor");
  for (auto* motor : {front_left_motor, rear_left_motor, front_right_motor, rear_right_motor}) {
    motor->setPosition(std::numeric_limits<double>::infinity());
    motor->setVelocity(0.0);
  }

  auto* left_encoder = robot.getPositionSensor("left_encoder");
  auto* right_encoder = robot.getPositionSensor("right_encoder");
  left_encoder->enable(time_step);
  right_encoder->enable(time_step);

  auto* front_camera = robot.getCamera("front_camera");
  front_camera->enable(time_step);

  auto* front_range = robot.getDistanceSensor("front_range");
  front_range->enable(time_step);

  auto* imu = robot.getInertialUnit("imu");
  imu->enable(time_step);
  // webots-kit region DEVICE_INIT end

  auto agent = ControllerAgent::from_robot(&robot, "front_camera");
  double previous_heading = 0.0;
  int state_code = ALIGN_STATE;
  int waypoint_recovery_events = 0;
  int stalled_steps = 0;
  double encoder_distance = 0.0;
  double search_direction = 1.0;
  bool encoders_initialized = false;
  double previous_left_ticks = 0.0;
  double previous_right_ticks = 0.0;

  while (robot.step(time_step) != -1) {
    const double front_range_value = front_range->getValue();
    const double normalized_range = std::min(std::max(front_range_value / RANGE_LIMIT, 0.0), 1.0);
    const double* rpy = imu->getRollPitchYaw();
    const double heading = rpy[2];
    const double yaw_rate = (heading - previous_heading) / std::max(time_step / 1000.0, 1e-6);
    previous_heading = heading;
    const double left_ticks = left_encoder->getValue();
    const double right_ticks = right_encoder->getValue();
    const double step_distance = progress_step(left_ticks, right_ticks, previous_left_ticks, previous_right_ticks, encoders_initialized);
    encoder_distance += step_distance;
    previous_left_ticks = left_ticks;
    previous_right_ticks = right_ticks;
    encoders_initialized = true;

    // webots-kit region CONTROL_POLICY start
    const double obstacle_pressure = 1.0 - normalized_range;
    const double heading_error = wrap_angle(0.0 - heading);
    const double heading_alignment_error = std::abs(heading_error);
    const double progress_ratio = std::max(0.0, std::min(1.0, encoder_distance / TARGET_DISTANCE));
    const double distance_to_goal_estimate = std::max(0.0, TARGET_DISTANCE - encoder_distance);
    if (std::abs(heading_error) > 0.04)
      search_direction = heading_error > 0.0 ? 1.0 : -1.0;
    else if (std::abs(yaw_rate) > 0.02)
      search_direction = yaw_rate > 0.0 ? -1.0 : 1.0;
    int next_state = ADVANCE_STATE;
    if (front_range_value < HARD_STOP_RANGE)
      next_state = RECOVER_STATE;
    else if (heading_alignment_error > 0.28)
      next_state = ALIGN_STATE;
    else if (progress_ratio >= 0.995)
      next_state = HOLD_STATE;
    if (next_state != state_code && (next_state == ALIGN_STATE || next_state == RECOVER_STATE))
      waypoint_recovery_events += 1;
    state_code = next_state;
    double base_speed = 0.0;
    double turn = 0.0;
    if (state_code == ADVANCE_STATE) {
      base_speed = CRUISE * std::max(0.55, 1.0 - heading_alignment_error * 0.65);
      if (front_range_value < CAUTION_RANGE)
        base_speed *= 0.72;
      turn = std::max(-3.2, std::min(3.2, heading_error * 3.6 - yaw_rate * 0.32));
    } else if (state_code == ALIGN_STATE) {
      base_speed = 1.5;
      turn = 4.4 * search_direction;
    } else if (state_code == RECOVER_STATE) {
      base_speed = 0.8;
      turn = 5.0 * search_direction;
    }
    double left_speed = clamp_value(base_speed - turn);
    double right_speed = clamp_value(base_speed + turn);
    // webots-kit region CONTROL_POLICY end

    auto override = agent.begin_step();
    if (override.has_value()) {
      left_speed = override->first;
      right_speed = override->second;
    }

    set_drive_velocity(front_left_motor, rear_left_motor, front_right_motor, rear_right_motor, left_speed, right_speed);
    const unsigned char* image = front_camera->getImage();
    const double mean_forward_speed = (left_speed + right_speed) / 2.0;
    if ((state_code == ADVANCE_STATE || state_code == ALIGN_STATE) && std::abs(mean_forward_speed) > 1.0 && step_distance < 0.0015)
      stalled_steps += 1;
    const double speed_saturation = (std::abs(left_speed) >= MAX_SPEED - 0.05 || std::abs(right_speed) >= MAX_SPEED - 0.05) ? 1.0 : 0.0;
    const double path_deviation_score = heading_alignment_error * 0.8 + std::abs(yaw_rate) * 0.12 + obstacle_pressure * 0.2;

    // webots-kit region TELEMETRY_REPORT start
    std::map<std::string, double> sensors = {
      {"front_range", front_range_value},
      {"heading", heading},
      {"yaw_rate", yaw_rate},
      {"left_encoder", left_ticks},
      {"right_encoder", right_ticks}
    };
    std::map<std::string, double> metrics = {
      {"obstacle_pressure", obstacle_pressure},
      {"mean_forward_speed", mean_forward_speed},
      {"progress_ratio", progress_ratio},
      {"distance_to_goal_estimate", distance_to_goal_estimate},
      {"heading_alignment_error", heading_alignment_error},
      {"path_deviation_score", path_deviation_score},
      {"waypoint_recovery_events", static_cast<double>(waypoint_recovery_events)},
      {"stalled_steps", static_cast<double>(stalled_steps)},
      {"waypoint_state_code", static_cast<double>(state_code)},
      {"speed_saturation", speed_saturation},
      {"line_visible", 0.0},
      {"center_error", 0.0},
      {"ir_balance_error", (left_ticks - right_ticks) * 0.01}
    };
    std::map<std::string, double> actuators = {
      {"left_velocity", left_speed},
      {"right_velocity", right_speed}
    };
    std::vector<CameraFrame> camera_frames = {
      CameraFrame{"front_camera", image, front_camera->getWidth(), front_camera->getHeight()}
    };
    // webots-kit region TELEMETRY_REPORT end

    agent.report_step(sensors, metrics, actuators, camera_frames);
  }
  return 0;
}
'''
