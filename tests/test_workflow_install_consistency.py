from __future__ import annotations

from pathlib import Path


WORKFLOWS = (
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


def test_runtime_workflow_does_not_depend_on_console_script_path() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/windows-runtime-smoke.yml").read_text(encoding="utf-8")
    assert "webots-kit doctor --json" not in content
    assert "-m webots_mcp_kit.cli doctor --json" in content


def test_runtime_workflow_does_not_use_unquoted_ampersand_run_lines() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/windows-runtime-smoke.yml").read_text(encoding="utf-8")
    assert "run: & " not in content
