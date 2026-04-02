# Changelog

## v0.9.5

- Fixed the self-hosted Windows runtime workflow to resolve Python 3.11 from the Windows registry instead of relying on the `py` launcher, which was selecting a broken runner-local interpreter.
- Removed PATH dependence from runtime smoke by invoking the doctor command as `python -m webots_mcp_kit.cli`.
- Extended workflow regression coverage for registry-based Python resolution and module-based doctor invocation.

## v0.9.4

- Fixed the self-hosted Windows runtime workflow to use the system `py` launcher with Python 3.11, avoiding PATH issues for the runner service account.
- Extended workflow regression coverage so the runtime workflow keeps both the PowerShell execution-policy bypass and the `py -3.11` launcher usage.

## v0.9.3

- Fixed the self-hosted Windows runtime workflow to run PowerShell steps with `ExecutionPolicy Bypass`, avoiding local script-blocking on the runner service account.
- Added regression coverage to ensure the runtime workflow keeps the execution-policy bypass template.

## v0.9.2

- Removed `actions/setup-python` from the self-hosted Windows runtime workflow to avoid runner-local PowerShell execution policy failures.
- Replaced it with direct validation of the runner's installed Python, keeping the runtime workflow aligned with the machine-local Webots setup.

## v0.9.1

- Fixed self-hosted Windows workflow installation so `pytest` and `webots_mcp_kit` are installed into the exact Python selected by `actions/setup-python`.
- Fixed release install smoke jobs to use `python -m pip`, preventing interpreter mismatch on Windows runners.
- Added extra workflow-level install verification for self-hosted Windows runs.

## v0.9.0

- Added path-filtered self-hosted runtime workflow triggers while keeping manual dispatch.
- Tightened runtime readiness output and contribution policy for runtime-affecting changes.
- Added public-contract regression tests for `ControllerAgent`, benchmark report formatting, doctor output, and bundled package assets.
- Promoted PyPI install and external-user onboarding docs, including a first-hour guide.
- Updated MCP contract documentation toward the v1.0 stable contract language.

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
