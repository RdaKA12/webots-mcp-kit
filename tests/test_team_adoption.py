from __future__ import annotations

import json
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (_root() / relative_path).read_text(encoding="utf-8")


def test_team_scripts_exist() -> None:
    root = _root()
    assert (root / "scripts" / "bootstrap_workspace.ps1").exists()
    assert (root / "scripts" / "upgrade_check.ps1").exists()
    verify_script = _read("scripts/verify_install.ps1")
    assert "[switch]$Json" in verify_script
    assert "[string]$Output" in verify_script
    assert "[string]$RobotProfile" in verify_script
    bootstrap_script = _read("scripts/bootstrap_workspace.ps1")
    assert "[string]$Starter" in bootstrap_script
    assert "[string]$Destination" in bootstrap_script
    upgrade_script = _read("scripts/upgrade_check.ps1")
    assert "verify_install.ps1" in upgrade_script
    assert "bootstrap_workspace.ps1" in upgrade_script
    assert "[string]$RobotProfile" in upgrade_script


def test_getting_started_workspaces_exist_with_expected_files() -> None:
    root = _root() / "examples" / "getting-started"
    starters = {
        "line-follower": ["README.md", "starter.json", "controllers/demo_agent.py"],
        "controller-edit": ["README.md", "starter.json", "controllers/demo_agent.py", "plans/controller-edit.json"],
        "world-edit": ["README.md", "starter.json", "worlds/editable_world.wbt", "plans/world-edit.json"],
        "import-replay": ["README.md", "starter.json", "worlds/import_world.wbt", "controllers/import_agent.py"],
        "monsterborg-line-follower": ["README.md", "starter.json", "controllers/demo_agent.py"],
        "monsterborg-controller-edit": ["README.md", "starter.json", "controllers/demo_agent.py", "plans/controller-edit.json"],
        "monsterborg-world-edit": ["README.md", "starter.json", "worlds/editable_world.wbt", "plans/world-edit.json"],
        "monsterborg-import-replay": ["README.md", "starter.json", "worlds/import_world.wbt", "controllers/import_agent.py"],
    }
    for starter, files in starters.items():
        starter_root = root / starter
        assert starter_root.exists(), starter
        for relative_path in files:
            assert (starter_root / relative_path).exists(), f"Missing {starter}/{relative_path}"
        metadata = json.loads((starter_root / "starter.json").read_text(encoding="utf-8"))
        assert metadata["name"] == starter
        assert metadata["recommended_commands"]
        assert metadata["expected_green"]


def test_readme_and_docs_reference_team_flows_and_scripts() -> None:
    readme = _read("README.md")
    onboarding = _read("docs/onboarding-flows.md")
    first_hour = _read("docs/first-hour-guide.md")
    install_ref = _read("docs/pypi-install-and-upgrade.md")

    assert "## For Teams" in readme
    assert "[Team flows](./docs/team-flows.md)" in readme
    assert "monsterborg-line-follower" in readme
    assert "[Upgrade guide](./docs/upgrade-guide.md)" in readme
    assert "bootstrap_workspace.ps1" in readme
    assert "upgrade_check.ps1" in readme

    assert "Team route map" in onboarding
    assert "[Team flows](./team-flows.md)" in onboarding
    assert "bootstrap_workspace.ps1" in first_hour
    assert "upgrade_check.ps1" in install_ref
    assert "[Version policy](./version-policy.md)" in install_ref


def test_release_and_ci_reference_upgrade_checks() -> None:
    package_ci = _read(".github/workflows/package-ci.yml")
    release = _read(".github/workflows/release.yml")
    windows_ci = _read(".github/workflows/windows-ci.yml")
    runtime_smoke = _read(".github/workflows/windows-runtime-smoke.yml")
    release_checklist = _read("docs/release-checklist.md")
    release_template = _read(".github/release-template.md")

    assert "tests/test_team_adoption.py" in package_ci
    assert "upgrade_check.ps1" in release
    assert "verify_install.ps1 -Runtime -Output" in release
    assert "upgrade_check.ps1 -Workspace .\\upgrade-check -Runtime -Output .\\upgrade-check.json" in release
    assert "upgrade_check.ps1" in windows_ci
    assert '"examples/getting-started/**"' in runtime_smoke
    assert "starter workspace smoke" in release_checklist.lower()
    assert "upgrade_check.ps1" in release_checklist
    assert "## Team Upgrade Checklist" in release_template
