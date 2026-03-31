from __future__ import annotations

from pathlib import Path

from .models import ScenarioDefinition, repo_example_root


def _examples_root() -> Path:
    return repo_example_root()


def scenario_registry() -> dict[str, ScenarioDefinition]:
    root = _examples_root()
    return {
        "line-follower": ScenarioDefinition(
            name="line-follower",
            description="Follow a high-contrast floor line with a camera-based controller.",
            world=root / "line-follower" / "worlds" / "line_follower_benchmark.wbt",
            controller=root / "line-follower" / "controllers" / "line_follower_agent.py",
            target_robot_name="epuck-line-follower",
            target_robot_def="EPUCK",
            benchmark_kind="line-follower",
        ),
        "obstacle-avoidance": ScenarioDefinition(
            name="obstacle-avoidance",
            description="Avoid arena obstacles using the e-puck proximity sensors.",
            world=root / "obstacle-avoidance" / "worlds" / "obstacle_avoidance_benchmark.wbt",
            controller=root / "obstacle-avoidance" / "controllers" / "obstacle_avoidance_agent.py",
            target_robot_name="epuck-obstacle-agent",
            target_robot_def="EPUCK",
            benchmark_kind="obstacle-avoidance",
        ),
    }


def get_scenario(name: str) -> ScenarioDefinition:
    registry = scenario_registry()
    if name not in registry:
        available = ", ".join(sorted(registry))
        raise KeyError(f"Unknown scenario '{name}'. Available scenarios: {available}")
    return registry[name]


def scenario_names() -> list[str]:
    return sorted(scenario_registry())
