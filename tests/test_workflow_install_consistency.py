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


def test_runtime_workflow_uses_py_launcher() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/windows-runtime-smoke.yml").read_text(encoding="utf-8")
    assert "py -3.11" in content
