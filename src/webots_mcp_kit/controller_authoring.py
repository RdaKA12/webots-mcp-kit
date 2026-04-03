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

from .benchmarks import get_scenario
from .environment import build_process_env, current_python, get_webots_environment
from .errors import KitError

REGION_NAMES = ("DEVICE_INIT", "CONTROL_POLICY", "TELEMETRY_REPORT", "HELPERS")
CPP_SOURCE_SUFFIXES = {".cpp", ".cc", ".cxx"}
CONTROLLER_SOURCE_SUFFIXES = {".py", *CPP_SOURCE_SUFFIXES}


@dataclass(slots=True)
class ControllerInspectionResult:
    path: str
    language: str
    scenario: str | None
    integration_mode: str
    valid_source: bool
    editable_regions: list[str] = field(default_factory=list)
    markers_present: bool = False
    has_robot_init: bool = False
    has_step_loop: bool = False
    has_from_robot: bool = False
    has_begin_step: bool = False
    has_report_step: bool = False
    default_camera: str | None = None
    device_bindings: list[str] = field(default_factory=list)
    telemetry_sections: dict[str, list[str]] = field(default_factory=dict)
    benchmark_readiness: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

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
) -> ControllerInspectionResult:
    resolved = path if path.is_absolute() else (Path.cwd() / path).resolve()
    language = detect_controller_language(resolved)
    scenario_name = scenario or _scenario_from_spec(spec_path)
    scenario_def = get_scenario(scenario_name) if scenario_name else None

    if not resolved.exists():
        return ControllerInspectionResult(
            path=str(resolved),
            language=language,
            scenario=scenario_name,
            integration_mode="unknown",
            valid_source=False,
            issues=["Controller file does not exist."],
        )

    if language not in {"python", "cpp"}:
        return ControllerInspectionResult(
            path=str(resolved),
            language=language,
            scenario=scenario_name,
            integration_mode="unknown",
            valid_source=False,
            issues=["Unsupported controller source type."],
        )

    try:
        source = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        return ControllerInspectionResult(
            path=str(resolved),
            language=language,
            scenario=scenario_name,
            integration_mode="unknown",
            valid_source=False,
            issues=[f"Unable to read controller file: {exc}"],
        )

    if language == "python":
        inspection = _inspect_python_source(resolved, source, scenario_name)
    else:
        inspection = _inspect_cpp_source(resolved, source, scenario_name)

    if scenario_def:
        benchmark_ready, benchmark_issues = _benchmark_readiness_from_sections(
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
    return inspection


def scaffold_source(*, scenario: str, language: str) -> tuple[str, dict[str, Any]]:
    scenario_def = get_scenario(scenario)
    if language == "python":
        return _python_template_for_scenario(scenario), {
            "language": language,
            "scenario": scenario_def.name,
            "default_camera": scenario_def.default_camera,
        }
    if language == "cpp":
        return _cpp_template_for_scenario(scenario), {
            "language": language,
            "scenario": scenario_def.name,
            "default_camera": scenario_def.default_camera,
            "sdk_header": str(controller_sdk_header()),
        }
    raise KitError(
        "unsupported-controller-language",
        f"Unsupported controller language '{language}'.",
        details={"supported_languages": ["python", "cpp"]},
    )


def scaffold_controller_artifacts(path: Path, *, scenario: str, language: str, force: bool = False) -> dict[str, Any]:
    target = path if path.is_absolute() else (Path.cwd() / path).resolve()
    if target.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)

    source, metadata = scaffold_source(scenario=scenario, language=language)
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
        "copied_files": copied_files,
        "editable_regions": list(REGION_NAMES),
    }


def edit_controller(path: Path, *, plan_path: Path | None = None, plan: dict[str, Any] | None = None) -> dict[str, Any]:
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
    inspection = inspect_controller(target, scenario=plan_payload.get("scenario_context", {}).get("scenario"))
    return {
        "path": str(target),
        "language": language,
        "applied_operations": applied,
        "editable_regions": inspection.editable_regions,
        "next_step": f"Run `webots-kit controller validate \"{target}\" --strict --json`.",
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
        f"controller_inspection: {'pass' if result.valid_source else 'fail'}",
        f"path: {result.path}",
        f"language: {result.language}",
        f"scenario: {result.scenario}",
        f"integration_mode: {result.integration_mode}",
        f"editable_regions: {result.editable_regions}",
        f"default_camera: {result.default_camera}",
        f"device_bindings: {result.device_bindings}",
        f"benchmark_ready: {readiness.get('ready')}",
        f"summary: {len(result.issues)} issues",
    ]
    if result.telemetry_sections:
        lines.append(f"telemetry_sections: {result.telemetry_sections}")
    if result.issues:
        lines.append("issues:")
        lines.extend(f"- {issue}" for issue in result.issues)
    lines.append(
        "next_step: Run `webots-kit controller validate <path> --strict --json` or apply `webots-kit controller edit <path> --plan <plan.json>`."
    )
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
    if sorted(expected_sensors) != sorted(telemetry_sections.get("sensors", [])):
        issues.append("Sensor telemetry keys do not match benchmark expectations.")
    if sorted(expected_metrics) != sorted(telemetry_sections.get("metrics", [])):
        issues.append("Metric telemetry keys do not match benchmark expectations.")
    if sorted(expected_actuators) != sorted(telemetry_sections.get("actuators", [])):
        issues.append("Actuator telemetry keys do not match benchmark expectations.")
    return not issues, issues


def _inspect_python_source(path: Path, source: str, scenario_name: str | None) -> ControllerInspectionResult:
    result = ControllerInspectionResult(
        path=str(path),
        language="python",
        scenario=scenario_name,
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
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "webots_mcp_kit.agent":
            if any(alias.name == "ControllerAgent" for alias in node.names):
                imported_controller_agent = True
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            keys = _literal_dict_keys(node.value)
            if keys is not None:
                literal_dict_assignments[node.targets[0].id] = keys
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

    result.integration_mode = "controller-agent" if imported_controller_agent else "plain-webots"
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


def _inspect_cpp_source(path: Path, source: str, scenario_name: str | None) -> ControllerInspectionResult:
    result = ControllerInspectionResult(
        path=str(path),
        language="cpp",
        scenario=scenario_name,
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

    result.device_bindings = sorted(
        {
            match.group(1)
            for match in re.finditer(r'(?:getDevice|getCamera|getMotor|getDistanceSensor)\s*\(\s*"([^"]+)"\s*\)', source)
        }
    )

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


def _python_template_for_scenario(scenario: str) -> str:
    templates = {
        "line-follower": _python_line_follower_template,
        "obstacle-avoidance": _python_obstacle_template,
        "waypoint-nav": _python_waypoint_template,
    }
    return templates[scenario]()


def _cpp_template_for_scenario(scenario: str) -> str:
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
