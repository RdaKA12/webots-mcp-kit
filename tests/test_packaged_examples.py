from __future__ import annotations

from webots_mcp_kit.models import bundled_example_root, package_example_root, repo_example_root


def test_packaged_example_root_exists() -> None:
    root = package_example_root()
    assert (root / "line-follower" / "worlds" / "line_follower_benchmark.wbt").exists()
    assert (root / "waypoint-nav" / "controllers" / "waypoint_nav_agent.py").exists()


def test_bundled_example_root_prefers_repo_or_package() -> None:
    root = bundled_example_root()
    assert root in {repo_example_root(), package_example_root()}
