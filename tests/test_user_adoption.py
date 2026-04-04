from __future__ import annotations

from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (_root() / relative_path).read_text(encoding="utf-8")


def test_install_and_verify_scripts_exist() -> None:
    root = _root()
    assert (root / "scripts" / "install.ps1").exists()
    assert (root / "scripts" / "verify_install.ps1").exists()
    verify_script = _read("scripts/verify_install.ps1")
    assert "GITHUB_ACTIONS" in verify_script
    assert "GitHub-hosted Windows runners are not a supported interactive Webots runtime." in verify_script


def test_readme_prefers_pipx_and_lists_support_boundaries() -> None:
    content = _read("README.md")
    assert "## Support Matrix" in content
    assert "## Unsupported Matrix" in content
    assert "pipx install webots-mcp-kit" in content
    assert "interactive-webots" in content
    assert "Webots `R2025a`" in content
    assert "Python `3.11+`" in content
    assert "`e-puck`" in content
    assert "[Troubleshooting](./docs/troubleshooting.md)" in content
    assert "## Docs Map" in content
    assert content.index("pipx install webots-mcp-kit") < content.index("python -m venv .venv")


def test_install_docs_reference_scripts_and_pipx_first() -> None:
    first_hour = _read("docs/first-hour-guide.md")
    install_ref = _read("docs/pypi-install-and-upgrade.md")
    troubleshooting = _read("docs/troubleshooting.md")

    assert "scripts\\install.ps1" in first_hour
    assert "scripts\\verify_install.ps1" in first_hour
    assert "pipx install webots-mcp-kit" in install_ref
    assert "scripts\\install.ps1" in install_ref
    assert "scripts\\verify_install.ps1" in install_ref
    assert install_ref.index("pipx install webots-mcp-kit") < install_ref.index("python -m venv .venv")

    for heading in (
        "## Webots Not Found / `WEBOTS_HOME`",
        "## Unsupported Runtime Mode / Non-Interactive Session",
        "## Render / Init Failure",
        "## C++ Controller Compile Failure",
        "## MCP Connection Failure",
        "## Benchmark Failure After Successful Install",
        "## MonsterBorg Physical Adapter Verification Failure",
    ):
        assert heading in troubleshooting
    assert troubleshooting.count("Symptom:") == 7
    assert troubleshooting.count("Likely cause:") == 7
    assert troubleshooting.count("Exact commands to diagnose:") == 7
    assert troubleshooting.count("Exact next action:") == 7


def test_onboarding_and_template_files_cover_user_adoption_paths() -> None:
    onboarding = _read("docs/onboarding-flows.md")
    bug_report = _read(".github/ISSUE_TEMPLATE/bug-report.yml")
    install_problem = _read(".github/ISSUE_TEMPLATE/install-problem.yml")
    runtime_smoke = _read(".github/ISSUE_TEMPLATE/runtime-smoke-failure.yml")
    pr_template = _read(".github/PULL_REQUEST_TEMPLATE.md")
    release_template = _read(".github/release-template.md")

    for heading in (
        "## 1. Connect An Agent",
        "## 2. Write Or Edit A Controller",
        "## 3. Inspect Or Edit A World",
        "## 4. Import And Replay",
    ):
        assert heading in onboarding

    assert "webots-kit --version" in bug_report
    assert "doctor --json" in bug_report
    assert "pipx" in bug_report
    assert "interactive-webots" in bug_report

    assert "verify_install.ps1 output" in install_problem
    assert "Webots version and path" in install_problem
    assert "Runtime smoke failure" in runtime_smoke
    assert "doctor --json" in runtime_smoke
    assert "artifacts" in runtime_smoke

    assert "install or onboarding path checked if user-facing behavior changed" in pr_template
    assert "`README` and docs updated if user-facing behavior changed" in pr_template
    assert "`verify_install` path checked if install or packaging behavior changed" in pr_template

    assert "## Onboarding / Install Impact" in release_template
    assert "## Troubleshooting Impact" in release_template
    assert "## Quickstart Changes" in release_template
