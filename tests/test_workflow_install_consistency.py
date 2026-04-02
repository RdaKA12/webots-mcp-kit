from __future__ import annotations

from pathlib import Path


WORKFLOWS = (
    ".github/workflows/package-ci.yml",
    ".github/workflows/windows-ci.yml",
    ".github/workflows/windows-runtime-smoke.yml",
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


def test_runtime_workflow_includes_generated_scenario_smoke() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/windows-runtime-smoke.yml").read_text(encoding="utf-8")
    assert "Generated scenario runtime smoke" in content
    assert "-k generated_scenario_smoke" in content


def test_release_and_package_workflows_smoke_project_and_scenario_commands() -> None:
    root = Path(__file__).resolve().parents[1]
    package_content = (root / ".github/workflows/package-ci.yml").read_text(encoding="utf-8")
    release_content = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
    for content in (package_content, release_content):
        assert "webots-kit controller scaffold" in content
        assert "webots-kit controller validate" in content
        assert "webots-kit project init" in content
        assert "webots-kit project import" in content
        assert "webots-kit scenario init" in content
        assert "webots-kit scenario validate" in content
        assert "webots-kit scenario build" in content
