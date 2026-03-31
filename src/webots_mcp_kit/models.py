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


def repo_example_root() -> Path:
    return Path(__file__).resolve().parents[2] / "examples"


def package_example_root() -> Path:
    return Path(__file__).resolve().parent / "examples"


def bundled_example_root() -> Path:
    repo_root = repo_example_root()
    if repo_root.exists():
        return repo_root
    return package_example_root()
