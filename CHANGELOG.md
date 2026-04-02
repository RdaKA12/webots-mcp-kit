# Changelog

## v0.10.0

- Added zero-to-sim foundations with `project init`, `scenario init`, `scenario validate`, `scenario build`, `scenario describe`, and `scenario doctor`.
- Added deterministic template-driven scenario generation for `epuck-arena`, `epuck-line-track`, `epuck-waypoint`, and `epuck-obstacle-course`.
- Added `project import`, `session export`, and `session replay` to bring existing Webots projects and finished runtime sessions into kit-managed workflows.
- Extended `benchmark run` so generated worlds can reuse bundled benchmark profiles through additive `--world`, `--robot-name`, and `--robot-def` overrides.
- Added regression coverage for project/scenario lifecycle, generated assets, import metadata, and session export/replay flows.
- Finalized the pre-`v1.0.0` contract polish around `doctor`, `scenario validate`, `scenario doctor`, `session replay`, and runtime documentation so all active user surfaces now use the same short summary plus `next_step` style.
- Promoted generated-scenario runtime smoke into the official self-hosted workflow and expanded package/release smoke so published installs also cover `project init`, `scenario init`, and `scenario build`.
- Hardened the runtime daemon for generated scenarios by mapping hashed extern-controller aliases back to long robot names, allowing built scenarios to connect under real Webots runtime smoke.
- Marked `project/scenario/import/replay` as `experimental-foundation`: CLI names are now stable, but deeper schema evolution remains additive until the post-`v1.0.0` zero-to-sim milestone.
- Tightened release and runner documentation around the `interactive-webots` runtime model and the shared runner-owned Python installation.

## v0.9.15

- Stabilized the self-hosted runtime contract around the `interactive-webots` runner model and enriched diagnostics with runner mode, launch environment, and categorized startup failures.
- Added structured runtime and MCP error payloads with stable error codes such as `render-init-failed`, `controller-launch-failed`, `agent-connect-timeout`, and `supervisor-connect-timeout`.
- Tightened the LLM-facing MCP surface by documenting request/response contracts, keeping stable success shapes, and returning structured failure payloads instead of free-form dumps.
- Improved agent-user output and onboarding with clearer `doctor`, `controller validate`, and `benchmark report` flows plus two explicit documentation entry paths: connect an agent or integrate a controller.
- Added regression coverage for runtime error classification, MCP failure payloads, diagnostics artifacts, environment detection, and controller validation formatting.

## v0.9.12

- Moved the self-hosted runtime workflow to the dedicated `interactive-webots` runner label so Webots runtime smoke runs in a logged-in desktop session instead of a Windows service session.
- Updated doctor output and runner documentation to mark interactive runner execution as a hard requirement for Webots runtime smoke on Windows.

## v0.9.11

- Added automatic software OpenGL detection for headless Webots launches by wiring `QT_OPENGL=software` and a discovered `opengl32sw.dll` directory into the Webots process environment.
- Enabled the runtime daemon to prefer software OpenGL automatically when sessions run with `--render off`.
- Added unit coverage for configured `opengl32sw.dll` discovery.

## v0.9.10

- Ensured the self-hosted Windows runtime workflow bootstraps `pip` with `python -m ensurepip --upgrade` before installing toolkit dependencies.
- Aligned the shared runner-owned Python 3.11 path with a guaranteed pip bootstrap path.

## v0.9.9

- Preferred a machine-local shared Python 3.11 install at `D:\actions-runner\python311-shared` for the self-hosted Windows runtime workflow, avoiding both the broken toolcache registration and inaccessible user-profile installs.
- Kept the Python bootstrap path as a fallback, but moved the workflow to a stable runner-owned interpreter first.

## v0.9.8

- Fixed the self-hosted Windows runtime workflow to skip inaccessible Python candidates instead of failing on `AccessDenied`.
- Added a bootstrap fallback that installs Python 3.11 into the runner temp directory from a local `python-3.11.9-amd64.exe` installer when no valid standard-library install is accessible.
- Hardened failure diagnostics so Python-resolution failures still upload a usable artifact bundle.

## v0.9.7

- Fixed the self-hosted Windows runtime workflow to reject broken Python toolcache installs that do not include `Lib\encodings`.
- Added filesystem fallback discovery for standard per-user Python 3.11 installs under `C:\Users\*\AppData\Local\Programs\Python\Python311`.
- Extended workflow regression coverage for valid-standard-library Python resolution.

## v0.9.6

- Fixed the self-hosted Windows runtime workflow YAML syntax by converting PowerShell invocations that started with `&` into block `run` sections.
- Added regression coverage to keep the runtime workflow free of unquoted ampersand-prefixed `run:` lines.

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
