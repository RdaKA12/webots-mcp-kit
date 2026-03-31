# Changelog

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
