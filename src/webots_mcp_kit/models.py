from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SessionManifest:
    session_id: str
    host: str
    port: int
    daemon_pid: int
    status: str
    scenario: str
    world: str
    mode: str
    render: bool
    robot_controller: str
    target_robot_name: str
    target_robot_def: str
    created_at: str
    session_dir: str
    artifacts_dir: str
    stopped_at: str | None = None
    last_error: str | None = None
    last_error_code: str | None = None
    last_error_details: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)
    runtime_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RuntimeSnapshot:
    role: str
    name: str
    connected: bool = False
    devices: list[dict[str, Any]] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    sensors: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    actuators: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BenchmarkReport:
    benchmark: str
    world: str
    controller: str
    session_mode: str
    sim_time_s: float
    steps: int
    line_loss_events: int
    max_line_loss_streak: int
    mean_center_error: float
    ir_balance_error: float
    passed: bool
    artifacts: dict[str, str]
    notes: list[str]
    extra_metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pass"] = payload.pop("passed")
        return payload


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    name: str
    description: str
    world: Path
    controller: Path
    target_robot_name: str
    target_robot_def: str
    benchmark_kind: str
    default_camera: str | None = None
    required_sensor_keys: tuple[str, ...] = ()
    required_metric_keys: tuple[str, ...] = ()
    required_actuator_keys: tuple[str, ...] = ()
    benchmark_thresholds: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProjectManifest:
    schema_version: int
    toolkit_version: str
    project_name: str
    created_at: str
    root_dir: str
    scenarios_dir: str
    runtime_runner_label: str = "interactive-webots"
    robot_family: str = "e-puck"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScenarioSpec:
    schema_version: int
    project: dict[str, Any]
    scenario: dict[str, Any]
    robot: dict[str, Any]
    environment: dict[str, Any]
    layout: dict[str, Any]
    task: dict[str, Any]
    controller: dict[str, Any]
    benchmark: dict[str, Any]
    sensors: dict[str, Any] = field(default_factory=dict)
    actuators: dict[str, Any] = field(default_factory=dict)
    import_source: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScenarioSpec":
        return cls(
            schema_version=int(payload.get("schema_version", 1)),
            project=payload.get("project") if isinstance(payload.get("project"), dict) else {},
            scenario=payload.get("scenario") if isinstance(payload.get("scenario"), dict) else {},
            robot=payload.get("robot") if isinstance(payload.get("robot"), dict) else {},
            environment=payload.get("environment") if isinstance(payload.get("environment"), dict) else {},
            layout=payload.get("layout") if isinstance(payload.get("layout"), dict) else {},
            task=payload.get("task") if isinstance(payload.get("task"), dict) else {},
            controller=payload.get("controller") if isinstance(payload.get("controller"), dict) else {},
            benchmark=payload.get("benchmark") if isinstance(payload.get("benchmark"), dict) else {},
            sensors=payload.get("sensors") if isinstance(payload.get("sensors"), dict) else {},
            actuators=payload.get("actuators") if isinstance(payload.get("actuators"), dict) else {},
            import_source=payload.get("import_source") if isinstance(payload.get("import_source"), dict) else {},
        )


@dataclass(slots=True)
class GeneratedScenario:
    spec_path: str
    project_root: str
    scenario_dir: str
    scenario_name: str
    scenario_kind: str
    benchmark_name: str
    world_path: str
    controller_path: str
    benchmark_config_path: str
    target_robot_name: str
    target_robot_def: str
    default_camera: str | None
    suggested_session_command: str
    suggested_benchmark_command: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SessionExport:
    export_dir: str
    session_id: str
    manifest_path: str
    inspect_path: str
    log_inventory_path: str
    log_summary_path: str
    runtime_environment_path: str
    copied_logs: list[str] = field(default_factory=list)
    copied_artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def repo_example_root() -> Path:
    return Path(__file__).resolve().parents[2] / "examples"


def package_example_root() -> Path:
    return Path(__file__).resolve().parent / "examples"


def bundled_example_root() -> Path:
    repo_root = repo_example_root()
    if repo_root.exists():
        return repo_root
    return package_example_root()
