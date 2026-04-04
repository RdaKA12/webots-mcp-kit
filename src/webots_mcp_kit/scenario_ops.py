from __future__ import annotations

import ast
import json
import math
import os
import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import __version__
from .benchmark import benchmark_next_step, controller_fix_hints
from .benchmarks import get_scenario, scenario_registry
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
from .robot_profiles import get_robot_profile, robot_profile_from_template
from .session_store import SessionStore
from .utils import atomic_write_text, utc_now_iso
from .world_ops import inspect_world

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
    "epuck-arena": {"default_kind": "waypoint-nav", "allowed_kinds": {"waypoint-nav", "obstacle-avoidance"}, "robot_profile": "e-puck"},
    "epuck-line-track": {"default_kind": "line-follow", "allowed_kinds": {"line-follow"}, "robot_profile": "e-puck"},
    "epuck-waypoint": {"default_kind": "waypoint-nav", "allowed_kinds": {"waypoint-nav"}, "robot_profile": "e-puck"},
    "epuck-obstacle-course": {"default_kind": "obstacle-avoidance", "allowed_kinds": {"obstacle-avoidance", "waypoint-nav"}, "robot_profile": "e-puck"},
    "monsterborg-line-track": {"default_kind": "line-follow", "allowed_kinds": {"line-follow"}, "robot_profile": "monsterborg-4wd"},
    "monsterborg-waypoint": {"default_kind": "waypoint-nav", "allowed_kinds": {"waypoint-nav"}, "robot_profile": "monsterborg-4wd"},
    "monsterborg-obstacle-course": {"default_kind": "obstacle-avoidance", "allowed_kinds": {"obstacle-avoidance", "waypoint-nav"}, "robot_profile": "monsterborg-4wd"},
}

SUPPORTED_ARENA_FLOORS: dict[str, dict[str, Any]] = {
    "plain": {"base_color": (0.82, 0.82, 0.82), "grid": False},
    "light": {"base_color": (0.9, 0.9, 0.88), "grid": False},
    "dark": {"base_color": (0.28, 0.28, 0.3), "grid": False},
    "grid": {"base_color": (0.86, 0.86, 0.84), "grid": True},
}

ROBOT_CLEARANCE_RADIUS = 0.045


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
    spec = ScenarioSpec.from_dict(payload)
    _apply_scenario_defaults(spec)
    return spec


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
    robot_profile = robot_profile_from_template(robot_template)
    environment_template = _str_field(spec.environment, "template")
    benchmark_name = SUPPORTED_TASKS.get(scenario_kind)
    scenario_def = get_scenario(benchmark_name, robot_profile=robot_profile) if benchmark_name else None

    if spec.schema_version != 1:
        issues.append(ValidationIssue("unsupported-scenario-schema", f"Unsupported schema version '{spec.schema_version}'.", "schema_version"))
    if not _str_field(spec.project, "name"):
        issues.append(ValidationIssue("missing-project-name", "project.name is required.", "project.name"))
    if not scenario_name:
        issues.append(ValidationIssue("missing-scenario-name", "scenario.name is required.", "scenario.name"))
    if scenario_kind not in SUPPORTED_TASKS:
        issues.append(ValidationIssue("unsupported-scenario-kind", f"scenario.kind must be one of {sorted(SUPPORTED_TASKS)}.", "scenario.kind"))
    if not robot_template:
        issues.append(ValidationIssue("missing-robot-template", "robot.template is required.", "robot.template"))
    else:
        try:
            get_robot_profile(robot_template)
        except KeyError:
            issues.append(ValidationIssue("unsupported-robot-template", f"robot.template must be one of {['e-puck', 'monsterborg-4wd']}.", "robot.template"))
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
    elif robot_template and SUPPORTED_ENVIRONMENT_TEMPLATES[environment_template]["robot_profile"] != robot_profile:
        issues.append(
            ValidationIssue(
                "unsupported-template-robot-combination",
                f"environment.template '{environment_template}' requires robot.template '{SUPPORTED_ENVIRONMENT_TEMPLATES[environment_template]['robot_profile']}'.",
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
    floor = _str_field(arena, "floor") or "plain"
    if floor not in SUPPORTED_ARENA_FLOORS:
        issues.append(
            ValidationIssue(
                "unsupported-arena-floor",
                f"environment.arena.floor must be one of {sorted(SUPPORTED_ARENA_FLOORS)}.",
                "environment.arena.floor",
            )
        )
    elif scenario_kind == "line-follow" and floor == "dark":
        issues.append(
            ValidationIssue(
                "unsupported-floor-task-combination",
                "line-follow scenarios require a non-dark arena floor so the generated line stays visible.",
                "environment.arena.floor",
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
        else:
            for index, (start, end) in enumerate(zip(line_track.get("points", []), line_track.get("points", [])[1:]), start=1):
                if float(start[0]) == float(end[0]) and float(start[1]) == float(end[1]):
                    issues.append(
                        ValidationIssue(
                            "degenerate-line-segment",
                            f"layout.line_track.points contains a zero-length segment at index {index}.",
                            "layout.line_track.points",
                        )
                    )
            if _is_positive_pair(arena.get("dimensions")):
                half_width = float(arena["dimensions"][0]) / 2
                half_height = float(arena["dimensions"][1]) / 2
                for index, point in enumerate(line_track.get("points", [])):
                    if abs(float(point[0])) > half_width or abs(float(point[1])) > half_height:
                        issues.append(
                            ValidationIssue(
                                "line-track-point-out-of-bounds",
                                f"layout.line_track.points[{index}] must stay inside the declared arena dimensions.",
                                "layout.line_track.points",
                            )
                        )
                if float(width) >= min(float(arena["dimensions"][0]), float(arena["dimensions"][1])) / 2:
                    issues.append(
                        ValidationIssue(
                            "line-track-width-too-large",
                            "layout.line_track.width is too large relative to environment.arena.dimensions.",
                            "layout.line_track.width",
                        )
                    )
    if scenario_kind == "waypoint-nav" and not _is_point_list(spec.layout.get("waypoints"), min_points=1):
        issues.append(ValidationIssue("missing-waypoints", "layout.waypoints must contain at least one waypoint.", "layout.waypoints"))
    if scenario_kind == "waypoint-nav":
        goal_region = spec.layout.get("goal_region") if isinstance(spec.layout.get("goal_region"), dict) else {}
        goal_center = goal_region.get("center")
        goal_radius = goal_region.get("radius")
        if not _is_numeric_list(goal_center, 2):
            issues.append(ValidationIssue("invalid-goal-region-center", "layout.goal_region.center must be a two-item numeric list.", "layout.goal_region.center"))
        if not isinstance(goal_radius, (int, float)) or float(goal_radius) <= 0:
            issues.append(ValidationIssue("invalid-goal-region-radius", "layout.goal_region.radius must be a positive number.", "layout.goal_region.radius"))
        waypoints = spec.layout.get("waypoints", [])
        if _is_numeric_list(goal_center, 2) and _is_point_list(waypoints, min_points=1):
            if _distance_2d(goal_center, waypoints[-1]) > 0.05:
                issues.append(
                    ValidationIssue(
                        "goal-region-waypoint-mismatch",
                        "layout.goal_region.center must stay aligned with the final waypoint for waypoint-nav scenarios.",
                        "layout.goal_region.center",
                    )
                )
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
        if shape == "box":
            size = obstacle.get("size")
            if not _is_numeric_list(size, 3) or any(float(item) <= 0 for item in size):
                issues.append(ValidationIssue("invalid-obstacle-size", "Box obstacles must define a three-item positive size list.", f"layout.obstacles[{index}].size"))
            if "radius" in obstacle or "height" in obstacle:
                issues.append(
                    ValidationIssue(
                        "obstacle-shape-field-mismatch",
                        "Box obstacles must not define cylinder-only radius or height fields.",
                        f"layout.obstacles[{index}]",
                    )
                )
        if shape == "cylinder":
            radius = obstacle.get("radius")
            height = obstacle.get("height")
            if not isinstance(radius, (int, float)) or float(radius) <= 0:
                issues.append(ValidationIssue("invalid-obstacle-radius", "Cylinder obstacles must define a positive radius.", f"layout.obstacles[{index}].radius"))
            if not isinstance(height, (int, float)) or float(height) <= 0:
                issues.append(ValidationIssue("invalid-obstacle-height", "Cylinder obstacles must define a positive height.", f"layout.obstacles[{index}].height"))
            if "size" in obstacle:
                issues.append(
                    ValidationIssue(
                        "obstacle-shape-field-mismatch",
                        "Cylinder obstacles must not define box-only size fields.",
                        f"layout.obstacles[{index}]",
                    )
                )

    for index, wall in enumerate(spec.layout.get("walls", [])):
        if not isinstance(wall, dict):
            issues.append(ValidationIssue("invalid-wall", f"Wall #{index + 1} must be an object.", f"layout.walls[{index}]"))
            continue
        if not _is_numeric_list(wall.get("start"), 2) or not _is_numeric_list(wall.get("end"), 2):
            issues.append(ValidationIssue("invalid-wall-segment", "Walls must define start and end XY points.", f"layout.walls[{index}]"))
        thickness = wall.get("thickness", 0.02)
        height = wall.get("height", 0.08)
        if not isinstance(thickness, (int, float)) or float(thickness) <= 0:
            issues.append(ValidationIssue("invalid-wall-thickness", "Walls must define a positive thickness.", f"layout.walls[{index}].thickness"))
        if not isinstance(height, (int, float)) or float(height) <= 0:
            issues.append(ValidationIssue("invalid-wall-height", "Walls must define a positive height.", f"layout.walls[{index}].height"))

    for index, landmark in enumerate(spec.layout.get("landmarks", [])):
        if not isinstance(landmark, dict):
            issues.append(ValidationIssue("invalid-landmark", f"Landmark #{index + 1} must be an object.", f"layout.landmarks[{index}]"))
            continue
        if not _is_numeric_list(landmark.get("position"), 2):
            issues.append(ValidationIssue("invalid-landmark-position", "Landmarks must define XY positions.", f"layout.landmarks[{index}].position"))
        radius = landmark.get("radius", 0.04)
        if not isinstance(radius, (int, float)) or float(radius) <= 0:
            issues.append(ValidationIssue("invalid-landmark-radius", "Landmarks must define a positive radius.", f"layout.landmarks[{index}].radius"))

    for index, zone in enumerate(spec.layout.get("zones", [])):
        if not isinstance(zone, dict):
            issues.append(ValidationIssue("invalid-zone", f"Zone #{index + 1} must be an object.", f"layout.zones[{index}]"))
            continue
        if not _is_numeric_list(zone.get("center"), 2):
            issues.append(ValidationIssue("invalid-zone-center", "Zones must define XY centers.", f"layout.zones[{index}].center"))
        if not _is_numeric_list(zone.get("size"), 2):
            issues.append(ValidationIssue("invalid-zone-size", "Zones must define a two-item XY size.", f"layout.zones[{index}].size"))

    for index, prop in enumerate(spec.layout.get("props", [])):
        if not isinstance(prop, dict):
            issues.append(ValidationIssue("invalid-prop", f"Prop #{index + 1} must be an object.", f"layout.props[{index}]"))
            continue
        if not _is_numeric_list(prop.get("position"), 2):
            issues.append(ValidationIssue("invalid-prop-position", "Props must define XY positions.", f"layout.props[{index}].position"))
        size = prop.get("size", [0.08, 0.08, 0.08])
        if not _is_numeric_list(size, 3) or any(float(item) <= 0 for item in size):
            issues.append(ValidationIssue("invalid-prop-size", "Props must define a positive three-item size list.", f"layout.props[{index}].size"))

    issues.extend(_validate_layout_geometry(spec))

    if not _str_field(spec.controller, "path"):
        issues.append(ValidationIssue("missing-controller-path", "controller.path is required.", "controller.path"))
    if scenario_def and scenario_def.default_camera and not _str_field(spec.controller, "default_camera"):
        issues.append(
            ValidationIssue(
                "missing-default-camera",
                f"controller.default_camera is required for benchmark profile '{scenario_def.name}'.",
                "controller.default_camera",
            )
        )
    benchmark_profile = _str_field(spec.benchmark, "profile")
    if benchmark_name and benchmark_profile != benchmark_name:
        issues.append(
            ValidationIssue(
                "benchmark-profile-mismatch",
                f"benchmark.profile must be '{benchmark_name}' for scenario.kind '{scenario_kind}'.",
                "benchmark.profile",
            )
        )
    if not isinstance(spec.benchmark.get("duration_s"), (int, float)) or float(spec.benchmark.get("duration_s", 0)) <= 0:
        issues.append(ValidationIssue("invalid-benchmark-duration", "benchmark.duration_s must be a positive number.", "benchmark.duration_s"))
    if scenario_def:
        sensors_required = spec.sensors.get("required") if isinstance(spec.sensors.get("required"), list) else []
        actuators_required = spec.actuators.get("required") if isinstance(spec.actuators.get("required"), list) else []
        missing_sensor_contract = sorted(set(scenario_def.required_sensor_keys) - {str(item) for item in sensors_required})
        missing_actuator_contract = sorted(set(scenario_def.required_actuator_keys) - {str(item) for item in actuators_required})
        if missing_sensor_contract:
            issues.append(
                ValidationIssue(
                    "missing-required-sensor-contract",
                    f"sensors.required is missing benchmark-required keys: {missing_sensor_contract}.",
                    "sensors.required",
                )
            )
        if missing_actuator_contract:
            issues.append(
                ValidationIssue(
                    "missing-required-actuator-contract",
                    f"actuators.required is missing benchmark-required keys: {missing_actuator_contract}.",
                    "actuators.required",
                )
            )

    normalized.setdefault("scenario", {})
    normalized["scenario"]["benchmark_name"] = benchmark_name
    normalized.setdefault("controller", {})
    normalized["controller"]["scaffold_source"] = (
        str(get_scenario(benchmark_name, robot_profile=robot_profile).controller) if benchmark_name else None
    )
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
    robot_profile = robot_profile_from_template(str(spec.robot.get("template") or "e-puck"))
    profile = get_robot_profile(robot_profile)
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
    controller_language = "cpp" if controller_path.suffix.lower() in {".cpp", ".cc", ".cxx"} else "python"
    scaffold_controller(
        path=controller_path,
        scenario=report.benchmark_name or "waypoint-nav",
        force=force,
        language=controller_language,
        robot_profile=profile.robot_profile,
    )
    world_inventory = inspect_world(world_path)

    benchmark_name = report.benchmark_name or "waypoint-nav"
    benchmark_profile = get_scenario(benchmark_name, robot_profile=profile.robot_profile)
    suggested_session_command = (
        f"webots-kit session start --scenario {benchmark_name} --world \"{world_path}\" --controller \"{controller_path}\" "
        f"--robot-profile {profile.robot_profile} --robot-name {spec.robot['name']} --robot-def {spec.robot['def']} --mode fast --render off"
    )
    suggested_benchmark_command = (
        f"webots-kit benchmark run {benchmark_name} --controller \"{controller_path}\" --world \"{world_path}\" "
        f"--robot-profile {profile.robot_profile} --robot-name {spec.robot['name']} --robot-def {spec.robot['def']} --output \"{scenario_dir / 'artifacts' / 'report.json'}\" "
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
        "robot_family": profile.robot_family,
        "robot_profile": profile.robot_profile,
        "runtime_target": "interactive-webots",
        "default_camera": spec.controller.get("default_camera", benchmark_profile.default_camera),
        "duration_s": spec.benchmark["duration_s"],
        "threshold_overrides": spec.benchmark.get("threshold_overrides", {}),
        "arena_floor": spec.environment.get("arena", {}).get("floor"),
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
        robot_family=profile.robot_family,
        robot_profile=profile.robot_profile,
        runtime_target="interactive-webots",
        default_camera=str(spec.controller.get("default_camera", benchmark_profile.default_camera)),
        suggested_session_command=suggested_session_command,
        suggested_benchmark_command=suggested_benchmark_command,
        world_inventory_summary=world_inventory.get("spatial_summary", {}),
        world_authoring_context={
            "supported_layout_fields": ["spawn", "line_track", "waypoints", "goal_region", "obstacles", "walls", "landmarks", "zones", "props"],
            "recommended_next_edit_ops": _recommended_next_edit_ops(spec),
            "supported_edit_targets": world_inventory.get("supported_edit_targets", []),
            "layout_counts": {
                "obstacles": len(spec.layout.get("obstacles", [])) if isinstance(spec.layout.get("obstacles"), list) else 0,
                "walls": len(spec.layout.get("walls", [])) if isinstance(spec.layout.get("walls"), list) else 0,
                "landmarks": len(spec.layout.get("landmarks", [])) if isinstance(spec.layout.get("landmarks"), list) else 0,
                "zones": len(spec.layout.get("zones", [])) if isinstance(spec.layout.get("zones"), list) else 0,
                "props": len(spec.layout.get("props", [])) if isinstance(spec.layout.get("props"), list) else 0,
            },
        },
        benchmark_mapping=_benchmark_mapping(spec, benchmark_name, benchmark_profile),
    )
    metadata_payload = {
        **generated.to_dict(),
        "supported_edit_targets": world_inventory["supported_edit_targets"],
        "recommended_next_edit_ops": generated.world_authoring_context.get("recommended_next_edit_ops", []),
        "support_tier": "experimental-foundation",
    }
    atomic_write_text(metadata_path, json.dumps(metadata_payload, indent=2), encoding="utf-8")
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
        f"arena_floor: {arena.get('floor')}",
        f"waypoints: {len(layout.get('waypoints', [])) if isinstance(layout.get('waypoints'), list) else 0}",
        f"obstacles: {len(layout.get('obstacles', [])) if isinstance(layout.get('obstacles'), list) else 0}",
        f"walls: {len(layout.get('walls', [])) if isinstance(layout.get('walls'), list) else 0}",
        f"landmarks: {len(layout.get('landmarks', [])) if isinstance(layout.get('landmarks'), list) else 0}",
        f"zones: {len(layout.get('zones', [])) if isinstance(layout.get('zones'), list) else 0}",
        f"props: {len(layout.get('props', [])) if isinstance(layout.get('props'), list) else 0}",
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
            "benchmark_readiness": {"ready": False, "benchmark_name": None, "profile": None, "issues": [issue.code for issue in report.issues]},
            "unsupported_combinations": [issue.to_dict() for issue in report.issues if "unsupported" in issue.code],
            "controller_contract_readiness": {"ready": False, "default_camera": None, "required_sensors": [], "required_actuators": [], "issues": [issue.code for issue in report.issues]},
            "controller_authoring_readiness": {"ready": False, "controller_path": None, "default_camera": None, "scaffold_source": None, "issues": [issue.code for issue in report.issues]},
            "build_readiness": {"ready": False, "issues": [issue.code for issue in report.issues]},
            "runtime_smoke_readiness": {"ready": False, "requires_interactive_runner": True, "benchmark_name": None},
            "benchmark_mapping_readiness": {"ready": False, "benchmark_name": None, "target_robot_name": None, "target_robot_def": None, "expected_sensor_keys": [], "expected_metric_keys": [], "expected_actuator_keys": [], "issues": [issue.code for issue in report.issues]},
            "world_authoring_readiness": {"ready": False, "supported_edit_targets": ["spawn", "obstacles", "walls", "landmarks", "zones", "props"], "counts": {"obstacles": 0, "walls": 0, "landmarks": 0, "zones": 0, "props": 0}, "recommended_next_edit_ops": []},
            "issues": [issue.to_dict() for issue in report.issues],
            "support_tier": "experimental-foundation",
            "next_step": "Create a spec with `webots-kit scenario init <path> --template <template>`.",
        }
    spec = load_scenario_spec(spec_path)
    robot_profile = robot_profile_from_template(str(spec.robot.get("template") or "e-puck"))
    benchmark_name = report.benchmark_name
    benchmark_profile = spec.benchmark.get("profile") if isinstance(spec.benchmark, dict) else None
    scenario_def = get_scenario(benchmark_name, robot_profile=robot_profile) if benchmark_name else None
    unsupported_combinations = [
        issue.to_dict()
        for issue in report.issues
        if issue.code.startswith("unsupported-") or issue.code.endswith("-mismatch")
    ]
    benchmark_readiness = {
        "ready": report.valid and benchmark_name is not None,
        "benchmark_name": benchmark_name,
        "profile": benchmark_profile,
        "duration_s": spec.benchmark.get("duration_s"),
        "threshold_override_count": len(spec.benchmark.get("threshold_overrides", {})) if isinstance(spec.benchmark.get("threshold_overrides"), dict) else 0,
        "issues": [issue.code for issue in report.issues if issue.field and issue.field.startswith("benchmark")],
    }
    controller_contract_readiness = {
        "ready": bool(spec.controller.get("path")) and not any(issue.code.startswith("missing-required-") or issue.code == "missing-default-camera" for issue in report.issues),
        "default_camera": spec.controller.get("default_camera"),
        "required_sensors": list(spec.sensors.get("required", [])) if isinstance(spec.sensors.get("required"), list) else [],
        "required_actuators": list(spec.actuators.get("required", [])) if isinstance(spec.actuators.get("required"), list) else [],
        "expected_sensor_keys": list(scenario_def.required_sensor_keys) if scenario_def else [],
        "expected_actuator_keys": list(scenario_def.required_actuator_keys) if scenario_def else [],
        "issues": [issue.code for issue in report.issues if issue.field in {"controller.default_camera", "sensors.required", "actuators.required"}],
    }
    build_readiness = {
        "ready": report.valid,
        "world_output_path": str(spec_path.parent / "worlds" / f"{spec.scenario.get('name')}.wbt"),
        "controller_output_path": str(spec_path.parent / "controllers" / Path(str(spec.controller.get("path"))).name),
        "issues": [issue.code for issue in report.issues],
    }
    runtime_smoke_readiness = {
        "ready": report.valid and benchmark_name is not None,
        "requires_interactive_runner": True,
        "benchmark_name": benchmark_name,
        "recommended_mode": "fast",
        "recommended_render": "off",
    }
    controller_authoring_readiness = {
        "ready": controller_contract_readiness["ready"],
        "controller_path": spec.controller.get("path"),
        "default_camera": spec.controller.get("default_camera"),
        "scaffold_source": str(scenario_def.controller) if scenario_def else None,
        "issues": list(controller_contract_readiness["issues"]),
    }
    benchmark_mapping_readiness = {
        "ready": report.valid and benchmark_name is not None and controller_contract_readiness["ready"],
        "benchmark_name": benchmark_name,
        "target_robot_name": spec.robot.get("name"),
        "target_robot_def": spec.robot.get("def"),
        "expected_sensor_keys": list(scenario_def.required_sensor_keys) if scenario_def else [],
        "expected_metric_keys": list(scenario_def.required_metric_keys) if scenario_def else [],
        "expected_actuator_keys": list(scenario_def.required_actuator_keys) if scenario_def else [],
        "issues": [
            issue.code
            for issue in report.issues
            if issue.field in {"benchmark.profile", "benchmark.duration_s", "controller.default_camera", "sensors.required", "actuators.required"}
        ],
    }
    world_authoring_readiness = {
        "ready": report.valid,
        "supported_edit_targets": ["spawn", "obstacles", "walls", "landmarks", "zones", "props"],
        "counts": {
            "obstacles": len(spec.layout.get("obstacles", [])) if isinstance(spec.layout.get("obstacles"), list) else 0,
            "walls": len(spec.layout.get("walls", [])) if isinstance(spec.layout.get("walls"), list) else 0,
            "landmarks": len(spec.layout.get("landmarks", [])) if isinstance(spec.layout.get("landmarks"), list) else 0,
            "zones": len(spec.layout.get("zones", [])) if isinstance(spec.layout.get("zones"), list) else 0,
            "props": len(spec.layout.get("props", [])) if isinstance(spec.layout.get("props"), list) else 0,
        },
        "recommended_next_edit_ops": _recommended_next_edit_ops(spec),
        "issues": [issue.code for issue in report.issues if issue.field and issue.field.startswith("layout.")],
    }
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
        "controller_scaffold_source": str(get_scenario(benchmark_name, robot_profile=robot_profile).controller) if benchmark_name else None,
        "controller_ready": bool(spec.controller.get("path")),
        "benchmark_ready": report.valid and benchmark_name is not None,
        "mcp_ready": report.valid,
        "benchmark_readiness": benchmark_readiness,
        "unsupported_combinations": unsupported_combinations,
        "controller_contract_readiness": controller_contract_readiness,
        "controller_authoring_readiness": controller_authoring_readiness,
        "build_readiness": build_readiness,
        "runtime_smoke_readiness": runtime_smoke_readiness,
        "benchmark_mapping_readiness": benchmark_mapping_readiness,
        "world_authoring_readiness": world_authoring_readiness,
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
    suggested_robot_profile = _discover_world_robot_profile(world_path)
    suggested_benchmark_name = SUPPORTED_TASKS[inferred_kind]
    discovered_robot_name, discovered_robot_def = _discover_world_robot_identity(
        world_path,
        suggested_benchmark_name,
        robot_profile=suggested_robot_profile,
    )
    discovered_devices = _discover_controller_devices(controller_path)
    world_inventory = inspect_world(world_path)
    scenario_def = get_scenario(suggested_benchmark_name, robot_profile=suggested_robot_profile)
    profile = get_robot_profile(suggested_robot_profile)
    scene_node_summary = world_inventory.get("scene_node_summary", world_inventory.get("summary", {}))
    authoring_targets = world_inventory.get("supported_edit_targets", [])
    controller_authoring_context = {
        "scenario": suggested_benchmark_name,
        "robot_family": profile.robot_family,
        "robot_profile": profile.robot_profile,
        "default_camera": scenario_def.default_camera,
        "expected_sensor_keys": list(scenario_def.required_sensor_keys),
        "expected_metric_keys": list(scenario_def.required_metric_keys),
        "expected_actuator_keys": list(scenario_def.required_actuator_keys),
        "discovered_devices": discovered_devices,
    }
    scenario_name = f"imported-{world_path.stem}"
    scenario_dir = root / "scenarios" / scenario_name
    scenario_dir.mkdir(parents=True, exist_ok=True)
    spec_path = scenario_dir / SCENARIO_SPEC_FILENAME

    spec = _default_spec(_default_template_for_kind(inferred_kind, robot_profile=suggested_robot_profile), scenario_name, _load_project_manifest(root).project_name)
    spec.scenario["kind"] = inferred_kind
    spec.robot["template"] = profile.robot_profile
    spec.robot["name"] = discovered_robot_name
    spec.robot["def"] = discovered_robot_def
    spec.controller["path"] = str(controller_path)
    minimal_scenario_metadata = {
        "scenario_name": scenario_name,
        "scenario_kind": inferred_kind,
        "benchmark_name": suggested_benchmark_name,
        "robot_name": discovered_robot_name,
        "robot_def": discovered_robot_def,
        "controller_path": str(controller_path),
        "world_path": str(world_path),
    }
    spec.import_source = {
        "world_path": str(world_path),
        "controller_path": str(controller_path),
        "discovered_robot_name": discovered_robot_name,
        "discovered_robot_def": discovered_robot_def,
        "discovered_robot_family": profile.robot_family,
        "suggested_robot_profile": profile.robot_profile,
        "runtime_target": "interactive-webots",
        "physical_adapter_supported": profile.robot_profile == "monsterborg-4wd",
        "discovered_devices": discovered_devices,
        "suggested_benchmark_name": suggested_benchmark_name,
        "minimal_scenario_metadata": minimal_scenario_metadata,
        "world_inventory": world_inventory,
        "scene_node_summary": scene_node_summary,
        "authoring_targets": authoring_targets,
        "controller_authoring_context": controller_authoring_context,
    }
    spec.environment["imported"] = True
    atomic_write_text(spec_path, json.dumps(spec.to_dict(), indent=2), encoding="utf-8")
    next_commands = [
        f'webots-kit scenario validate "{spec_path}"',
        f'webots-kit world inspect "{world_path}" --json',
        f'webots-kit controller inspect "{controller_path}" --scenario {suggested_benchmark_name} --json',
    ]
    return {
        "project_root": str(root),
        "manifest_path": str(manifest_path),
        "scenario_metadata_path": str(spec_path),
        "world_path": str(world_path),
        "controller_path": str(controller_path),
        "inferred_kind": inferred_kind,
        "inferred_scenario_kind": inferred_kind,
        "suggested_benchmark_name": suggested_benchmark_name,
        "discovered_robot_family": profile.robot_family,
        "suggested_robot_profile": profile.robot_profile,
        "runtime_target": "interactive-webots",
        "physical_adapter_supported": profile.robot_profile == "monsterborg-4wd",
        "discovered_robot_name": discovered_robot_name,
        "discovered_robot_def": discovered_robot_def,
        "discovered_devices": discovered_devices,
        "minimal_scenario_metadata": minimal_scenario_metadata,
        "world_inventory": world_inventory,
        "scene_node_summary": scene_node_summary,
        "authoring_targets": authoring_targets,
        "controller_authoring_context": controller_authoring_context,
        "edit_target_summary": authoring_targets,
        "next_commands": next_commands,
        "team_handoff_summary": f"Imported {world_path.name} as {scenario_name}; validate the generated spec, inspect the world, then inspect the controller contract before a rerun.",
        "support_tier": "experimental-foundation",
    }


def export_session(session_id: str, *, output: Path | None = None, store: SessionStore | None = None) -> SessionExport:
    session_store = store or SessionStore()
    manifest = session_store.load_manifest(session_id)
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
        scenario=manifest.scenario,
        status=manifest.status,
        last_error_code=manifest.last_error_code,
        result_reason=manifest.last_error_code or manifest.status or "completed",
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
    runtime_failure_class = _classify_runtime_failure(last_error_code=session_state.get("last_error_code"), status=session.get("status"), result_reason=result_reason)
    telemetry_summary = _build_telemetry_summary(runtime_summary)
    benchmark_summary = _build_benchmark_summary(
        benchmark_name=benchmark_name,
        status=session.get("status"),
        result_reason=result_reason,
        last_error_code=session_state.get("last_error_code"),
    )
    triage_recipe = _build_triage_recipe(runtime_failure_class)
    fix_hints = controller_fix_hints(benchmark_name, result_reason)
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
        "benchmark_summary": benchmark_summary,
        "telemetry_summary": telemetry_summary,
        "runtime_failure_class": runtime_failure_class,
        "triage_recipe": triage_recipe,
        "controller_fix_hints": fix_hints,
        "copied_logs": sorted(Path(path).name for path in copied_logs) if copied_logs is not None else sorted(path.name for path in (export_root / "logs").glob("*")),
        "copied_artifacts": (
            sorted(Path(path).name for path in copied_artifacts)
            if copied_artifacts is not None
            else sorted(path.name for path in (export_root / "artifacts").glob("*"))
        ),
        "team_handoff_summary": f"Replay indicates {runtime_failure_class} focus; start with {triage_recipe.get('primary_artifacts', [])} before handing the session back for a rerun.",
        "next_step": benchmark_next_step(benchmark_name, result_reason),
        "support_tier": "experimental-foundation",
    }


def infer_project_kind(world_path: Path) -> str:
    content = world_path.read_text(encoding="utf-8", errors="replace").lower()
    if any(token in content for token in ("line follower", "line-follower", "line_track", "line-segment", "line_segment", "tri_color")):
        return "line-follow"
    if "woodenbox" in content or "obstacle" in content:
        return "obstacle-avoidance"
    if "waypoint" in content or "goal-region" in content:
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
        f"benchmark_profile: {result.normalized.get('benchmark', {}).get('profile')}",
        f"arena_floor: {result.normalized.get('environment', {}).get('arena', {}).get('floor')}",
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
        f"benchmark_readiness: {payload.get('benchmark_readiness', {}).get('ready')}",
        f"controller_contract_readiness: {payload.get('controller_contract_readiness', {}).get('ready')}",
        f"controller_authoring_readiness: {payload.get('controller_authoring_readiness', {}).get('ready')}",
        f"build_readiness: {payload.get('build_readiness', {}).get('ready')}",
        f"runtime_smoke_readiness: {payload.get('runtime_smoke_readiness', {}).get('ready')}",
        f"benchmark_mapping_readiness: {payload.get('benchmark_mapping_readiness', {}).get('ready')}",
        f"world_authoring_readiness: {payload.get('world_authoring_readiness', {}).get('ready')}",
        f"unsupported_combinations: {len(payload.get('unsupported_combinations', []))}",
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
    benchmark_summary = payload.get("benchmark_summary") if isinstance(payload.get("benchmark_summary"), dict) else {}
    telemetry_summary = payload.get("telemetry_summary") if isinstance(payload.get("telemetry_summary"), dict) else {}
    triage_recipe = payload.get("triage_recipe") if isinstance(payload.get("triage_recipe"), dict) else {}
    fix_hints = payload.get("controller_fix_hints") if isinstance(payload.get("controller_fix_hints"), list) else []
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
        f"runtime_failure_class: {payload.get('runtime_failure_class')}",
        f"benchmark_summary: {benchmark_summary.get('benchmark_name')} ({benchmark_summary.get('result_reason')})",
        f"telemetry_roles: {telemetry_summary.get('connected_roles')}",
        f"runtime_runner_mode: {runner_mode_text}",
        f"runtime_python: {runtime_environment.get('python_executable')}",
        f"copied_logs: {payload['copied_logs']}",
        f"copied_artifacts: {payload['copied_artifacts']}",
        f"standard_artifacts: {sorted(payload.get('standard_artifacts', {}))}",
        f"triage_focus: {triage_recipe.get('focus')}",
        f"triage_primary_artifacts: {triage_recipe.get('primary_artifacts')}",
        f"team_handoff_summary: {payload.get('team_handoff_summary')}",
        f"summary: {len(payload['copied_logs'])} logs, {len(payload['copied_artifacts'])} artifacts",
        "support_tier: experimental-foundation",
        f"next_step: {payload['next_step']}",
    ]
    if fix_hints:
        lines.append(f"controller_fix_hints: {fix_hints}")
    return "\n".join(lines)


def _build_line_follow_world(spec: ScenarioSpec) -> str:
    arena_dimensions = spec.environment["arena"]["dimensions"]
    floor_style = str(spec.environment.get("arena", {}).get("floor", "plain"))
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
    for index, wall in enumerate(spec.layout.get("walls", []), start=1):
        segment_nodes.append(_wall_block(index, wall))
    for index, landmark in enumerate(spec.layout.get("landmarks", []), start=1):
        segment_nodes.append(_landmark_block(index, landmark))
    for index, zone in enumerate(spec.layout.get("zones", []), start=1):
        segment_nodes.append(_zone_block(index, zone))
    for index, prop in enumerate(spec.layout.get("props", []), start=1):
        segment_nodes.append(_prop_block(index, prop))
    return _world_shell(
        title=f"{spec.project['name']} {spec.scenario['name']}",
        info_lines=["Generated by webots-kit scenario build.", "Template-driven line-follow scenario."],
        arena_size=arena_dimensions,
        floor_style=floor_style,
        body="\n".join(segment_nodes),
        robot_block=_robot_block(robot_profile=str(spec.robot["template"]), robot_name=str(spec.robot["name"]), spawn=spawn, camera_mode=True),
    )


def _build_arena_world(spec: ScenarioSpec) -> str:
    arena_dimensions = spec.environment["arena"]["dimensions"]
    floor_style = str(spec.environment.get("arena", {}).get("floor", "plain"))
    spawn = spec.layout["spawn"]
    body_nodes: list[str] = []
    for index, obstacle in enumerate(spec.layout.get("obstacles", []), start=1):
        body_nodes.append(_obstacle_block(index, obstacle))
    for index, wall in enumerate(spec.layout.get("walls", []), start=1):
        body_nodes.append(_wall_block(index, wall))
    for index, landmark in enumerate(spec.layout.get("landmarks", []), start=1):
        body_nodes.append(_landmark_block(index, landmark))
    for index, zone in enumerate(spec.layout.get("zones", []), start=1):
        body_nodes.append(_zone_block(index, zone))
    for index, prop in enumerate(spec.layout.get("props", []), start=1):
        body_nodes.append(_prop_block(index, prop))
    if spec.scenario["kind"] == "waypoint-nav":
        goal = spec.layout.get("goal_region") or {"center": spec.layout["waypoints"][-1], "radius": 0.16}
        body_nodes.append(_goal_block(goal))
    return _world_shell(
        title=f"{spec.project['name']} {spec.scenario['name']}",
        info_lines=["Generated by webots-kit scenario build.", f"Template-driven {spec.scenario['kind']} scenario."],
        arena_size=arena_dimensions,
        floor_style=floor_style,
        body="\n".join(body_nodes),
        robot_block=_robot_block(robot_profile=str(spec.robot["template"]), robot_name=str(spec.robot["name"]), spawn=spawn, camera_mode=False),
    )


def _world_shell(*, title: str, info_lines: list[str], arena_size: list[float], floor_style: str, body: str, robot_block: str) -> str:
    info = "\n".join(f'    "{line}"' for line in info_lines)
    supervisor_y = -max(float(arena_size[1]) / 2 - 0.05, 0.95)
    robot_name = robot_block.split('name "')[1].split('"', 1)[0]
    floor_overlay = _floor_overlay_block(floor_style, arena_size)
    externproto_lines = [
        'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/backgrounds/protos/TexturedBackground.proto"',
        'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/backgrounds/protos/TexturedBackgroundLight.proto"',
        'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/floors/protos/RectangleArena.proto"',
    ]
    if "E-puck" in robot_block:
        externproto_lines.append('EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/robots/gctronic/e-puck/protos/E-puck.proto"')
    return f"""#VRML_SIM R2025a utf8

{chr(10).join(externproto_lines)}

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
{floor_overlay}
{body}
{robot_block}
Robot {{
  translation 0 {_fmt(supervisor_y)} 0.03
  name "kit-supervisor"
  controller "<extern>"
  supervisor TRUE
}}
"""


def _floor_overlay_block(floor_style: str, arena_size: list[float]) -> str:
    floor = SUPPORTED_ARENA_FLOORS.get(floor_style, SUPPORTED_ARENA_FLOORS["plain"])
    base = floor["base_color"]
    base_block = f"""Solid {{
  translation 0 0 0.0004
  children [
    DEF FLOOR_STYLE Shape {{
      appearance PBRAppearance {{
        baseColor {_fmt(base[0])} {_fmt(base[1])} {_fmt(base[2])}
        roughness 1
        metalness 0
      }}
      geometry Box {{
        size {_fmt(arena_size[0])} {_fmt(arena_size[1])} 0.0008
      }}
    }}
  ]
  name "floor-style-{floor_style}"
  locked TRUE
}}"""
    if not floor["grid"]:
        return base_block
    stripe_nodes: list[str] = [base_block]
    spacing = 0.25
    half_width = float(arena_size[0]) / 2
    half_height = float(arena_size[1]) / 2
    grid_color = "0.72 0.72 0.72"
    grid_index = 1
    y = -half_height + spacing
    while y < half_height:
        stripe_nodes.append(
            f"""Solid {{
  translation 0 {_fmt(y)} 0.0012
  children [
    Shape {{
      appearance PBRAppearance {{
        baseColor {grid_color}
        roughness 1
        metalness 0
      }}
      geometry Box {{
        size {_fmt(arena_size[0])} 0.01 0.0004
      }}
    }}
  ]
  name "floor-grid-horizontal-{grid_index}"
  locked TRUE
}}"""
        )
        grid_index += 1
        y += spacing
    x = -half_width + spacing
    while x < half_width:
        stripe_nodes.append(
            f"""Solid {{
  translation {_fmt(x)} 0 0.0012
  children [
    Shape {{
      appearance PBRAppearance {{
        baseColor {grid_color}
        roughness 1
        metalness 0
      }}
      geometry Box {{
        size 0.01 {_fmt(arena_size[1])} 0.0004
      }}
    }}
  ]
  name "floor-grid-vertical-{grid_index}"
  locked TRUE
}}"""
        )
        grid_index += 1
        x += spacing
    return "\n".join(stripe_nodes)


def _robot_block(*, robot_profile: str, robot_name: str, spawn: dict[str, Any], camera_mode: bool) -> str:
    translation = spawn["translation"]
    rotation = float(spawn.get("rotation_z", 0.0))
    if robot_profile == "monsterborg-4wd":
        camera_block = ""
        if camera_mode:
            camera_block = """
    Transform {
      translation 0.16 0 0.14
      rotation 0 1 0 0.62
      children [
        Camera {
          name "front_camera"
          width 40
          height 1
          fieldOfView 1.05
        }
      ]
    }"""
        else:
            camera_block = """
    Transform {
      translation 0.16 0 0.14
      rotation 0 1 0 0.62
      children [
        Camera {
          name "front_camera"
          width 64
          height 12
          fieldOfView 1.05
        }
      ]
    }"""
        return f"""DEF MONSTERBORG Robot {{
  translation {_fmt(translation[0])} {_fmt(translation[1])} {_fmt(translation[2])}
  rotation 0 0 1 {_fmt(rotation)}
  name "{robot_name}"
  controller "<extern>"
  children [
    Transform {{
      translation 0 0 0.11
      children [
        Shape {{
          appearance PBRAppearance {{
            baseColor 0.7 0.72 0.76
            roughness 0.9
            metalness 0.05
          }}
          geometry Box {{
            size 0.24 0.18 0.04
          }}
        }}
      ]
    }}
{camera_block}
    Transform {{
      translation 0.17 0 0.09
      children [
        DistanceSensor {{
          name "front_range"
          lookupTable [
            0 1000 0
            0.5 600 0
            1 200 0
          ]
          type "infra-red"
        }}
      ]
    }}
    InertialUnit {{
      name "imu"
    }}
    HingeJoint {{
      jointParameters HingeJointParameters {{
        axis 0 1 0
        anchor 0 0.11 0.055
      }}
      device [
        RotationalMotor {{
          name "front_left_motor"
          maxVelocity 9
          maxTorque 24
        }}
        PositionSensor {{
          name "left_encoder"
        }}
      ]
      endPoint Solid {{
        translation 0 0.11 0.055
        name "front-left-drive-wheel"
        children [
          Pose {{
            rotation -1 0 0 1.5708
            children [
              Shape {{
                appearance PBRAppearance {{
                  baseColor 0.05 0.05 0.05
                  roughness 1
                  metalness 0
                }}
                geometry Cylinder {{
                  radius 0.055
                  height 0.038
                }}
              }}
            ]
          }}
        ]
        boundingObject Pose {{
          rotation -1 0 0 1.5708
          children [
            Cylinder {{
              radius 0.055
              height 0.038
            }}
          ]
        }}
        physics Physics {{
          density -1
          mass 0.12
        }}
      }}
    }}
    HingeJoint {{
      jointParameters HingeJointParameters {{
        axis 0 1 0
        anchor 0 -0.11 0.055
      }}
      device [
        RotationalMotor {{
          name "front_right_motor"
          maxVelocity 9
          maxTorque 24
        }}
        PositionSensor {{
          name "right_encoder"
        }}
      ]
      endPoint Solid {{
        translation 0 -0.11 0.055
        name "front-right-drive-wheel"
        children [
          Pose {{
            rotation -1 0 0 1.5708
            children [
              Shape {{
                appearance PBRAppearance {{
                  baseColor 0.05 0.05 0.05
                  roughness 1
                  metalness 0
                }}
                geometry Cylinder {{
                  radius 0.055
                  height 0.038
                }}
              }}
            ]
          }}
        ]
        boundingObject Pose {{
          rotation -1 0 0 1.5708
          children [
            Cylinder {{
              radius 0.055
              height 0.038
            }}
          ]
        }}
        physics Physics {{
          density -1
          mass 0.12
        }}
      }}
    }}
    Transform {{
      translation 0.1 0.11 0.055
      children [
        Shape {{
          appearance PBRAppearance {{
            baseColor 0.05 0.05 0.05
            roughness 1
            metalness 0
          }}
          geometry Cylinder {{
            radius 0.055
            height 0.038
          }}
        }}
      ]
    }}
    Transform {{
      translation -0.1 0.11 0.055
      children [
        Shape {{
          appearance PBRAppearance {{
            baseColor 0.05 0.05 0.05
            roughness 1
            metalness 0
          }}
          geometry Cylinder {{
            radius 0.055
            height 0.038
          }}
        }}
      ]
    }}
    Transform {{
      translation 0.1 -0.11 0.055
      children [
        Shape {{
          appearance PBRAppearance {{
            baseColor 0.05 0.05 0.05
            roughness 1
            metalness 0
          }}
          geometry Cylinder {{
            radius 0.055
            height 0.038
          }}
        }}
      ]
    }}
    Transform {{
      translation -0.1 -0.11 0.055
      children [
        Shape {{
          appearance PBRAppearance {{
            baseColor 0.05 0.05 0.05
            roughness 1
            metalness 0
          }}
          geometry Cylinder {{
            radius 0.055
            height 0.038
          }}
        }}
      ]
    }}
    HingeJoint {{
      jointParameters HingeJointParameters {{
        axis 0 1 0
        anchor -0.06 0.04 0.18
      }}
      device [
        RotationalMotor {{
          name "rear_left_motor"
          maxVelocity 9
        }}
      ]
      endPoint Solid {{
        translation -0.06 0.04 0.18
        name "rear-left-actuator"
        children [
          Shape {{
            appearance PBRAppearance {{
              baseColor 0.2 0.2 0.2
              transparency 1
            }}
            geometry Sphere {{
              radius 0.01
            }}
          }}
        ]
        boundingObject Sphere {{
          radius 0.01
        }}
        physics Physics {{
          density -1
          mass 0.001
        }}
      }}
    }}
    HingeJoint {{
      jointParameters HingeJointParameters {{
        axis 0 1 0
        anchor -0.06 -0.04 0.18
      }}
      device [
        RotationalMotor {{
          name "rear_right_motor"
          maxVelocity 9
        }}
      ]
      endPoint Solid {{
        translation -0.06 -0.04 0.18
        name "rear-right-actuator"
        children [
          Shape {{
            appearance PBRAppearance {{
              baseColor 0.2 0.2 0.2
              transparency 1
            }}
            geometry Sphere {{
              radius 0.01
            }}
          }}
        ]
        boundingObject Sphere {{
          radius 0.01
        }}
        physics Physics {{
          density -1
          mass 0.001
        }}
      }}
    }}
    Solid {{
      translation 0.13 0 0.02
      name "front-caster"
      children [
        Shape {{
          appearance PBRAppearance {{
            baseColor 0.15 0.15 0.15
            roughness 1
            metalness 0
          }}
          geometry Sphere {{
            radius 0.02
          }}
        }}
      ]
      boundingObject Sphere {{
        radius 0.02
      }}
      physics Physics {{
        density -1
        mass 0.01
      }}
    }}
    Solid {{
      translation -0.13 0 0.02
      name "rear-caster"
      children [
        Shape {{
          appearance PBRAppearance {{
            baseColor 0.15 0.15 0.15
            roughness 1
            metalness 0
          }}
          geometry Sphere {{
            radius 0.02
          }}
        }}
      ]
      boundingObject Sphere {{
        radius 0.02
      }}
      physics Physics {{
        density -1
        mass 0.01
      }}
    }}
  ]
  boundingObject Transform {{
    translation 0 0 0.11
    children [
      Box {{
        size 0.24 0.18 0.04
      }}
    ]
  }}
  physics Physics {{
    density -1
    mass 1.6
  }}
}}"""
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


def _wall_block(index: int, wall: dict[str, Any]) -> str:
    start = wall.get("start", [-0.3, 0.0])
    end = wall.get("end", [0.3, 0.0])
    thickness = float(wall.get("thickness", 0.02))
    height = float(wall.get("height", 0.08))
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    length = math.hypot(dx, dy)
    center_x = (float(start[0]) + float(end[0])) / 2
    center_y = (float(start[1]) + float(end[1])) / 2
    rotation = math.atan2(dy, dx) if length > 0 else 0.0
    return f"""Solid {{
  translation {_fmt(center_x)} {_fmt(center_y)} {_fmt(height / 2)}
  rotation 0 0 1 {_fmt(rotation)}
  children [
    DEF WALL_{index} Shape {{
      appearance PBRAppearance {{
        baseColor 0.4 0.4 0.4
        roughness 1
        metalness 0
      }}
      geometry Box {{
        size {_fmt(length)} {_fmt(thickness)} {_fmt(height)}
      }}
    }}
  ]
  name "{wall.get('name', f'wall-{index}')}"
  boundingObject USE WALL_{index}
}}"""


def _landmark_block(index: int, landmark: dict[str, Any]) -> str:
    position = landmark.get("position", [0.0, 0.0])
    radius = float(landmark.get("radius", 0.04))
    return f"""Solid {{
  translation {_fmt(position[0])} {_fmt(position[1])} 0.005
  children [
    Shape {{
      appearance PBRAppearance {{
        baseColor 0.15 0.3 0.9
        roughness 1
        metalness 0
      }}
      geometry Cylinder {{
        height 0.01
        radius {_fmt(radius)}
      }}
    }}
  ]
  name "{landmark.get('name', f'landmark-{index}')}"
  locked TRUE
}}"""


def _zone_block(index: int, zone: dict[str, Any]) -> str:
    center = zone.get("center", [0.0, 0.0])
    size = zone.get("size", [0.2, 0.2])
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
      geometry Box {{
        size {_fmt(size[0])} {_fmt(size[1])} 0.002
      }}
    }}
  ]
  name "{zone.get('name', f'zone-{index}')}"
  locked TRUE
}}"""


def _prop_block(index: int, prop: dict[str, Any]) -> str:
    position = prop.get("position", [0.0, 0.0])
    size = prop.get("size", [0.08, 0.08, 0.08])
    return f"""Solid {{
  translation {_fmt(position[0])} {_fmt(position[1])} {_fmt(float(size[2]) / 2)}
  children [
    DEF PROP_{index} Shape {{
      appearance PBRAppearance {{
        baseColor 0.72 0.53 0.27
        roughness 1
        metalness 0
      }}
      geometry Box {{
        size {_fmt(size[0])} {_fmt(size[1])} {_fmt(size[2])}
      }}
    }}
  ]
  name "{prop.get('name', f'prop-{index}')}"
  boundingObject USE PROP_{index}
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
    robot_profile = SUPPORTED_ENVIRONMENT_TEMPLATES[template]["robot_profile"]
    benchmark_name = SUPPORTED_TASKS[default_kind]
    profile = get_robot_profile(robot_profile)
    scenario = get_scenario(benchmark_name, robot_profile=robot_profile)
    defaults = _template_defaults(template)
    return ScenarioSpec(
        schema_version=1,
        project={"name": project_name},
        scenario={"name": scenario_name, "kind": default_kind},
        robot={"template": profile.robot_profile, "name": _default_robot_name(default_kind, scenario_name, robot_profile=profile.robot_profile), "def": _default_robot_def(profile.robot_profile)},
        environment={"template": template, "arena": defaults["arena"]},
        layout=defaults["layout"],
        task={"kind": default_kind, "description": f"Generated {default_kind} task."},
        controller={"path": f"controllers/{scenario_name}_agent.py", "default_camera": scenario.default_camera},
        benchmark={"profile": benchmark_name, "duration_s": 20.0, "threshold_overrides": {}},
        sensors={"required": list(scenario.required_sensor_keys)},
        actuators={"required": list(scenario.required_actuator_keys)},
    )


def _template_defaults(template: str) -> dict[str, Any]:
    return _clone_json_like(
        {
        "epuck-line-track": {
            "arena": {"dimensions": [1.8, 1.2], "floor": "light"},
            "layout": {
                "spawn": {"translation": [-0.7, 0.03, 0.0], "rotation_z": 0.0},
                "line_track": {"width": 0.06, "points": [[-0.75, 0.03], [-0.2, 0.03], [-0.2, 0.42], [0.55, 0.42], [0.55, -0.2]]},
                "obstacles": [],
                "walls": [],
                "landmarks": [],
                "zones": [],
                "props": [],
                "waypoints": [],
            },
        },
        "epuck-waypoint": {
            "arena": {"dimensions": [2.0, 2.0], "floor": "plain"},
            "layout": {
                "spawn": {"translation": [-0.65, 0.0, 0.0], "rotation_z": 0.0},
                "obstacles": [],
                "walls": [],
                "landmarks": [],
                "zones": [],
                "props": [],
                "waypoints": [[0.55, 0.0]],
                "goal_region": {"center": [0.55, 0.0], "radius": 0.16},
            },
        },
        "epuck-arena": {
            "arena": {"dimensions": [2.0, 2.0], "floor": "grid"},
            "layout": {
                "spawn": {"translation": [-0.55, 0.0, 0.0], "rotation_z": 0.0},
                "obstacles": [],
                "walls": [],
                "landmarks": [],
                "zones": [],
                "props": [],
                "waypoints": [[0.4, 0.0]],
                "goal_region": {"center": [0.4, 0.0], "radius": 0.16},
            },
        },
        "epuck-obstacle-course": {
            "arena": {"dimensions": [2.0, 2.0], "floor": "grid"},
            "layout": {
                "spawn": {"translation": [0.0, 0.0, 0.0], "rotation_z": 1.57},
                "obstacles": [
                    {"shape": "box", "position": [-0.68, 0.2], "size": [0.1, 0.1, 0.1], "rotation_z": 0.5},
                    {"shape": "box", "position": [0.35, 0.75], "size": [0.1, 0.1, 0.1], "rotation_z": 4.96782},
                    {"shape": "box", "position": [-0.35, -0.5], "size": [0.1, 0.1, 0.1], "rotation_z": 5.36782},
                ],
                "walls": [],
                "landmarks": [],
                "zones": [],
                "props": [],
                "waypoints": [],
            },
        },
        "monsterborg-line-track": {
            "arena": {"dimensions": [3.2, 2.2], "floor": "light"},
            "layout": {
                "spawn": {"translation": [-1.1, 0.05, 0.0], "rotation_z": 0.0},
                "line_track": {"width": 0.1, "points": [[-1.25, 0.05], [-0.45, 0.05], [-0.15, 0.6], [0.95, 0.6], [1.15, -0.4]]},
                "obstacles": [],
                "walls": [],
                "landmarks": [],
                "zones": [],
                "props": [],
                "waypoints": [],
            },
        },
        "monsterborg-waypoint": {
            "arena": {"dimensions": [3.4, 3.0], "floor": "plain"},
            "layout": {
                "spawn": {"translation": [-1.0, 0.0, 0.0], "rotation_z": 0.0},
                "obstacles": [],
                "walls": [],
                "landmarks": [],
                "zones": [],
                "props": [],
                "waypoints": [[1.35, 0.0]],
                "goal_region": {"center": [1.35, 0.0], "radius": 0.3},
            },
        },
        "monsterborg-obstacle-course": {
            "arena": {"dimensions": [3.4, 3.0], "floor": "grid"},
            "layout": {
                "spawn": {"translation": [-0.9, 0.0, 0.0], "rotation_z": 0.0},
                "obstacles": [
                    {"shape": "box", "position": [-0.05, 0.42], "size": [0.16, 0.16, 0.14], "rotation_z": 0.0},
                    {"shape": "box", "position": [0.62, -0.48], "size": [0.16, 0.16, 0.14], "rotation_z": 0.3},
                    {"shape": "cylinder", "position": [0.95, 0.62], "radius": 0.08, "height": 0.16, "rotation_z": 0.0},
                ],
                "walls": [],
                "landmarks": [],
                "zones": [],
                "props": [],
                "waypoints": [],
            },
        },
    }[template]
    )


def _apply_scenario_defaults(spec: ScenarioSpec) -> None:
    scenario_kind = _str_field(spec.scenario, "kind")
    environment_template = _str_field(spec.environment, "template")
    robot_profile = robot_profile_from_template(_str_field(spec.robot, "template"))
    if not scenario_kind and environment_template in SUPPORTED_ENVIRONMENT_TEMPLATES:
        scenario_kind = SUPPORTED_ENVIRONMENT_TEMPLATES[environment_template]["default_kind"]
        spec.scenario["kind"] = scenario_kind
    benchmark_name = SUPPORTED_TASKS.get(scenario_kind or "")
    if environment_template in SUPPORTED_ENVIRONMENT_TEMPLATES:
        robot_profile = SUPPORTED_ENVIRONMENT_TEMPLATES[environment_template]["robot_profile"]
        spec.robot.setdefault("template", robot_profile)
    scenario_def = get_scenario(benchmark_name, robot_profile=robot_profile) if benchmark_name else None
    template = environment_template or (_default_template_for_kind(scenario_kind, robot_profile=robot_profile) if scenario_kind in SUPPORTED_TASKS else "epuck-waypoint")
    defaults = _template_defaults(template)

    arena = spec.environment.setdefault("arena", {})
    arena.setdefault("dimensions", defaults["arena"]["dimensions"])
    arena.setdefault("floor", defaults["arena"].get("floor", "plain"))

    layout = spec.layout
    spawn = layout.setdefault("spawn", {})
    spawn.setdefault("translation", defaults["layout"]["spawn"]["translation"])
    spawn.setdefault("rotation_z", defaults["layout"]["spawn"].get("rotation_z", 0.0))
    layout.setdefault("obstacles", defaults["layout"].get("obstacles", []))
    layout.setdefault("walls", defaults["layout"].get("walls", []))
    layout.setdefault("landmarks", defaults["layout"].get("landmarks", []))
    layout.setdefault("zones", defaults["layout"].get("zones", []))
    layout.setdefault("props", defaults["layout"].get("props", []))
    layout.setdefault("waypoints", defaults["layout"].get("waypoints", []))
    if scenario_kind == "line-follow":
        line_track = layout.setdefault("line_track", {})
        line_track.setdefault("width", defaults["layout"].get("line_track", {}).get("width", 0.06))
        line_track.setdefault("points", defaults["layout"].get("line_track", {}).get("points", []))
    if scenario_kind == "waypoint-nav" and not isinstance(layout.get("goal_region"), dict) and _is_point_list(layout.get("waypoints"), min_points=1):
        layout["goal_region"] = {"center": list(layout["waypoints"][-1]), "radius": 0.16}

    task_kind = _str_field(spec.task, "kind")
    if scenario_kind and not task_kind:
        spec.task["kind"] = scenario_kind
        spec.task.setdefault("description", f"Generated {scenario_kind} task.")

    if scenario_def:
        spec.controller.setdefault("default_camera", scenario_def.default_camera)
        spec.benchmark.setdefault("profile", scenario_def.name)
        spec.benchmark.setdefault("duration_s", 20.0)
        spec.benchmark.setdefault("threshold_overrides", {})
        spec.sensors.setdefault("required", list(scenario_def.required_sensor_keys))
        spec.actuators.setdefault("required", list(scenario_def.required_actuator_keys))


def _clone_json_like(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _distance_2d(left: list[float] | tuple[float, ...], right: list[float] | tuple[float, ...]) -> float:
    dx = float(left[0]) - float(right[0])
    dy = float(left[1]) - float(right[1])
    return math.hypot(dx, dy)


def _validate_layout_geometry(spec: ScenarioSpec) -> list[ValidationIssue]:
    arena = spec.environment.get("arena") if isinstance(spec.environment.get("arena"), dict) else {}
    if not _is_positive_pair(arena.get("dimensions")):
        return []

    issues: list[ValidationIssue] = []
    half_width = float(arena["dimensions"][0]) / 2
    half_height = float(arena["dimensions"][1]) / 2
    clearance_radius = get_robot_profile(robot_profile_from_template(_str_field(spec.robot, "template"))).footprint_radius
    layout = spec.layout if isinstance(spec.layout, dict) else {}
    scenario_kind = _str_field(spec.scenario, "kind")
    spawn = layout.get("spawn") if isinstance(layout.get("spawn"), dict) else {}
    spawn_translation = spawn.get("translation")
    spawn_xy = [float(spawn_translation[0]), float(spawn_translation[1])] if _is_numeric_list(spawn_translation, 3) else None

    def point_in_bounds(point: list[float] | tuple[float, ...], *, padding: float = 0.0) -> bool:
        return abs(float(point[0])) <= half_width - padding and abs(float(point[1])) <= half_height - padding

    if spawn_xy and not point_in_bounds(spawn_xy, padding=clearance_radius):
        issues.append(
            ValidationIssue(
                "spawn-out-of-bounds",
                "layout.spawn.translation must keep the robot inside environment.arena.dimensions.",
                "layout.spawn.translation",
            )
        )

    waypoints = layout.get("waypoints") if isinstance(layout.get("waypoints"), list) else []
    for index, point in enumerate(waypoints):
        if _is_numeric_list(point, 2) and not point_in_bounds(point):
            issues.append(
                ValidationIssue(
                    "waypoint-out-of-bounds",
                    f"layout.waypoints[{index}] must stay inside the declared arena dimensions.",
                    "layout.waypoints",
                )
            )

    goal_region = layout.get("goal_region") if isinstance(layout.get("goal_region"), dict) else {}
    goal_center = goal_region.get("center")
    goal_radius = goal_region.get("radius")
    if _is_numeric_list(goal_center, 2) and isinstance(goal_radius, (int, float)) and float(goal_radius) > 0:
        radius = float(goal_radius)
        if not point_in_bounds(goal_center, padding=radius):
            issues.append(
                ValidationIssue(
                    "goal-region-out-of-bounds",
                    "layout.goal_region must stay inside the declared arena dimensions.",
                    "layout.goal_region",
                )
            )
        if spawn_xy and scenario_kind == "waypoint-nav" and _distance_2d(spawn_xy, goal_center) <= radius + clearance_radius:
            issues.append(
                ValidationIssue(
                    "spawn-goal-overlap",
                    "layout.spawn.translation must start outside the goal region for waypoint-nav scenarios.",
                    "layout.spawn.translation",
                )
            )

    if scenario_kind == "line-follow":
        line_track = layout.get("line_track") if isinstance(layout.get("line_track"), dict) else {}
        points = line_track.get("points") if isinstance(line_track.get("points"), list) else []
        if spawn_xy and _is_point_list(points, min_points=2) and _distance_2d(spawn_xy, points[0]) > 0.5:
            issues.append(
                ValidationIssue(
                    "spawn-line-track-mismatch",
                    "layout.spawn.translation should start near the first line_track point for line-follow scenarios.",
                    "layout.spawn.translation",
                    level="warning",
                )
            )

    blocking_objects: list[dict[str, Any]] = []
    obstacles = layout.get("obstacles") if isinstance(layout.get("obstacles"), list) else []
    for index, obstacle in enumerate(obstacles):
        if not isinstance(obstacle, dict) or not _is_numeric_list(obstacle.get("position"), 2):
            continue
        center = [float(obstacle["position"][0]), float(obstacle["position"][1])]
        radius = _obstacle_footprint_radius(obstacle)
        if not point_in_bounds(center, padding=radius):
            issues.append(
                ValidationIssue(
                    "obstacle-out-of-bounds",
                    f"layout.obstacles[{index}] must stay inside the declared arena dimensions.",
                    f"layout.obstacles[{index}].position",
                )
            )
        blocking_objects.append({"kind": "obstacle", "index": index, "center": center, "radius": radius})

    props = layout.get("props") if isinstance(layout.get("props"), list) else []
    prop_objects: list[dict[str, Any]] = []
    for index, prop in enumerate(props):
        if not isinstance(prop, dict) or not _is_numeric_list(prop.get("position"), 2):
            continue
        center = [float(prop["position"][0]), float(prop["position"][1])]
        radius = _box_footprint_radius(prop.get("size", [0.08, 0.08, 0.08]))
        if not point_in_bounds(center, padding=radius):
            issues.append(
                ValidationIssue(
                    "prop-out-of-bounds",
                    f"layout.props[{index}] must stay inside the declared arena dimensions.",
                    f"layout.props[{index}].position",
                )
            )
        prop_objects.append({"kind": "prop", "index": index, "center": center, "radius": radius})
        blocking_objects.append(prop_objects[-1])

    for obstacle in blocking_objects:
        if obstacle["kind"] != "obstacle":
            continue
        for prop in prop_objects:
            if _distance_2d(obstacle["center"], prop["center"]) < obstacle["radius"] + prop["radius"]:
                issues.append(
                    ValidationIssue(
                        "obstacle-prop-collision",
                        f"layout.obstacles[{obstacle['index']}] overlaps layout.props[{prop['index']}].",
                        f"layout.obstacles[{obstacle['index']}]",
                    )
                )

    wall_segments: list[dict[str, Any]] = []
    walls = layout.get("walls") if isinstance(layout.get("walls"), list) else []
    for index, wall in enumerate(walls):
        if not isinstance(wall, dict):
            continue
        start = wall.get("start")
        end = wall.get("end")
        if not (_is_numeric_list(start, 2) and _is_numeric_list(end, 2)):
            continue
        start_point = [float(start[0]), float(start[1])]
        end_point = [float(end[0]), float(end[1])]
        thickness = float(wall.get("thickness", 0.02)) if isinstance(wall.get("thickness", 0.02), (int, float)) else 0.02
        if _distance_2d(start_point, end_point) <= 1e-6:
            issues.append(
                ValidationIssue(
                    "degenerate-wall",
                    f"layout.walls[{index}] must not collapse to a zero-length segment.",
                    f"layout.walls[{index}]",
                )
            )
        if not point_in_bounds(start_point, padding=thickness / 2) or not point_in_bounds(end_point, padding=thickness / 2):
            issues.append(
                ValidationIssue(
                    "wall-out-of-bounds",
                    f"layout.walls[{index}] must stay inside the declared arena dimensions.",
                    f"layout.walls[{index}]",
                )
            )
        wall_segments.append({"index": index, "start": start_point, "end": end_point, "thickness": thickness})

    for left_index, left in enumerate(wall_segments):
        for right in wall_segments[left_index + 1 :]:
            if _segments_intersect_or_overlap(left["start"], left["end"], right["start"], right["end"]):
                issues.append(
                    ValidationIssue(
                        "wall-overlap",
                        f"layout.walls[{left['index']}] overlaps or intersects layout.walls[{right['index']}].",
                        f"layout.walls[{left['index']}]",
                    )
                )

    landmark_names: dict[str, int] = {}
    landmarks = layout.get("landmarks") if isinstance(layout.get("landmarks"), list) else []
    for index, landmark in enumerate(landmarks):
        if not isinstance(landmark, dict) or not _is_numeric_list(landmark.get("position"), 2):
            continue
        center = [float(landmark["position"][0]), float(landmark["position"][1])]
        radius = float(landmark.get("radius", 0.04)) if isinstance(landmark.get("radius", 0.04), (int, float)) else 0.04
        if not point_in_bounds(center, padding=radius):
            issues.append(
                ValidationIssue(
                    "landmark-out-of-bounds",
                    f"layout.landmarks[{index}] must stay inside the declared arena dimensions.",
                    f"layout.landmarks[{index}].position",
                )
            )
        name = str(landmark.get("name") or f"landmark-{index + 1}")
        if name in landmark_names:
            issues.append(
                ValidationIssue(
                    "landmark-name-collision",
                    f"layout.landmarks[{index}] reuses landmark name '{name}'.",
                    f"layout.landmarks[{index}].name",
                )
            )
        landmark_names[name] = index

    zones = layout.get("zones") if isinstance(layout.get("zones"), list) else []
    for index, zone in enumerate(zones):
        if not isinstance(zone, dict):
            continue
        center = zone.get("center")
        size = zone.get("size")
        if not (_is_numeric_list(center, 2) and _is_numeric_list(size, 2)):
            continue
        if any(float(item) <= 0 for item in size):
            issues.append(
                ValidationIssue(
                    "invalid-zone-size",
                    "Zones must define a two-item positive XY size.",
                    f"layout.zones[{index}].size",
                )
            )
            continue
        half_size = [float(size[0]) / 2, float(size[1]) / 2]
        center_point = [float(center[0]), float(center[1])]
        if not point_in_bounds(center_point, padding=max(half_size)):
            issues.append(
                ValidationIssue(
                    "zone-out-of-bounds",
                    f"layout.zones[{index}] must stay inside the declared arena dimensions.",
                    f"layout.zones[{index}]",
                )
            )

    if spawn_xy:
        for item in blocking_objects:
            if _distance_2d(spawn_xy, item["center"]) < clearance_radius + item["radius"]:
                issues.append(
                    ValidationIssue(
                        "spawn-blocked",
                        f"layout.spawn.translation overlaps {item['kind']} #{item['index'] + 1}.",
                        "layout.spawn.translation",
                    )
                )
                break
        else:
            for wall in wall_segments:
                clearance = clearance_radius + wall["thickness"] / 2
                if _distance_point_to_segment(spawn_xy, wall["start"], wall["end"]) < clearance:
                    issues.append(
                        ValidationIssue(
                            "spawn-blocked",
                            f"layout.spawn.translation overlaps wall #{wall['index'] + 1}.",
                            "layout.spawn.translation",
                        )
                    )
                    break

    return issues


def _obstacle_footprint_radius(obstacle: dict[str, Any]) -> float:
    shape = str(obstacle.get("shape", "box"))
    if shape == "cylinder":
        radius = obstacle.get("radius", 0.06)
        return float(radius) if isinstance(radius, (int, float)) else 0.06
    return _box_footprint_radius(obstacle.get("size", [0.1, 0.1, 0.1]))


def _box_footprint_radius(size: Any) -> float:
    if not _is_numeric_list(size, 3):
        return 0.06
    half_x = float(size[0]) / 2
    half_y = float(size[1]) / 2
    return math.hypot(half_x, half_y)


def _distance_point_to_segment(point: list[float], start: list[float], end: list[float]) -> float:
    px, py = float(point[0]), float(point[1])
    sx, sy = float(start[0]), float(start[1])
    ex, ey = float(end[0]), float(end[1])
    dx = ex - sx
    dy = ey - sy
    if abs(dx) <= 1e-9 and abs(dy) <= 1e-9:
        return math.hypot(px - sx, py - sy)
    projection = ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)
    projection = max(0.0, min(1.0, projection))
    closest_x = sx + projection * dx
    closest_y = sy + projection * dy
    return math.hypot(px - closest_x, py - closest_y)


def _segments_intersect_or_overlap(
    left_start: list[float],
    left_end: list[float],
    right_start: list[float],
    right_end: list[float],
) -> bool:
    shared_endpoints = {tuple(round(value, 6) for value in left_start), tuple(round(value, 6) for value in left_end)} & {
        tuple(round(value, 6) for value in right_start),
        tuple(round(value, 6) for value in right_end),
    }
    if shared_endpoints:
        return False

    def orientation(a: list[float], b: list[float], c: list[float]) -> float:
        return (float(b[0]) - float(a[0])) * (float(c[1]) - float(a[1])) - (float(b[1]) - float(a[1])) * (float(c[0]) - float(a[0]))

    def on_segment(a: list[float], b: list[float], c: list[float]) -> bool:
        return (
            min(float(a[0]), float(c[0])) - 1e-9 <= float(b[0]) <= max(float(a[0]), float(c[0])) + 1e-9
            and min(float(a[1]), float(c[1])) - 1e-9 <= float(b[1]) <= max(float(a[1]), float(c[1])) + 1e-9
        )

    o1 = orientation(left_start, left_end, right_start)
    o2 = orientation(left_start, left_end, right_end)
    o3 = orientation(right_start, right_end, left_start)
    o4 = orientation(right_start, right_end, left_end)

    if (o1 > 0 and o2 < 0 or o1 < 0 and o2 > 0) and (o3 > 0 and o4 < 0 or o3 < 0 and o4 > 0):
        return True
    if abs(o1) <= 1e-9 and on_segment(left_start, right_start, left_end):
        return True
    if abs(o2) <= 1e-9 and on_segment(left_start, right_end, left_end):
        return True
    if abs(o3) <= 1e-9 and on_segment(right_start, left_start, right_end):
        return True
    if abs(o4) <= 1e-9 and on_segment(right_start, left_end, right_end):
        return True
    return False


def _recommended_next_edit_ops(spec: ScenarioSpec) -> list[str]:
    layout = spec.layout if isinstance(spec.layout, dict) else {}
    recommendations = ["set_spawn"]
    if spec.scenario.get("kind") == "line-follow":
        recommendations.append("set_line_track")
    if spec.scenario.get("kind") == "waypoint-nav":
        recommendations.extend(["set_waypoints", "set_goal_region"])
    if spec.scenario.get("kind") == "obstacle-avoidance" or layout.get("obstacles"):
        recommendations.extend(["add_obstacle", "update_obstacle"])
    if isinstance(layout.get("walls"), list):
        recommendations.append("add_wall")
    if isinstance(layout.get("landmarks"), list):
        recommendations.append("add_landmark")
    if isinstance(layout.get("zones"), list):
        recommendations.append("add_zone")
    if isinstance(layout.get("props"), list):
        recommendations.append("add_prop")
    return list(dict.fromkeys(recommendations))


def _benchmark_mapping(spec: ScenarioSpec, benchmark_name: str, scenario_def: Any) -> dict[str, Any]:
    return {
        "benchmark_name": benchmark_name,
        "profile": spec.benchmark.get("profile"),
        "duration_s": spec.benchmark.get("duration_s"),
        "target_robot_name": spec.robot.get("name"),
        "target_robot_def": spec.robot.get("def"),
        "default_camera": spec.controller.get("default_camera"),
        "expected_sensor_keys": list(scenario_def.required_sensor_keys) if scenario_def else [],
        "expected_metric_keys": list(scenario_def.required_metric_keys) if scenario_def else [],
        "expected_actuator_keys": list(scenario_def.required_actuator_keys) if scenario_def else [],
    }


def _discover_world_robot_identity(world_path: Path, benchmark_name: str, *, robot_profile: str = "e-puck") -> tuple[str, str]:
    content = world_path.read_text(encoding="utf-8", errors="replace")
    if "front_left_motor" in content and "front_camera" in content:
        def_match = re.search(r"DEF\s+([A-Za-z0-9_]+)\s+Robot\s*{", content)
        robot_def = def_match.group(1) if def_match else _default_robot_def("monsterborg-4wd")
        name_match = re.search(r'name\s+"([^"]+)"', content[def_match.end() : def_match.end() + 600] if def_match else content)
        if name_match:
            return name_match.group(1), robot_def
        scenario_def = get_scenario(benchmark_name, robot_profile="monsterborg-4wd")
        return scenario_def.target_robot_name, robot_def
    def_match = re.search(r"DEF\s+([A-Za-z0-9_]+)\s+E-puck\s*{", content)
    if def_match:
        robot_def = def_match.group(1)
        name_match = re.search(r'name\s+"([^"]+)"', content[def_match.end() : def_match.end() + 400])
        if name_match:
            return name_match.group(1), robot_def
        return get_scenario(benchmark_name, robot_profile=robot_profile).target_robot_name, robot_def
    scenario_def = get_scenario(benchmark_name, robot_profile=robot_profile)
    return scenario_def.target_robot_name, scenario_def.target_robot_def


def _discover_controller_devices(controller_path: Path) -> list[str]:
    try:
        source = controller_path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        tree = ast.parse(source, filename=str(controller_path))
    except SyntaxError:
        matches = re.findall(r'getDevice\(\s*["\']([^"\']+)["\']\s*\)', source)
        return sorted(set(matches))
    devices: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "getDevice":
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            devices.add(first_arg.value)
    return sorted(devices)


def _classify_runtime_failure(*, last_error_code: str | None, status: Any, result_reason: str | None) -> str:
    if not last_error_code and str(status) in {"stopped", "completed", "ready"}:
        return "none"
    if last_error_code == "render-init-failed":
        return "rendering"
    if last_error_code in {"controller-launch-failed", "agent-connect-timeout", "supervisor-connect-timeout", "session-start-timeout"}:
        return "startup"
    if last_error_code == "webots-unexpected-exit":
        return "runtime-exit"
    if result_reason in {"line-loss-threshold-reached", "collision-detected", "target-not-reached", "low-travel-distance", "insufficient-forward-speed"}:
        return "benchmark"
    if str(status) == "failed":
        return "runtime-failure"
    return "none"


def _build_benchmark_summary(*, benchmark_name: str, status: Any, result_reason: str | None, last_error_code: str | None) -> dict[str, Any]:
    return {
        "benchmark_name": benchmark_name,
        "result_reason": result_reason,
        "status": status,
        "last_error_code": last_error_code,
        "rerun_supported": benchmark_name in scenario_registry(),
        "next_step": benchmark_next_step(benchmark_name, result_reason or "completed"),
    }


def _build_telemetry_summary(runtime_summary: dict[str, Any]) -> dict[str, Any]:
    roles: dict[str, dict[str, Any]] = {}
    for role, payload in runtime_summary.items():
        if not isinstance(payload, dict):
            continue
        roles[role] = {
            "connected": bool(payload.get("connected", False)),
            "device_count": int(payload.get("device_count", 0)),
            "state_keys": list(payload.get("state_keys", [])) if isinstance(payload.get("state_keys"), list) else [],
            "sensor_keys": list(payload.get("sensor_keys", [])) if isinstance(payload.get("sensor_keys"), list) else [],
            "metric_keys": list(payload.get("metric_keys", [])) if isinstance(payload.get("metric_keys"), list) else [],
            "actuator_keys": list(payload.get("actuator_keys", [])) if isinstance(payload.get("actuator_keys"), list) else [],
        }
    return {
        "connected_roles": sorted(role for role, payload in roles.items() if payload["connected"]),
        "roles": roles,
    }


def _build_triage_recipe(failure_class: str) -> dict[str, Any]:
    recipes = {
        "none": {
            "focus": "observability",
            "primary_artifacts": ["summary.json", "inspect.json", "log_summary.json"],
            "steps": [
                "Review the replay summary and copied artifacts.",
                "Rerun the matching benchmark if you need fresh telemetry.",
            ],
        },
        "rendering": {
            "focus": "rendering",
            "primary_artifacts": ["webots.stderr.log", "daemon.stderr.log", "runtime_environment.json"],
            "steps": [
                "Confirm the runtime is running in an interactive desktop session.",
                "Inspect Webots stderr for OpenGL or rendering initialization failures.",
            ],
        },
        "startup": {
            "focus": "startup",
            "primary_artifacts": ["daemon.stderr.log", "inspect.json", "session.json"],
            "steps": [
                "Check controller/world paths and the controller contract.",
                "Inspect daemon and controller stderr logs for runtime connection failures.",
            ],
        },
        "runtime-exit": {
            "focus": "runtime-exit",
            "primary_artifacts": ["webots.stdout.log", "webots.stderr.log", "summary.json"],
            "steps": [
                "Inspect Webots stdout/stderr around the exit point.",
                "Rerun the same scenario with fresh logs if the exit reason stays unclear.",
            ],
        },
        "benchmark": {
            "focus": "benchmark",
            "primary_artifacts": ["summary.json", "inspect.json", "log_summary.json"],
            "steps": [
                "Inspect benchmark-facing telemetry keys and copied log summaries.",
                "Tune controller behavior and rerun the benchmark with the same scenario profile.",
            ],
        },
        "runtime-failure": {
            "focus": "runtime",
            "primary_artifacts": ["summary.json", "daemon.stderr.log", "inspect.json"],
            "steps": [
                "Inspect the last structured runtime error and copied daemon logs.",
                "Rerun the same session path after addressing the reported failure.",
            ],
        },
    }
    return recipes.get(failure_class, recipes["runtime-failure"])


def _default_robot_def(robot_profile: str) -> str:
    return "MONSTERBORG" if robot_profile == "monsterborg-4wd" else "EPUCK"


def _default_robot_name(kind: str, scenario_name: str, *, robot_profile: str = "e-puck") -> str:
    prefix = "monsterborg" if robot_profile == "monsterborg-4wd" else "epuck"
    return f"{prefix}-{scenario_name}-{kind}"


def _default_template_for_kind(kind: str, *, robot_profile: str = "e-puck") -> str:
    return get_robot_profile(robot_profile).default_templates[kind]


def _discover_world_robot_profile(world_path: Path) -> str:
    content = world_path.read_text(encoding="utf-8", errors="replace").lower()
    if "front_left_motor" in content or "monsterborg" in content or "front_camera" in content:
        return "monsterborg-4wd"
    return "e-puck"


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
