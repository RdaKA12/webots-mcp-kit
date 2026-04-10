from __future__ import annotations

from webots_mcp_kit.models import bundled_example_root, package_example_root, repo_example_root


MONSTERBORG_WORLD_PATHS = (
    ("monsterborg", "line-follower", "worlds", "monsterborg_line_follower_benchmark.wbt"),
    ("monsterborg", "obstacle-avoidance", "worlds", "monsterborg_obstacle_avoidance_benchmark.wbt"),
    ("monsterborg", "waypoint-nav", "worlds", "monsterborg_waypoint_nav_benchmark.wbt"),
    ("getting-started", "monsterborg-world-edit", "worlds", "editable_world.wbt"),
    ("getting-started", "monsterborg-import-replay", "worlds", "import_world.wbt"),
)


def test_packaged_example_root_exists() -> None:
    root = package_example_root()
    assert (root / "line-follower" / "worlds" / "line_follower_benchmark.wbt").exists()
    assert (root / "waypoint-nav" / "controllers" / "waypoint_nav_agent.py").exists()
    assert (root / "monsterborg" / "line-follower" / "worlds" / "monsterborg_line_follower_benchmark.wbt").exists()
    assert (root / "monsterborg" / "line-follower" / "variants" / "baseline.webots-kit.scenario.json").exists()
    assert (root / "monsterborg" / "line-follower" / "variants" / "camera-degradation.webots-kit.scenario.json").exists()
    assert (root / "monsterborg" / "line-follower" / "protos" / "MonsterBorg4WD.proto").exists()
    assert (root / "monsterborg" / "obstacle-avoidance" / "variants" / "baseline.webots-kit.scenario.json").exists()
    assert (root / "monsterborg" / "obstacle-avoidance" / "variants" / "range-noise.webots-kit.scenario.json").exists()
    assert (root / "monsterborg" / "obstacle-avoidance" / "protos" / "MonsterBorg4WD.proto").exists()
    assert (root / "monsterborg" / "waypoint-nav" / "controllers" / "monsterborg_waypoint_nav_agent.py").exists()
    assert (root / "monsterborg" / "waypoint-nav" / "variants" / "baseline.webots-kit.scenario.json").exists()
    assert (root / "monsterborg" / "waypoint-nav" / "variants" / "imu-drift.webots-kit.scenario.json").exists()
    assert (root / "monsterborg" / "waypoint-nav" / "protos" / "MonsterBorg4WD.proto").exists()
    assert (root / "monsterborg" / "physical-captures" / "line-follower.capture.json").exists()
    assert (root / "monsterborg" / "physical-captures" / "obstacle-avoidance.capture.json").exists()
    assert (root / "monsterborg" / "physical-captures" / "waypoint-nav.capture.json").exists()
    assert (root / "getting-started" / "line-follower" / "starter.json").exists()
    assert (root / "getting-started" / "monsterborg-line-follower" / "starter.json").exists()
    assert (root / "getting-started" / "world-edit" / "README.md").exists()
    assert (root / "getting-started" / "monsterborg-world-edit" / "protos" / "MonsterBorg4WD.proto").exists()
    assert (root / "getting-started" / "monsterborg-import-replay" / "protos" / "MonsterBorg4WD.proto").exists()


def test_bundled_example_root_prefers_repo_or_package() -> None:
    root = bundled_example_root()
    assert root in {repo_example_root(), package_example_root()}


def test_monsterborg_example_worlds_use_reference_proto() -> None:
    for root in (repo_example_root(), package_example_root()):
        for parts in MONSTERBORG_WORLD_PATHS:
            world_path = root.joinpath(*parts)
            content = world_path.read_text(encoding="utf-8")
            assert 'EXTERNPROTO "../protos/MonsterBorg4WD.proto"' in content
            assert "DEF MONSTERBORG MonsterBorg4WD {" in content
            assert "DEF MONSTERBORG Robot {" not in content
