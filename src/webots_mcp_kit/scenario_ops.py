from __future__ import annotations

import json
import math
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import __version__
from .benchmark import benchmark_next_step
from .benchmarks import get_scenario
from .controller_scaffold import scaffold_controller
from .diagnostics import collect_runtime_diagnostics
from .errors import KitError
from .models import (
    SESSION_EXPORT_ARTIFACT_STANDARD_VERSION,
    SESSION_EXPORT_STANDARD_ARTIFACTS,
    GeneratedScenario,
    ProjectManifest,
    ScenarioSpec,
    SessionExport,
)
from .session_store import SessionStore
from .utils import atomic_write_text, utc_now_iso

PROJECT_MANIFEST_FILENAME = "webots-kit.project.json"
SCENARIO_SPEC_FILENAME = "webots-kit.scenario.json"
GENERATED_METADATA_FILENAME = "webots-kit.generated.json"
BENCHMARK_CONFIG_FILENAME = "benchmark.config.json"

SUPPORTED_TASKS = {
    "line-follow": "line-follower",
    "waypoint-nav": "waypoint-nav",
    "obstacle-avoidance": "obstacle-avoidance",
}

SUPPORTED_ENVIRONMENT_TEMPLATES = {
    "epuck-arena": {"default_kind": "waypoint-nav", "allowed_kinds": {"waypoint-nav", "obstacle-avoidance"}},
    "epuck-line-track": {"default_kind": "line-follow", "allowed_kinds": {"line-follow"}},
    "epuck-waypoint": {"default_kind": "waypoint-nav", "allowed_kinds": {"waypoint-nav"}},
    "epuck-obstacle-course": {"default_kind": "obstacle-avoidance", "allowed_kinds": {"obstacle-avoidance", "waypoint-nav"}},
}


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    field: str | None = None
    level: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScenarioValidationResult:
    spec_path: str
    valid: bool
    scenario_name: str | None
    scenario_kind: str | None
    environment_template: str | None
    benchmark_name: str | None
    issues: list[ValidationIssue] = field(default_factory=list)
    normalized: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_path": self.spec_path,
            "valid": self.valid,
            "scenario_name": self.scenario_name,
            "scenario_kind": self.scenario_kind,
            "environment_template": self.environment_template,
            "benchmark_name": self.benchmark_name,
            "issues": [issue.to_dict() for issue in self.issues],
            "normalized": self.normalized,
        }


def project_manifest_path(project_root: Path) -> Path:
    return project_root / PROJECT_MANIFEST_FILENAME


def scenario_spec_path(path: Path) -> Path:
    resolved = path if path.is_absolute() else (Path.cwd() / path).resolve()
    if resolved.suffix == ".json":
        return resolved
    return resolved / SCENARIO_SPEC_FILENAME


def init_project(path: Path, *, name: str | None = None, force: bool = False) -> dict[str, Any]:
    project_root = path if path.is_absolute() else (Path.cwd() / path).resolve()
    manifest_path = project_manifest_path(project_root)
    if manifest_path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing project manifest: {manifest_path}")

    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "scenarios").mkdir(exist_ok=True)
    (project_root / "artifacts").mkdir(exist_ok=True)

    manifest = ProjectManifest(
        schema_version=1,
        toolkit_version=__version__,
        project_name=name or project_root.name,
        created_at=utc_now_iso(),
        root_dir=str(project_root),
        scenarios_dir="scenarios",
        notes=[
            "This project uses template-driven scenario generation.",
            "Runtime smoke requires an interactive self-hosted runner labeled interactive-webots.",
        ],
    )
    atomic_write_text(manifest_path, json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    return {
        "project_root": str(project_root),
        "manifest_path": str(manifest_path),
        "scenarios_dir": str(project_root / "scenarios"),
        "artifacts_dir": str(project_root / "artifacts"),
        "support_tier": "experimental-foundation",
    }


def init_scenario(path: Path, *, template: str, force: bool = False) -> dict[str, Any]:
    if template not in SUPPORTED_ENVIRONMENT_TEMPLATES:
        raise KitError(
            "unsupported-environment-template",
            f"Unsupported environment template '{template}'.",
            details={"supported_templates": sorted(SUPPORTED_ENVIRONMENT_TEMPLATES)},
        )
    spec_path = scenario_spec_path(path)
    scenario_dir = spec_path.parent
    if spec_path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing scenario spec: {spec_path}")

    scenario_dir.mkdir(parents=True, exist_ok=True)
    project_root = _discover_project_root(scenario_dir)
    manifest = _load_project_manifest(project_root)
    scenario_name = scenario_dir.name
    spec = _default_spec(template=template, scenario_name=scenario_name, project_name=manifest.project_name)
    atomic_write_text(spec_path, json.dumps(spec.to_dict(), indent=2), encoding="utf-8")
    return {
        "spec_path": str(spec_path),
        "project_root": str(project_root),
        "scenario_name": scenario_name,
        "template": template,
        "scenario_kind": spec.scenario["kind"],
        "support_tier": "experimental-foundation",
    }


def load_scenario_spec(path: Path) -> ScenarioSpec:
    spec_path = scenario_spec_path(path)
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    return ScenarioSpec.from_dict(payload)


def validate_scenario(path: Path) -> ScenarioValidationResult:
    spec_path = scenario_spec_path(path)
    issues: list[ValidationIssue] = []
    try:
        spec = load_scenario_spec(spec_path)
    except FileNotFoundError:
        issues.append(ValidationIssue(code="scenario-spec-missing", message="Scenario spec file does not exist.", field="spec_path"))
        return ScenarioValidationResult(str(spec_path), False, None, None, None, None, issues)
    except json.JSONDecodeError as exc:
        issues.append(
            ValidationIssue(
                code="scenario-spec-invalid-json",
                message=f"Scenario spec is not valid JSON: {exc.msg}",
                field="spec_path",
            )
        )
        return ScenarioValidationResult(str(spec_path), False, None, None, None, None, issues)

    normalized = spec.to_dict()
    scenario_name = _str_field(spec.scenario, "name")
    scenario_kind = _str_field(spec.scenario, "kind")
    robot_template = _str_field(spec.robot, "template")
    environment_template = _str_field(spec.environment, "template")
    benchmark_name = SUPPORTED_TASKS.get(scenario_kind)

    if spec.schema_version != 1:
        issues.append(ValidationIssue("unsupported-scenario-schema", f"Unsupported schema version '{spec.schema_version}'.", "schema_version"))
    if not _str_field(spec.project, "name"):
        issues.append(ValidationIssue("missing-project-name", "project.name is required.", "project.name"))
    if not scenario_name:
        issues.append(ValidationIssue("missing-scenario-name", "scenario.name is required.", "scenario.name"))
    if scenario_kind not in SUPPORTED_TASKS:
        issues.append(ValidationIssue("unsupported-scenario-kind", f"scenario.kind must be one of {sorted(SUPPORTED_TASKS)}.", "scenario.kind"))
    if robot_template != "e-puck":
        issues.append(ValidationIssue("unsupported-robot-template", "robot.template must be 'e-puck'.", "robot.template"))
    if environment_template not in SUPPORTED_ENVIRONMENT_TEMPLATES:
        issues.append(
            ValidationIssue(
                "unsupported-environment-template",
                f"environment.template must be one of {sorted(SUPPORTED_ENVIRONMENT_TEMPLATES)}.",
                "environment.template",
            )
        )
    elif scenario_kind and scenario_kind not in SUPPORTED_ENVIRONMENT_TEMPLATES[environment_template]["allowed_kinds"]:
        issues.append(
            ValidationIssue(
                "unsupported-template-task-combination",
                f"environment.template '{environment_template}' does not support scenario.kind '{scenario_kind}'.",
                "environment.template",
            )
        )

    arena = spec.environment.get("arena") if isinstance(spec.environment.get("arena"), dict) else {}
    if not _is_positive_pair(arena.get("dimensions")):
        issues.append(
            ValidationIssue(
                "invalid-arena-dimensions",
                "environment.arena.dimensions must be a two-item list of positive numbers.",
                "environment.arena.dimensions",
            )
        )

    spawn = spec.layout.get("spawn") if isinstance(spec.layout.get("spawn"), dict) else {}
    if not _is_numeric_list(spawn.get("translation"), 3):
        issues.append(
            ValidationIssue(
                "invalid-spawn-translation",
                "layout.spawn.translation must be a three-item numeric list.",
                "layout.spawn.translation",
            )
        )

    if scenario_kind == "line-follow":
        line_track = spec.layout.get("line_track") if isinstance(spec.layout.get("line_track"), dict) else {}
        if not _is_point_list(line_track.get("points"), min_points=2):
            issues.append(
                ValidationIssue(
                    "invalid-line-track",
                    "layout.line_track.points must contain at least two XY points for line-follow scenarios.",
                    "layout.line_track.points",
                )
            )
        width = line_track.get("width")
        if not isinstance(width, (int, float)) or float(width) <= 0:
            issues.append(ValidationIssue("invalid-line-width", "layout.line_track.width must be a positive number.", "layout.line_track.width"))
    if scenario_kind == "waypoint-nav" and not _is_point_list(spec.layout.get("waypoints"), min_points=1):
        issues.append(ValidationIssue("missing-waypoints", "layout.waypoints must contain at least one waypoint.", "layout.waypoints"))
    if scenario_kind == "obstacle-avoidance":
        obstacles = spec.layout.get("obstacles")
        if not isinstance(obstacles, list) or not obstacles:
            issues.append(ValidationIssue("missing-obstacles", "layout.obstacles must contain at least one obstacle.", "layout.obstacles"))

    for index, obstacle in enumerate(spec.layout.get("obstacles", [])):
        if not isinstance(obstacle, dict):
            issues.append(ValidationIssue("invalid-obstacle", f"Obstacle #{index + 1} must be an object.", f"layout.obstacles[{index}]"))
            continue
        shape = obstacle.get("shape", "box")
        if shape not in {"box", "cylinder"}:
            issues.append(ValidationIssue("unsupported-obstacle-shape", "Obstacle shape must be 'box' or 'cylinder'.", f"layout.obstacles[{index}].shape"))
        if not _is_numeric_list(obstacle.get("position"), 2):
            issues.append(ValidationIssue("invalid-obstacle-position", "Obstacle position must be a two-item numeric list.", f"layout.obstacles[{index}].position"))

    if not _str_field(spec.controller, "path"):
        issues.append(ValidationIssue("missing-controller-path", "controller.path is required.", "controller.path"))
    if not isinstance(spec.benchmark.get("duration_s"), (int, float)) or float(spec.benchmark.get("duration_s", 0)) <= 0:
        issues.append(ValidationIssue("invalid-benchmark-duration", "benchmark.duration_s must be a positive number.", "benchmark.duration_s"))

    normalized.setdefault("scenario", {})
    normalized["scenario"]["benchmark_name"] = benchmark_name
    normalized.setdefault("controller", {})
    normalized["controller"]["scaffold_source"] = str(get_scenario(benchmark_name).controller) if benchmark_name else None
    return ScenarioValidationResult(str(spec_path), not issues, scenario_name, scenario_kind, environment_template, benchmark_name, issues, normalized)


def build_scenario(path: Path, *, force: bool = False) -> GeneratedScenario:
    report = validate_scenario(path)
    if not report.valid:
        raise KitError(
            "scenario-validation-failed",
            f"Scenario spec '{report.spec_path}' did not pass validation.",
            details={"issues": [issue.to_dict() for issue in report.issues]},
        )

    spec_path = Path(report.spec_path)
    spec = load_scenario_spec(spec_path)
    scenario_dir = spec_path.parent
    (scenario_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    world_path = scenario_dir / "worlds" / f"{spec.scenario['name']}.wbt"
    controller_name = Path(str(spec.controller["path"])).name
    controller_path = scenario_dir / "controllers" / controller_name
    benchmark_config_path = scenario_dir / BENCHMARK_CONFIG_FILENAME
    metadata_path = scenario_dir / GENERATED_METADATA_FILENAME

    if world_path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing world file: {world_path}")

    atomic_write_text(world_path, build_world_text(spec), encoding="utf-8")
    scaffold_controller(path=controller_path, scenario=report.benchmark_name or "waypoint-nav", force=force)

    benchmark_name = report.benchmark_name or "waypoint-nav"
    benchmark_profile = get_scenario(benchmark_name)
    suggested_session_command = (
        f"webots-kit session start --scenario {benchmark_name} --world \"{world_path}\" --controller \"{controller_path}\" "
        f"--robot-name {spec.robot['name']} --robot-def {spec.robot['def']} --mode fast --render off"
    )
    suggested_benchmark_command = (
        f"webots-kit benchmark run {benchmark_name} --controller \"{controller_path}\" --world \"{world_path}\" "
        f"--robot-name {spec.robot['name']} --robot-def {spec.robot['def']} --output \"{scenario_dir / 'artifacts' / 'report.json'}\" "
        f"--duration-s {spec.benchmark['duration_s']}"
    )

    benchmark_payload = {
        "scenario_name": spec.scenario["name"],
        "scenario_kind": spec.scenario["kind"],
        "benchmark_name": benchmark_name,
        "world_path": str(world_path),
        "controller_path": str(controller_path),
        "target_robot_name": spec.robot["name"],
        "target_robot_def": spec.robot["def"],
        "default_camera": spec.controller.get("default_camera", benchmark_profile.default_camera),
        "duration_s": spec.benchmark["duration_s"],
        "threshold_overrides": spec.benchmark.get("threshold_overrides", {}),
        "next_step": suggested_benchmark_command,
    }
    atomic_write_text(benchmark_config_path, json.dumps(benchmark_payload, indent=2), encoding="utf-8")

    generated = GeneratedScenario(
        spec_path=str(spec_path),
        project_root=str(_discover_project_root(scenario_dir)),
        scenario_dir=str(scenario_dir),
        scenario_name=str(spec.scenario["name"]),
        scenario_kind=str(spec.scenario["kind"]),
        benchmark_name=benchmark_name,
        world_path=str(world_path),
        controller_path=str(controller_path),
        benchmark_config_path=str(benchmark_config_path),
        target_robot_name=str(spec.robot["name"]),
        target_robot_def=str(spec.robot["def"]),
        default_camera=str(spec.controller.get("default_camera", benchmark_profile.default_camera)),
        suggested_session_command=suggested_session_command,
        suggested_benchmark_command=suggested_benchmark_command,
    )
    atomic_write_text(metadata_path, json.dumps(generated.to_dict(), indent=2), encoding="utf-8")
    return generated


def describe_scenario(path: Path) -> str:
    spec = load_scenario_spec(scenario_spec_path(path))
    report = validate_scenario(path)
    arena = spec.environment.get("arena", {})
    layout = spec.layout
    lines = [
        f"scenario: {spec.scenario.get('name')}",
        f"kind: {spec.scenario.get('kind')}",
        f"environment_template: {spec.environment.get('template')}",
        f"robot: {spec.robot.get('name')} ({spec.robot.get('template')})",
        f"arena_dimensions: {arena.get('dimensions')}",
        f"waypoints: {len(layout.get('waypoints', [])) if isinstance(layout.get('waypoints'), list) else 0}",
        f"obstacles: {len(layout.get('obstacles', [])) if isinstance(layout.get('obstacles'), list) else 0}",
        f"default_camera: {spec.controller.get('default_camera')}",
        f"benchmark_profile: {report.benchmark_name}",
        f"status: {'valid' if report.valid else 'invalid'}",
    ]
    if spec.scenario.get("kind") == "line-follow":
        line_track = layout.get("line_track", {})
        lines.append(f"line_points: {len(line_track.get('points', [])) if isinstance(line_track.get('points'), list) else 0}")
    return "\n".join(lines)


def scenario_doctor(path: Path) -> dict[str, Any]:
    spec_path = scenario_spec_path(path)
    report = validate_scenario(spec_path)
    if not spec_path.exists():
        return {
            "status": "blocked",
            "spec_path": str(spec_path),
            "scenario_name": None,
            "scenario_kind": None,
            "environment_template": None,
            "benchmark_name": None,
            "controller_scaffold_source": None,
            "controller_ready": False,
            "benchmark_ready": False,
            "mcp_ready": False,
            "issues": [issue.to_dict() for issue in report.issues],
            "support_tier": "experimental-foundation",
            "next_step": "Create a spec with `webots-kit scenario init <path> --template <template>`.",
        }
    spec = load_scenario_spec(spec_path)
    benchmark_name = report.benchmark_name
    next_step = f"Run `webots-kit scenario build \"{spec_path}\"` once the validation issues are fixed."
    if report.valid and benchmark_name:
        next_step = (
            f"Run `webots-kit scenario build \"{spec_path}\"` to generate the world and controller artifacts for `{benchmark_name}` smoke."
        )
    return {
        "status": "ready" if report.valid else "misconfigured",
        "spec_path": str(spec_path),
        "scenario_name": spec.scenario.get("name"),
        "scenario_kind": spec.scenario.get("kind"),
        "environment_template": spec.environment.get("template"),
        "benchmark_name": benchmark_name,
        "controller_scaffold_source": str(get_scenario(benchmark_name).controller) if benchmark_name else None,
        "controller_ready": bool(spec.controller.get("path")),
        "benchmark_ready": report.valid and benchmark_name is not None,
        "mcp_ready": report.valid,
        "issues": [issue.to_dict() for issue in report.issues],
        "support_tier": "experimental-foundation",
        "next_step": next_step,
    }


def import_project(*, world: Path, controller: Path, project_root: Path | None = None) -> dict[str, Any]:
    world_path = world if world.is_absolute() else (Path.cwd() / world).resolve()
    controller_path = controller if controller.is_absolute() else (Path.cwd() / controller).resolve()
    if not world_path.exists():
        raise FileNotFoundError(f"World file does not exist: {world_path}")
    if not controller_path.exists():
        raise FileNotFoundError(f"Controller file does not exist: {controller_path}")

    root = project_root if project_root else Path(os.path.commonpath([str(world_path.parent), str(controller_path.parent)]))
    root = root if root.is_absolute() else (Path.cwd() / root).resolve()
    manifest_path = project_manifest_path(root)
    if not manifest_path.exists():
        init_project(root, name=root.name, force=False)

    inferred_kind = infer_project_kind(world_path)
    scenario_name = f"imported-{world_path.stem}"
    scenario_dir = root / "scenarios" / scenario_name
    scenario_dir.mkdir(parents=True, exist_ok=True)
    spec_path = scenario_dir / SCENARIO_SPEC_FILENAME

    spec = _default_spec(_default_template_for_kind(inferred_kind), scenario_name, _load_project_manifest(root).project_name)
    spec.scenario["kind"] = inferred_kind
    spec.controller["path"] = str(controller_path)
    spec.import_source = {"world_path": str(world_path), "controller_path": str(controller_path)}
    spec.environment["imported"] = True
    atomic_write_text(spec_path, json.dumps(spec.to_dict(), indent=2), encoding="utf-8")
    return {
        "project_root": str(root),
        "manifest_path": str(manifest_path),
        "scenario_metadata_path": str(spec_path),
        "world_path": str(world_path),
        "controller_path": str(controller_path),
        "inferred_kind": inferred_kind,
        "support_tier": "experimental-foundation",
    }


def export_session(session_id: str, *, output: Path | None = None, store: SessionStore | None = None) -> SessionExport:
    session_store = store or SessionStore()
    session_store.load_manifest(session_id)
    export_root = output if output else (Path.cwd() / "artifacts" / "session-exports" / session_id)
    export_dir = export_root if export_root.is_absolute() else (Path.cwd() / export_root).resolve()
    export_dir.mkdir(parents=True, exist_ok=True)

    collect_runtime_diagnostics(output_dir=export_dir, session_id=session_id)
    logs_dir = export_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    copied_logs: list[str] = []
    for entry in session_store.log_inventory(session_id):
        if not entry["exists"]:
            continue
        source = Path(str(entry["path"]))
        destination = logs_dir / source.name
        shutil.copy2(source, destination)
        copied_logs.append(str(destination))

    copied_artifacts: list[str] = []
    artifacts_copy_dir = export_dir / "artifacts"
    artifacts_copy_dir.mkdir(exist_ok=True)
    for artifact in session_store.list_artifacts(session_id):
        source = Path(str(artifact["path"]))
        destination = artifacts_copy_dir / source.name
        if source.is_file():
            shutil.copy2(source, destination)
            copied_artifacts.append(str(destination))

    standard_artifacts = {name: str(export_dir / filename) for name, filename in SESSION_EXPORT_STANDARD_ARTIFACTS}
    payload = SessionExport(
        export_dir=str(export_dir),
        session_id=session_id,
        manifest_path=standard_artifacts["session"],
        inspect_path=standard_artifacts["inspect"],
        log_inventory_path=standard_artifacts["log_inventory"],
        log_summary_path=standard_artifacts["log_summary"],
        runtime_environment_path=standard_artifacts["runtime_environment"],
        doctor_path=standard_artifacts["doctor"],
        summary_path=standard_artifacts["summary"],
        export_manifest_path=standard_artifacts["export_manifest"],
        artifact_standard_version=SESSION_EXPORT_ARTIFACT_STANDARD_VERSION,
        replay_mode="observability",
        standard_artifacts=standard_artifacts,
        copied_logs=copied_logs,
        copied_artifacts=copied_artifacts,
    )
    atomic_write_text(export_dir / "export.json", json.dumps(payload.to_dict(), indent=2), encoding="utf-8")
    return payload


def replay_session(export_path: Path) -> dict[str, Any]:
    resolved_path = export_path if export_path.is_absolute() else (Path.cwd() / export_path).resolve()
    export_root = resolved_path.parent if resolved_path.is_file() else resolved_path
    export_manifest_path = resolved_path if resolved_path.is_file() else (export_root / "export.json")
    export_manifest = json.loads(export_manifest_path.read_text(encoding="utf-8")) if export_manifest_path.exists() else {}

    standard_artifacts = export_manifest.get("standard_artifacts") if isinstance(export_manifest.get("standard_artifacts"), dict) else {}
    if not standard_artifacts:
        standard_artifacts = {name: str(export_root / filename) for name, filename in SESSION_EXPORT_STANDARD_ARTIFACTS}
    summary_path = Path(str(export_manifest.get("summary_path") or standard_artifacts["summary"]))
    session_path = Path(str(export_manifest.get("manifest_path") or standard_artifacts["session"]))
    inspect_path = Path(str(export_manifest.get("inspect_path") or standard_artifacts["inspect"]))
    log_summary_path = Path(str(export_manifest.get("log_summary_path") or standard_artifacts["log_summary"]))
    runtime_environment_path = Path(
        str(export_manifest.get("runtime_environment_path") or standard_artifacts["runtime_environment"])
    )
    if not session_path.exists() and not summary_path.exists():
        raise FileNotFoundError(f"Session export was not found under {export_root}")

    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    session = json.loads(session_path.read_text(encoding="utf-8")) if session_path.exists() else {}
    inspect = json.loads(inspect_path.read_text(encoding="utf-8")) if inspect_path.exists() else {}
    log_summary = json.loads(log_summary_path.read_text(encoding="utf-8")) if log_summary_path.exists() else {}
    runtime_environment = json.loads(runtime_environment_path.read_text(encoding="utf-8")) if runtime_environment_path.exists() else {}
    session_state = inspect.get("session_state") if isinstance(inspect.get("session_state"), dict) else {}
    result_reason = session_state.get("last_error_code") or session_state.get("status") or "completed"
    benchmark_name = str(session.get("scenario") or "line-follower")
    copied_logs = export_manifest.get("copied_logs") if isinstance(export_manifest.get("copied_logs"), list) else None
    copied_artifacts = export_manifest.get("copied_artifacts") if isinstance(export_manifest.get("copied_artifacts"), list) else None
    runtime_summary = session.get("runtime_summary") if isinstance(session.get("runtime_summary"), dict) else {}
    return {
        "export_dir": str(export_root),
        "session_id": summary.get("session_id"),
        "scenario": session.get("scenario"),
        "status": session.get("status"),
        "artifact_standard_version": int(export_manifest.get("artifact_standard_version", SESSION_EXPORT_ARTIFACT_STANDARD_VERSION)),
        "replay_mode": str(export_manifest.get("replay_mode") or "observability"),
        "standard_artifacts": standard_artifacts,
        "session_state": session_state,
        "result_reason": result_reason,
        "last_error_code": session_state.get("last_error_code"),
        "last_error": session_state.get("last_error"),
        "runtime_summary": runtime_summary,
        "runtime_environment": summary.get("runtime_environment") if isinstance(summary.get("runtime_environment"), dict) else runtime_environment,
        "log_summary": log_summary if isinstance(log_summary, dict) else {},
        "copied_logs": sorted(Path(path).name for path in copied_logs) if copied_logs is not None else sorted(path.name for path in (export_root / "logs").glob("*")),
        "copied_artifacts": (
            sorted(Path(path).name for path in copied_artifacts)
            if copied_artifacts is not None
            else sorted(path.name for path in (export_root / "artifacts").glob("*"))
        ),
        "next_step": benchmark_next_step(benchmark_name, result_reason),
        "support_tier": "experimental-foundation",
    }


def infer_project_kind(world_path: Path) -> str:
    content = world_path.read_text(encoding="utf-8", errors="replace").lower()
    if "line follower" in content or "line_track" in content or "tri_color" in content:
        return "line-follow"
    if "woodenbox" in content or "obstacle" in content:
        return "obstacle-avoidance"
    if "waypoint" in content:
        return "waypoint-nav"
    return "waypoint-nav"


def build_world_text(spec: ScenarioSpec) -> str:
    kind = str(spec.scenario["kind"])
    if kind == "line-follow":
        return _build_line_follow_world(spec)
    return _build_arena_world(spec)


def format_scenario_validation_report(result: ScenarioValidationResult) -> str:
    lines = [
        f"scenario_validation: {'pass' if result.valid else 'fail'}",
        f"spec_path: {result.spec_path}",
        f"scenario_name: {result.scenario_name}",
        f"scenario_kind: {result.scenario_kind}",
        f"environment_template: {result.environment_template}",
        f"benchmark_name: {result.benchmark_name}",
        f"summary: {len(result.issues)} issues",
        "support_tier: experimental-foundation",
    ]
    if result.issues:
        lines.append("issues:")
        for issue in result.issues:
            location = f" [{issue.field}]" if issue.field else ""
            lines.append(f"- {issue.level}:{location} {issue.code} -> {issue.message}")
    lines.append(
        "next_step: "
        + (
            f"Run `webots-kit scenario build \"{result.spec_path}\"`."
            if result.valid
            else "Fix the listed scenario spec issues, then rerun `webots-kit scenario validate`."
        )
    )
    return "\n".join(lines)


def format_scenario_doctor_report(payload: dict[str, Any]) -> str:
    lines = [
        f"scenario_doctor: {payload['status']}",
        f"spec_path: {payload['spec_path']}",
        f"scenario_name: {payload['scenario_name']}",
        f"scenario_kind: {payload['scenario_kind']}",
        f"environment_template: {payload['environment_template']}",
        f"benchmark_name: {payload['benchmark_name']}",
        f"controller_ready: {payload['controller_ready']}",
        f"benchmark_ready: {payload['benchmark_ready']}",
        f"mcp_ready: {payload['mcp_ready']}",
        f"summary: {len(payload.get('issues', []))} issues",
        "support_tier: experimental-foundation",
    ]
    if payload.get("issues"):
        lines.append("issues:")
        for issue in payload["issues"]:
            lines.append(f"- {issue['code']}: {issue['message']}")
    lines.append(f"next_step: {payload['next_step']}")
    return "\n".join(lines)


def format_session_replay(payload: dict[str, Any]) -> str:
    runtime_environment = payload.get("runtime_environment") if isinstance(payload.get("runtime_environment"), dict) else {}
    runner_mode = runtime_environment.get("runner_mode")
    if isinstance(runner_mode, dict):
        runner_mode_text = runner_mode.get("mode")
    else:
        runner_mode_text = runner_mode
    lines = [
        f"session_replay: {payload['status']}",
        f"session_id: {payload['session_id']}",
        f"scenario: {payload['scenario']}",
        f"replay_mode: {payload.get('replay_mode')}",
        f"artifact_standard_version: {payload.get('artifact_standard_version')}",
        f"session_state_status: {payload.get('session_state', {}).get('status')}",
        f"result_reason: {payload.get('result_reason')}",
        f"last_error_code: {payload['last_error_code']}",
        f"last_error: {payload['last_error']}",
        f"runtime_runner_mode: {runner_mode_text}",
        f"runtime_python: {runtime_environment.get('python_executable')}",
        f"copied_logs: {payload['copied_logs']}",
        f"copied_artifacts: {payload['copied_artifacts']}",
        f"standard_artifacts: {sorted(payload.get('standard_artifacts', {}))}",
        f"summary: {len(payload['copied_logs'])} logs, {len(payload['copied_artifacts'])} artifacts",
        "support_tier: experimental-foundation",
        f"next_step: {payload['next_step']}",
    ]
    return "\n".join(lines)


def _build_line_follow_world(spec: ScenarioSpec) -> str:
    arena_dimensions = spec.environment["arena"]["dimensions"]
    spawn = spec.layout["spawn"]
    segments = _line_track_segments(spec.layout["line_track"]["points"])
    segment_nodes: list[str] = []
    for index, segment in enumerate(segments, start=1):
        segment_nodes.append(
            f"""Solid {{
  translation {_fmt(segment['x'])} {_fmt(segment['y'])} 0.001
  rotation 0 0 1 {_fmt(segment['rotation'])}
  children [
    DEF LINE_SEGMENT_{index} Shape {{
      appearance PBRAppearance {{
        baseColor 0 0 0
        roughness 1
        metalness 0
      }}
      geometry Box {{
        size {_fmt(segment['length'])} {_fmt(spec.layout['line_track']['width'])} 0.002
      }}
    }}
  ]
  name "line-segment-{index}"
  locked TRUE
}}"""
        )
    return _world_shell(
        title=f"{spec.project['name']} {spec.scenario['name']}",
        info_lines=["Generated by webots-kit scenario build.", "Template-driven line-follow scenario."],
        arena_size=arena_dimensions,
        body="\n".join(segment_nodes),
        robot_block=_robot_block(robot_name=str(spec.robot["name"]), spawn=spawn, camera_mode=True),
    )


def _build_arena_world(spec: ScenarioSpec) -> str:
    arena_dimensions = spec.environment["arena"]["dimensions"]
    spawn = spec.layout["spawn"]
    body_nodes: list[str] = []
    for index, obstacle in enumerate(spec.layout.get("obstacles", []), start=1):
        body_nodes.append(_obstacle_block(index, obstacle))
    if spec.scenario["kind"] == "waypoint-nav":
        goal = spec.layout.get("goal_region") or {"center": spec.layout["waypoints"][-1], "radius": 0.16}
        body_nodes.append(_goal_block(goal))
    return _world_shell(
        title=f"{spec.project['name']} {spec.scenario['name']}",
        info_lines=["Generated by webots-kit scenario build.", f"Template-driven {spec.scenario['kind']} scenario."],
        arena_size=arena_dimensions,
        body="\n".join(body_nodes),
        robot_block=_robot_block(robot_name=str(spec.robot["name"]), spawn=spawn, camera_mode=False),
    )


def _world_shell(*, title: str, info_lines: list[str], arena_size: list[float], body: str, robot_block: str) -> str:
    info = "\n".join(f'    "{line}"' for line in info_lines)
    supervisor_y = -max(float(arena_size[1]) / 2 - 0.05, 0.95)
    robot_name = robot_block.split('name "')[1].split('"', 1)[0]
    return f"""#VRML_SIM R2025a utf8

EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/backgrounds/protos/TexturedBackground.proto"
EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/backgrounds/protos/TexturedBackgroundLight.proto"
EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/floors/protos/RectangleArena.proto"
EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/robots/gctronic/e-puck/protos/E-puck.proto"

WorldInfo {{
  info [
{info}
  ]
  title "{title}"
}}
Viewpoint {{
  orientation -0.23377742247284416 -0.14462426941825353 0.9614536434507968 4.02642814535917
  position 0.31650922270931994 0.2246304652876164 0.30312892921312386
  follow "{robot_name}"
}}
TexturedBackground {{
}}
TexturedBackgroundLight {{
}}
RectangleArena {{
  floorSize {_fmt(arena_size[0])} {_fmt(arena_size[1])}
}}
{body}
{robot_block}
Robot {{
  translation 0 {_fmt(supervisor_y)} 0.03
  name "kit-supervisor"
  controller "<extern>"
  supervisor TRUE
}}
"""


def _robot_block(*, robot_name: str, spawn: dict[str, Any], camera_mode: bool) -> str:
    translation = spawn["translation"]
    rotation = float(spawn.get("rotation_z", 0.0))
    camera_settings = ""
    if camera_mode:
        camera_settings = "\n  camera_width 40\n  camera_height 1\n  camera_rotation 0 1 0 0.47"
    return (
        "DEF EPUCK E-puck {\n"
        f"  translation {_fmt(translation[0])} {_fmt(translation[1])} {_fmt(translation[2])}\n"
        f"  rotation 0 0 1 {_fmt(rotation)}\n"
        f"  name \"{robot_name}\"\n"
        "  controller \"<extern>\""
        f"{camera_settings}\n"
        "}"
    )


def _obstacle_block(index: int, obstacle: dict[str, Any]) -> str:
    x, y = obstacle["position"]
    rotation = float(obstacle.get("rotation_z", 0.0))
    shape = obstacle.get("shape", "box")
    if shape == "cylinder":
        radius = float(obstacle.get("radius", 0.06))
        height = float(obstacle.get("height", 0.12))
        geometry = f"Cylinder {{ height {_fmt(height)} radius {_fmt(radius)} }}"
        z = height / 2
    else:
        size = obstacle.get("size", [0.1, 0.1, 0.1])
        geometry = f"Box {{ size {_fmt(size[0])} {_fmt(size[1])} {_fmt(size[2])} }}"
        z = float(size[2]) / 2
    return f"""Solid {{
  translation {_fmt(x)} {_fmt(y)} {_fmt(z)}
  rotation 0 0 1 {_fmt(rotation)}
  children [
    DEF OBSTACLE_{index} Shape {{
      appearance PBRAppearance {{
        baseColor 0.59 0.4 0.24
        roughness 1
        metalness 0
      }}
      geometry {geometry}
    }}
  ]
  name "obstacle-{index}"
  boundingObject USE OBSTACLE_{index}
}}"""


def _goal_block(goal: dict[str, Any]) -> str:
    center = goal.get("center", [0.55, 0.0])
    radius = float(goal.get("radius", 0.16))
    return f"""Solid {{
  translation {_fmt(center[0])} {_fmt(center[1])} 0.001
  children [
    Shape {{
      appearance PBRAppearance {{
        baseColor 0.08 0.7 0.38
        transparency 0.35
        roughness 1
        metalness 0
      }}
      geometry Cylinder {{
        height 0.002
        radius {_fmt(radius)}
      }}
    }}
  ]
  name "goal-region"
  locked TRUE
}}"""


def _line_track_segments(points: list[list[float]]) -> list[dict[str, float]]:
    segments: list[dict[str, float]] = []
    for start, end in zip(points, points[1:]):
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
        length = math.hypot(dx, dy)
        if length <= 0:
            continue
        segments.append(
            {
                "x": (float(start[0]) + float(end[0])) / 2,
                "y": (float(start[1]) + float(end[1])) / 2,
                "length": length,
                "rotation": math.atan2(dy, dx),
            }
        )
    return segments


def _default_spec(template: str, scenario_name: str, project_name: str) -> ScenarioSpec:
    default_kind = SUPPORTED_ENVIRONMENT_TEMPLATES[template]["default_kind"]
    benchmark_name = SUPPORTED_TASKS[default_kind]
    scenario = get_scenario(benchmark_name)
    defaults = {
        "epuck-line-track": {
            "arena": {"dimensions": [1.8, 1.2], "floor": "plain"},
            "layout": {
                "spawn": {"translation": [-0.7, 0.03, 0.0], "rotation_z": 0.0},
                "line_track": {"width": 0.06, "points": [[-0.75, 0.03], [-0.2, 0.03], [-0.2, 0.42], [0.55, 0.42], [0.55, -0.2]]},
                "obstacles": [],
                "waypoints": [],
            },
        },
        "epuck-waypoint": {
            "arena": {"dimensions": [2.0, 2.0], "floor": "plain"},
            "layout": {
                "spawn": {"translation": [-0.65, 0.0, 0.0], "rotation_z": 0.0},
                "obstacles": [],
                "waypoints": [[0.55, 0.0]],
                "goal_region": {"center": [0.55, 0.0], "radius": 0.16},
            },
        },
        "epuck-arena": {
            "arena": {"dimensions": [2.0, 2.0], "floor": "plain"},
            "layout": {
                "spawn": {"translation": [-0.55, 0.0, 0.0], "rotation_z": 0.0},
                "obstacles": [],
                "waypoints": [[0.4, 0.0]],
                "goal_region": {"center": [0.4, 0.0], "radius": 0.16},
            },
        },
        "epuck-obstacle-course": {
            "arena": {"dimensions": [2.0, 2.0], "floor": "plain"},
            "layout": {
                "spawn": {"translation": [0.0, 0.0, 0.0], "rotation_z": 1.57},
                "obstacles": [
                    {"shape": "box", "position": [-0.68, 0.2], "size": [0.1, 0.1, 0.1], "rotation_z": 0.5},
                    {"shape": "box", "position": [0.35, 0.75], "size": [0.1, 0.1, 0.1], "rotation_z": 4.96782},
                    {"shape": "box", "position": [-0.35, -0.5], "size": [0.1, 0.1, 0.1], "rotation_z": 5.36782},
                ],
                "waypoints": [],
            },
        },
    }[template]
    return ScenarioSpec(
        schema_version=1,
        project={"name": project_name},
        scenario={"name": scenario_name, "kind": default_kind},
        robot={"template": "e-puck", "name": _default_robot_name(default_kind, scenario_name), "def": "EPUCK"},
        environment={"template": template, "arena": defaults["arena"]},
        layout=defaults["layout"],
        task={"kind": default_kind, "description": f"Generated {default_kind} task."},
        controller={"path": f"controllers/{scenario_name}_agent.py", "default_camera": scenario.default_camera},
        benchmark={"profile": benchmark_name, "duration_s": 20.0, "threshold_overrides": {}},
        sensors={"required": list(scenario.required_sensor_keys)},
        actuators={"required": list(scenario.required_actuator_keys)},
    )


def _default_robot_name(kind: str, scenario_name: str) -> str:
    return f"epuck-{scenario_name}-{kind}"


def _default_template_for_kind(kind: str) -> str:
    return {
        "line-follow": "epuck-line-track",
        "waypoint-nav": "epuck-waypoint",
        "obstacle-avoidance": "epuck-obstacle-course",
    }[kind]


def _discover_project_root(path: Path) -> Path:
    current = path.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / PROJECT_MANIFEST_FILENAME).exists():
            return candidate
        if candidate.name == "scenarios":
            return candidate.parent
    return current if current.is_dir() else current.parent


def _load_project_manifest(project_root: Path) -> ProjectManifest:
    manifest_path = project_manifest_path(project_root)
    if not manifest_path.exists():
        init_project(project_root, name=project_root.name, force=False)
    return ProjectManifest(**json.loads(manifest_path.read_text(encoding="utf-8")))


def _str_field(payload: dict[str, Any], name: str) -> str | None:
    value = payload.get(name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _is_positive_pair(value: Any) -> bool:
    return _is_numeric_list(value, 2) and all(float(item) > 0 for item in value)


def _is_numeric_list(value: Any, length: int) -> bool:
    return isinstance(value, list) and len(value) == length and all(isinstance(item, (int, float)) for item in value)


def _is_point_list(value: Any, *, min_points: int) -> bool:
    return isinstance(value, list) and len(value) >= min_points and all(_is_numeric_list(item, 2) for item in value)


def _fmt(value: float | int) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".")
