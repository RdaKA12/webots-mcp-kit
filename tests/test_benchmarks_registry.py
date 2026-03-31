from __future__ import annotations

from webots_mcp_kit.benchmarks import scenario_names, scenario_registry


def test_benchmark_registry_contains_two_examples() -> None:
    names = scenario_names()
    assert "line-follower" in names
    assert "obstacle-avoidance" in names
    registry = scenario_registry()
    assert registry["line-follower"].world.exists()
    assert registry["obstacle-avoidance"].controller.exists()
