from __future__ import annotations

from webots_mcp_kit.benchmarks import scenario_names, scenario_registry


def test_benchmark_registry_contains_bundled_examples() -> None:
    names = scenario_names()
    assert "line-follower" in names
    assert "obstacle-avoidance" in names
    assert "waypoint-nav" in names
    registry = scenario_registry()
    assert registry["line-follower"].world.exists()
    assert registry["obstacle-avoidance"].controller.exists()
    assert registry["waypoint-nav"].controller.exists()
    assert registry["waypoint-nav"].benchmark_thresholds["target_position"] == (0.55, 0.0)


def test_monsterborg_benchmark_registry_contains_bundled_examples() -> None:
    registry = scenario_registry(robot_profile="monsterborg-4wd")
    assert registry["line-follower"].world.exists()
    assert registry["obstacle-avoidance"].controller.exists()
    assert registry["waypoint-nav"].controller.exists()
    assert registry["line-follower"].robot_profile == "monsterborg-4wd"
    assert registry["line-follower"].robot_family == "monsterborg"
    assert registry["waypoint-nav"].benchmark_thresholds["target_position"] == (1.35, 0.0)
