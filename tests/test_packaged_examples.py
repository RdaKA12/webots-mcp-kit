from __future__ import annotations

from webots_mcp_kit.models import bundled_example_root, package_example_root, repo_example_root


def test_packaged_example_root_exists() -> None:
    root = package_example_root()
    assert (root / "line-follower" / "worlds" / "line_follower_benchmark.wbt").exists()
    assert (root / "waypoint-nav" / "controllers" / "waypoint_nav_agent.py").exists()
    assert (root / "monsterborg" / "line-follower" / "worlds" / "monsterborg_line_follower_benchmark.wbt").exists()
    assert (root / "monsterborg" / "line-follower" / "variants" / "baseline.webots-kit.scenario.json").exists()
    assert (root / "monsterborg" / "line-follower" / "variants" / "camera-degradation.webots-kit.scenario.json").exists()
    assert (root / "monsterborg" / "obstacle-avoidance" / "variants" / "baseline.webots-kit.scenario.json").exists()
    assert (root / "monsterborg" / "obstacle-avoidance" / "variants" / "range-noise.webots-kit.scenario.json").exists()
    assert (root / "monsterborg" / "waypoint-nav" / "controllers" / "monsterborg_waypoint_nav_agent.py").exists()
    assert (root / "monsterborg" / "waypoint-nav" / "variants" / "baseline.webots-kit.scenario.json").exists()
    assert (root / "monsterborg" / "waypoint-nav" / "variants" / "imu-drift.webots-kit.scenario.json").exists()
    assert (root / "monsterborg" / "physical-captures" / "line-follower.capture.json").exists()
    assert (root / "monsterborg" / "physical-captures" / "obstacle-avoidance.capture.json").exists()
    assert (root / "monsterborg" / "physical-captures" / "waypoint-nav.capture.json").exists()
    assert (root / "getting-started" / "line-follower" / "starter.json").exists()
    assert (root / "getting-started" / "monsterborg-line-follower" / "starter.json").exists()
    assert (root / "getting-started" / "world-edit" / "README.md").exists()


def test_bundled_example_root_prefers_repo_or_package() -> None:
    root = bundled_example_root()
    assert root in {repo_example_root(), package_example_root()}
