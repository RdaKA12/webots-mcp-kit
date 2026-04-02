# Changelog

## v1.4.0-alpha.1

- Added generated-world and imported-world authoring runtime smoke coverage so world edits are now exercised through real `world edit -> validate -> session start` flows.
- Extended the preview gate and self-hosted runtime workflow with authoring lanes for generated and imported world edit paths.
- Promoted the feature-branch preview versioning to `v1.4.0-alpha.1` while keeping the work isolated on `feature/agent-authoring-platform`.

## v1.3.0-alpha.1

- Added an agent-authoring preview branch foundation for controller scaffold, inspect, edit, and validate across Python and C++ sources.
- Added a preserve-first WBT inspect, validate, and edit foundation with selector-based world operations for supported task-world node families.
- Extended clean-user acceptance with controller and world authoring flows while keeping the existing runtime/session/benchmark surfaces intact.

## v1.2.0

- Expanded `project import` with deterministic discovery for robot name/DEF, controller device usage, suggested benchmark profile, and minimal imported scenario metadata.
- Expanded `session replay` with additive `benchmark_summary`, `telemetry_summary`, `runtime_failure_class`, and `triage_recipe` fields plus a more triage-oriented text summary.
- Kept `export.json` and the standard artifact bundle backward-compatible while extending the export manifest with additive scenario and result metadata.

## v1.1.0

- Expanded the template-driven zero-to-sim path with richer `ScenarioSpec` defaults, semantic validation, and a documented stable core subset for `v1.1.0`.
- Added floor-aware world generation, richer `scenario doctor` readiness fields, and broader generated-scenario runtime smoke across line-follow, waypoint-nav, and obstacle-avoidance.
- Extended the no-mock gate so generated scenarios for all three bundled task families are validated through real runtime `session start` and `benchmark run`.

## v1.0.0

- Declared the Windows, Webots `R2025a`, Python `3.11+`, `interactive-webots` runtime model as the stable supported baseline.
- Promoted the MCP tool names and documented success/failure payload shapes to the stable public contract.
- Documented `ControllerAgent.from_robot(...)`, `begin_step()`, and `report_step(...)` as the stable controller-side API.
- Kept zero-to-sim and import/export/replay workflows supported at a foundation level while explicitly leaving deeper JSON schema refinement additive until `v1.1.0`.
- Carried the no-mock real-runtime gate, clean-user acceptance flow, and published release pipeline forward from the `v0.10.x` hardening series.

## v0.10.7

- Stabilized real `capture_camera` success-path execution by hardening runtime socket I/O, delaying `ready` until both runtimes have published telemetry, and retrying capture only after fresh agent steps.
- Tightened the live MCP contract smoke back to a real success assertion for `capture_camera` instead of tolerating structured failure payloads during warm-up races.

## v0.10.6

- Moved more contract coverage off monkeypatched dummy clients and onto real normalization paths plus real runtime smoke checks, especially around MCP tool outputs and export/replay diagnostics.
- Added live runtime smoke for MCP tool contracts and `session export -> diagnostics -> replay`, while keeping only the inherently synthetic OS/error-branch tests in the unit layer.
- Removed unnecessary `SessionStore` monkeypatching from `inspect_session` and diagnostics regression coverage by allowing store-backed inspection paths to be exercised directly in tests.

## v0.10.5

- Added an explicit no-mock `v1.0.0` gate script that exercises the real CLI/runtime flows for bundled benchmarks, generated scenarios, and import/export/replay.
- Fixed the bundled `waypoint-nav` reference controller so the bundled benchmark can actually reach the target and pass on the real runtime.

## v0.10.4

- Fixed the centralized acceptance workflow for hosted Linux package smoke by adding an explicit `hosted-safe` profile that skips `doctor` when Webots is intentionally unavailable.
- Kept the full clean-user acceptance path for Windows/TestPyPI/PyPI install smoke while routing `Packaging CI` through the hosted-safe profile.

## v0.10.3

- Centralized the clean-user acceptance flow in a single reusable script so package CI, TestPyPI smoke, and PyPI smoke all exercise the same command sequence.
- Added an explicit onboarding index that points users to the four pre-`v1.0.0` public entry paths: connect an agent, integrate a controller, generate a scenario from a spec, and import/replay.
- Tightened release-hardening docs and workflow regression coverage around the clean-user acceptance script and checkout requirements in publish-install smoke jobs.

## v0.10.2

- Finalized the runtime export bundle around a canonical standard-artifact manifest, including explicit artifact-version and replay-mode metadata in `export.json`.
- Expanded `session replay` into a more observability-focused report with artifact standard metadata, result reason, runtime environment summary, and log-summary context.
- Added imported-project runtime smoke coverage so the real runtime path now validates `project import` plus basic `session start -> inspect -> stop` on an existing bundled world/controller pair.
- Tightened runner and replay documentation so the `interactive-webots` machine standard and exported-session triage flow stay aligned with the runtime smoke workflow.

## v0.10.1

- Tightened the pre-`v1.0.0` MCP contract freeze by normalizing stable success payloads for `webots_session_start`, `webots_get_state`, `webots_capture_camera`, and `webots_run_benchmark` while preserving additive extra fields.
- Preserved structured runtime/admin error codes through the daemon request path so lower-level failures are no longer collapsed into a generic `admin-request-failed` code.
- Standardized runtime diagnostics artifacts even when no session manifest is available and promoted `export.json` plus the standard artifact paths into the canonical session export manifest.
- Hardened `session replay` around the canonical export manifest while keeping directory-based replay compatibility.
- Expanded package and publish smoke flows to cover `controller scaffold` and `scenario validate`, and updated runtime/release docs to treat `interactive-webots` as the single supported runtime execution model.

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
