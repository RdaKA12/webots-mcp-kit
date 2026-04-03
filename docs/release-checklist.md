# Release Checklist

## Before tagging

- `python -m pytest -q`
- hosted CI is green
- hosted MCP smoke is green
- interactive self-hosted runtime smoke is green if runtime code changed
- latest `interactive-webots` runner runtime smoke passed in a logged-in desktop session
- generated-scenario runtime smoke passed on the interactive runner
- generated-world authoring runtime smoke passed on the interactive runner when authoring code changed
- richer generated-world authoring smoke for `walls`, `landmarks`, `zones`, and `props` passed on the interactive runner when `scenario_ops` changed
- imported-world authoring runtime smoke passed on the interactive runner when authoring code changed
- MCP authoring/editing contract smoke passed when `mcp_server`, controller authoring, or world authoring code changed
- package build and `twine check` are green
- TestPyPI install smoke passes through the public `verify_install.ps1` path on the hosted Windows runner
- PyPI install smoke passes through the public `verify_install.ps1` path on the hosted Windows runner
- starter workspace smoke is green through `bootstrap_workspace.ps1` or `upgrade_check.ps1`
- team upgrade smoke is green through `powershell -ExecutionPolicy Bypass -File .\scripts\upgrade_check.ps1 -Workspace <path> -Runtime`
- real runtime benchmark proof still comes from the self-hosted `interactive-webots` runtime smoke workflow
- README quickstart has been rerun once from a clean machine or clean virtual environment
- changelog and README version notes are updated

## Historical pre-`v1.0.0` hardening gate

- at least a few consecutive `v0.10.x` patch releases have passed the GitHub Release, TestPyPI, and PyPI flow cleanly
- hosted CI stays green
- interactive runtime smoke stays green on the `interactive-webots` runner
- package build stays green
- PyPI install smoke stays green
- generated-scenario smoke stays green
- imported-project basic runtime smoke stays green
- the clean-user acceptance flow is still repeatable:
  - `pipx install webots-mcp-kit`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1`
- the centralized acceptance script still matches the clean-user flow:
  - `python scripts/clean_user_acceptance.py --workspace <path>`
- the explicit no-mock v1 gate still passes on the real runtime:
  - `python scripts/v1_gate_check.py --workspace <path>`

## Trusted Publishing setup

Configure PyPI and TestPyPI trusted publishers for:

- owner: `RdaKA12`
- repository: `webots-mcp-kit`
- workflow: `.github/workflows/release.yml`
- environments: `testpypi` and `pypi`

## Tag flow

1. Push `v*` tag
2. Verify build + `twine check`
3. Verify draft GitHub release exists
4. Verify TestPyPI publish
5. Verify TestPyPI install smoke
6. Verify PyPI publish
7. Verify PyPI install smoke
8. Verify the public install story still works:
   - `pipx install webots-mcp-kit`
   - `powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1 -Runtime`
9. Verify the team adoption lane still works:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_workspace.ps1 -Starter line-follower -Destination .\workspaces\line-follower-demo`
   - `powershell -ExecutionPolicy Bypass -File .\scripts\upgrade_check.ps1 -Workspace .\artifacts\upgrade-check -Runtime`

## After release

- replace template text in GitHub release notes if needed
- add package link to release summary
- confirm `pipx install webots-mcp-kit` install path works on a clean machine

## `v1.0.0` baseline gate

- hosted CI is continuously green
- interactive runtime smoke has stayed green across several patch releases
- GitHub Release, TestPyPI, and PyPI publishing is stable
- all 3 bundled scenarios still produce benchmark reports
- generated scenario `session start` plus `benchmark run` has been revalidated on the real interactive runtime
- external-user onboarding docs have been re-run end to end
- MCP contract docs use stable language
- `ControllerAgent` is documented as stable
