# Release Checklist

## Before tagging

- `python -m pytest -q`
- hosted MCP smoke is green
- interactive self-hosted runtime smoke is green if runtime code changed
- latest `interactive-webots` runner runtime smoke passed in a logged-in desktop session
- `Packaging CI` is green
- changelog and README version notes are updated

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

## After release

- replace template text in GitHub release notes if needed
- add package link to release summary
- confirm `pip install webots-mcp-kit` install path works on a clean machine
