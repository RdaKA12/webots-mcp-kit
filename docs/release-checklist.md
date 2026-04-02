# Release Checklist

## Before tagging

- `python -m pytest -q`
- hosted CI is green
- hosted MCP smoke is green
- interactive self-hosted runtime smoke is green if runtime code changed
- latest `interactive-webots` runner runtime smoke passed in a logged-in desktop session
- generated-scenario runtime smoke passed on the interactive runner
- package build and `twine check` are green
- PyPI/TestPyPI install smoke expectations are ready to pass
- changelog and README version notes are updated

## Pre-`v1.0.0` hardening gate

- at least a few consecutive `v0.10.x` patch releases have passed the GitHub Release, TestPyPI, and PyPI flow cleanly
- hosted CI stays green
- interactive runtime smoke stays green on the `interactive-webots` runner
- package build stays green
- PyPI install smoke stays green
- generated-scenario smoke stays green
- the clean-user acceptance flow is still repeatable:
  - `pip install webots-mcp-kit`
  - `webots-kit doctor`
  - `webots-kit benchmark list`
  - `webots-kit controller scaffold`
  - `webots-kit project init`
  - `webots-kit scenario init`
  - `webots-kit scenario build`

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
8. Verify `project init -> scenario init -> scenario build` works from the published package

## After release

- replace template text in GitHub release notes if needed
- add package link to release summary
- confirm `pip install webots-mcp-kit` install path works on a clean machine

## `v1.0.0` gate

- hosted CI is continuously green
- interactive runtime smoke has stayed green across several patch releases
- GitHub Release, TestPyPI, and PyPI publishing is stable
- all 3 bundled scenarios still produce benchmark reports
- generated scenario `session start` plus `benchmark run` has been revalidated on the real interactive runtime
- external-user onboarding docs have been re-run end to end
- MCP contract docs use stable language
- `ControllerAgent` is documented as stable
