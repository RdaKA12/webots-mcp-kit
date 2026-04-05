from __future__ import annotations

from pathlib import Path


WORKFLOWS = (
    ".github/workflows/package-ci.yml",
    ".github/workflows/windows-ci.yml",
    ".github/workflows/windows-runtime-smoke.yml",
    ".github/workflows/monsterborg-physical-smoke.yml",
    ".github/workflows/release.yml",
)


def test_windows_workflows_do_not_use_bare_pip_install() -> None:
    root = Path(__file__).resolve().parents[1]
    for relative_path in WORKFLOWS:
        content = (root / relative_path).read_text(encoding="utf-8")
        assert "\npip install" not in content, f"Workflow uses bare pip install: {relative_path}"


def test_runtime_workflow_bypasses_powershell_execution_policy() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/windows-runtime-smoke.yml").read_text(encoding="utf-8")
    assert "-ExecutionPolicy Bypass" in content


def test_runtime_workflow_resolves_registry_python() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/windows-runtime-smoke.yml").read_text(encoding="utf-8")
    assert "Resolve runner Python" in content
    assert "HKCU:\\SOFTWARE\\Python\\PythonCore\\3.11\\InstallPath" in content
    assert "HKLM:\\SOFTWARE\\Python\\PythonCore\\3.11\\InstallPath" in content
    assert "steps.python.outputs.python_exe" in content
    assert "Lib\\encodings\\__init__.py" in content
    assert "C:\\Users" in content
    assert "D:\\actions-runner\\python311-shared" in content
    assert "Test-Path -LiteralPath $candidate -ErrorAction Stop" in content
    assert "python311-bootstrap" in content
    assert "python-3.11.9-amd64.exe" in content


def test_runtime_workflow_does_not_depend_on_console_script_path() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/windows-runtime-smoke.yml").read_text(encoding="utf-8")
    assert "webots-kit doctor --json" not in content
    assert "-m webots_mcp_kit.cli doctor --json" in content
    assert "-m ensurepip --upgrade" in content


def test_runtime_workflow_does_not_use_unquoted_ampersand_run_lines() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/windows-runtime-smoke.yml").read_text(encoding="utf-8")
    assert "run: & " not in content


def test_runtime_workflow_handles_missing_python_output_in_diagnostics() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/windows-runtime-smoke.yml").read_text(encoding="utf-8")
    assert "python_exe output was empty" in content


def test_runtime_workflow_uses_interactive_runner_label() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/windows-runtime-smoke.yml").read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, windows, interactive-webots]" in content
    assert '"src/webots_mcp_kit/scenario_ops.py"' in content
    assert '"src/webots_mcp_kit/world_ops.py"' in content
    assert '"src/webots_mcp_kit/controller_authoring.py"' in content
    assert '"src/webots_mcp_kit/robot_profiles.py"' in content
    assert '"src/webots_mcp_kit/monsterborg_adapter.py"' in content
    assert '"examples/monsterborg/**"' in content


def test_runtime_workflow_includes_generated_scenario_smoke() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/windows-runtime-smoke.yml").read_text(encoding="utf-8")
    assert "Generated scenario runtime smoke" in content
    assert "-k generated_scenario_smoke" in content
    assert "MonsterBorg line-follow repeatability runtime smoke" in content
    assert "-k monsterborg_line_follow_variants_repeatability_smoke" in content
    assert "MonsterBorg obstacle repeatability runtime smoke" in content
    assert "-k monsterborg_obstacle_variants_repeatability_smoke" in content
    assert "MonsterBorg waypoint repeatability runtime smoke" in content
    assert "-k monsterborg_waypoint_variants_repeatability_smoke" in content
    assert "Generated world authoring runtime smoke" in content
    assert "-k generated_world_edit_smoke" in content


def test_runtime_workflow_includes_imported_project_smoke() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/windows-runtime-smoke.yml").read_text(encoding="utf-8")
    assert "Imported project runtime smoke" in content
    assert "-k imported_project_smoke" in content
    assert "MonsterBorg line-follow robustness runtime smoke" in content
    assert "-k monsterborg_line_follow_robustness_smoke" in content
    assert "MonsterBorg obstacle robustness runtime smoke" in content
    assert "-k monsterborg_obstacle_robustness_smoke" in content
    assert "MonsterBorg waypoint robustness runtime smoke" in content
    assert "-k monsterborg_waypoint_robustness_smoke" in content
    assert "Imported world authoring runtime smoke" in content
    assert "-k imported_world_edit_smoke" in content
    assert "MCP authoring contract smoke" in content
    assert "-k mcp_authoring_contract_smoke" in content
    assert "MCP authoring contract smoke" in content
    assert "-k mcp_authoring_contract_smoke" in content


def test_release_and_package_workflows_use_public_verify_path() -> None:
    root = Path(__file__).resolve().parents[1]
    package_content = (root / ".github/workflows/package-ci.yml").read_text(encoding="utf-8")
    release_content = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "User adoption static checks" in package_content
    assert "tests/test_user_adoption.py" in package_content
    assert "tests/test_team_adoption.py" in package_content
    assert "MonsterBorg task hardening checks" in package_content
    assert "tests/test_monsterborg_navigation.py" in package_content
    assert "tests/test_monsterborg_physical_gate.py" in package_content
    assert "python scripts/clean_user_acceptance.py --workspace package-smoke --profile hosted-safe" in package_content
    assert "powershell -ExecutionPolicy Bypass -File .\\scripts\\verify_install.ps1 -Runtime -Output .\\verify-install.json" in release_content
    assert "powershell -ExecutionPolicy Bypass -File .\\scripts\\upgrade_check.ps1 -Workspace .\\upgrade-check -Runtime -Output .\\upgrade-check.json" in release_content
    assert "powershell -ExecutionPolicy Bypass -File .\\scripts\\verify_install.ps1 -RobotProfile monsterborg-4wd -Runtime -Output .\\verify-install-monsterborg.json" in release_content
    assert "powershell -ExecutionPolicy Bypass -File .\\scripts\\upgrade_check.ps1 -Workspace .\\monsterborg-upgrade-check -RobotProfile monsterborg-4wd -Runtime -Output .\\monsterborg-upgrade-check.json" in release_content
    assert "monsterborg-physical-gate:" in release_content
    assert "vars.MONSTERBORG_PHYSICAL_GATE == 'enabled'" in release_content
    assert "!contains(github.ref_name, 'alpha')" in release_content
    assert "needs.monsterborg-physical-gate.result == 'skipped'" in release_content
    assert "always() && needs.build.result == 'success'" in release_content
    assert release_content.count("verify_install.ps1 -Runtime -Output") >= 2
    assert release_content.count("upgrade_check.ps1 -Workspace .\\upgrade-check -Runtime -Output") >= 2


def test_release_install_smoke_jobs_checkout_repo_for_verify_script() -> None:
    root = Path(__file__).resolve().parents[1]
    release_content = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "test-install-testpypi:" in release_content
    assert "test-install-pypi:" in release_content
    assert release_content.count("uses: actions/checkout@v5") >= 2


def test_windows_ci_includes_team_upgrade_smoke() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/windows-ci.yml").read_text(encoding="utf-8")
    assert "Public verify JSON smoke" in content
    assert "verify_install.ps1 -Json -Output .\\verify-install.json" in content
    assert "MonsterBorg verify JSON smoke" in content
    assert "verify_install.ps1 -RobotProfile monsterborg-4wd -Json -Output .\\verify-install-monsterborg.json" in content
    assert "Team upgrade smoke" in content
    assert "upgrade_check.ps1 -Workspace .\\upgrade-check -Runtime -Output .\\upgrade-check.json" in content
    assert "MonsterBorg team upgrade smoke" in content
    assert "upgrade_check.ps1 -Workspace .\\monsterborg-upgrade-check -RobotProfile monsterborg-4wd -Runtime -Output .\\monsterborg-upgrade-check.json" in content


def test_monsterborg_physical_workflow_exists_with_designated_runner_and_gate_steps() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/monsterborg-physical-smoke.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in content
    assert "push:" not in content
    assert "pull_request:" not in content
    assert "runs-on: [self-hosted, linux, monsterborg-physical]" in content
    assert "python3 scripts/monsterborg_physical_verify.py --json" in content
    assert "tests/test_monsterborg_physical_gate.py" in content
    assert "python3 -m pip install -e .[dev]" in content


def test_monsterborg_physical_runner_setup_assets_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    setup_script = (root / "scripts" / "setup_monsterborg_physical_runner.sh").read_text(encoding="utf-8")
    runner_doc = (root / "docs" / "monsterborg-physical-runner.md").read_text(encoding="utf-8")
    assert "--repo-url" in setup_script
    assert "--token" in setup_script
    assert "monsterborg-physical" in setup_script
    assert "actions/runner/releases/latest" in setup_script
    assert "this is not general Linux runtime support" in runner_doc
    assert "self-hosted" in runner_doc
    assert "monsterborg-physical" in runner_doc
