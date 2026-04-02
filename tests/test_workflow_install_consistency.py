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
