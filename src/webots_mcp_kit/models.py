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
    world: str
    mode: str
    render: bool
    robot_controller: str
    created_at: str
    session_dir: str
    artifacts_dir: str

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

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pass"] = payload.pop("passed")
        return payload


def repo_example_world() -> Path:
    return Path(__file__).resolve().parents[2] / "examples" / "line-follower" / "worlds" / "line_follower_benchmark.wbt"


def repo_example_controller() -> Path:
    return Path(__file__).resolve().parents[2] / "examples" / "line-follower" / "controllers" / "line_follower_agent.py"
