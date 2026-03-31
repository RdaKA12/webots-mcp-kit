# Changelog

## v0.8.0

- Added packaging-ready bundled scenario assets inside the package so wheel installs can run `benchmark list`.
- Added `Packaging CI` and tag-driven `Release` workflows for GitHub Release, TestPyPI, and PyPI publication.
- Added runtime diagnostics collection for workflow artifact bundles.
- Hardened package metadata for public distribution and added packaging/install documentation.
- Added controller, scenario, runtime triage, release, and packaging verification guides.

## v0.7.0

- Stabilized the public `ControllerAgent` contract around `from_robot(...)`, `begin_step()`, and `report_step(...)`.
- Added `webots-kit controller scaffold` and expanded `controller validate` with `--scenario` and `--strict`.
- Added stable MCP payload normalization for `webots_list_devices` and `webots_get_sensors`.
- Added session environment snapshots, runtime summaries, canonical log inventory, and richer `session inspect` output.
- Added the bundled `waypoint-nav` scenario and moved benchmark thresholds into the scenario registry.
- Added self-hosted runtime and MCP contract documentation.

## v0.4.3

- Split hosted-safe CI from real Webots runtime smoke.
- Kept GitHub-hosted Windows CI focused on unit tests, `doctor`, and MCP tool-list smoke.
- Added a separate manual `Windows Runtime Smoke` workflow for self-hosted Windows runners labeled `webots`.
- Split smoke-test env gating so runtime-dependent tests require `WEBOTS_KIT_RUN_RUNTIME_SMOKE=1`.

## v0.4.2

- Stopped launching the daemon with detached process flags on Windows and now capture daemon stdout/stderr into session artifacts.
- Added richer `session start` timeout diagnostics, including daemon and Webots log tails.
- Marked early Webots exit before runtime registration as session failure.
- Increased GitHub Actions session startup timeout to 180 seconds.

## v0.4.1

- Increased CI session startup tolerance through `WEBOTS_KIT_SESSION_START_TIMEOUT`.
- Improved `session start` timeout diagnostics so CI logs include manifest and artifact context.
- Fixed Windows Actions diagnostics upload by copying session logs into the workspace before artifact upload.

## v0.4.0

- Added controller SDK hardening through the public `ControllerAgent` wrapper.
- Added `controller validate`, `session inspect`, `session logs`, and `doctor --json`.
- Added benchmark registry support and the bundled `obstacle-avoidance` scenario.
- Added Windows CI, repo templates, contributing guide, and release template.
- Added smoke-test coverage for session, MCP, and benchmark workflows.

## v0.3.0

- Added scenario registry with `line-follower` and `obstacle-avoidance`.
- Added `ControllerAgent` as the public controller-side SDK wrapper.
- Added `doctor --json`, `session inspect`, `session logs`, and `controller validate`.
- Stabilized session lifecycle metadata and session artifact inspection.
- Added Windows CI, issue templates, contributing guide, and release template.

## v0.1.0

- Initial public release with CLI, MCP server, agent-aware line follower example, and benchmark flow.
