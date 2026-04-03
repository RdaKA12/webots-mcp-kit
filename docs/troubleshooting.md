# Troubleshooting

Use this page when install, verification, runtime smoke, or controller/world workflows fail.

## Webots Not Found / `WEBOTS_HOME`

Symptom:

- `webots-kit doctor --json` reports `status: blocked`
- `scripts\install.ps1` or `scripts\verify_install.ps1` says Webots could not be found

Likely cause:

- Webots `R2025a` is not installed
- `WEBOTS_HOME` does not point at the Webots installation root

Exact commands to diagnose:

```powershell
webots-kit doctor --json
Get-ChildItem Env:WEBOTS_HOME
Test-Path 'C:\Program Files\Webots'
```

Exact next action:

- install Webots `R2025a`, or set `WEBOTS_HOME` to the Webots install root for the current shell, then rerun:

```powershell
webots-kit doctor --json
```

## Unsupported Runtime Mode / Non-Interactive Session

Symptom:

- `doctor` reports `status: misconfigured`
- runtime smoke or real sessions fail when run from a Windows service session

Likely cause:

- the runner or shell is not inside an interactive desktop session
- you are on a GitHub-hosted Windows runner, which is not a supported interactive Webots runtime

Exact commands to diagnose:

```powershell
webots-kit doctor --json
$env:SESSIONNAME
```

Exact next action:

- restart the runtime runner in a logged-in desktop session labeled `interactive-webots`, then rerun:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1 -Runtime
```

- if you are in a GitHub-hosted release smoke job, treat the public verify script as a quick install check there and use the self-hosted Windows Runtime Smoke workflow for the real benchmark path

## Render / Init Failure

Symptom:

- `session start` or `benchmark run` fails during Webots startup
- logs mention render init, OpenGL, or controller connect timeouts

Likely cause:

- the machine cannot initialize the supported rendering path for Webots
- runtime was started in the wrong session mode

Exact commands to diagnose:

```powershell
webots-kit doctor --json
webots-kit benchmark run line-follower --controller example --output .\report.json --duration-s 3
webots-kit benchmark report .\report.json
```

Exact next action:

- move the run to an interactive desktop session with Webots installed, then rerun:

```powershell
webots-kit benchmark run line-follower --controller example --output .\report.json --duration-s 3
```

## C++ Controller Compile Failure

Symptom:

- `webots-kit controller validate <path> --strict` fails on a C++ controller
- output mentions compile readiness, missing includes, or compiler errors

Likely cause:

- Webots controller headers or compiler path are missing from the detected installation
- the controller edit introduced a compile error

Exact commands to diagnose:

```powershell
webots-kit doctor --json
webots-kit controller inspect .\controllers\demo_agent.cpp --scenario waypoint-nav --json
webots-kit controller validate .\controllers\demo_agent.cpp --scenario waypoint-nav --strict --json
```

Exact next action:

- fix the include or compile error reported by `controller validate`, or reinstall Webots `R2025a`, then rerun:

```powershell
webots-kit controller validate .\controllers\demo_agent.cpp --scenario waypoint-nav --strict --json
```

## MCP Connection Failure

Symptom:

- `webots-kit mcp serve` starts, but the client cannot use `webots_session_start` or follow-up tools
- session tools fail immediately after MCP startup

Likely cause:

- no active Webots runtime session
- the runtime side is not healthy even though the MCP server process itself started

Exact commands to diagnose:

```powershell
webots-kit doctor --json
webots-kit session start --scenario line-follower --controller example --mode fast --render off
webots-kit mcp serve
```

Exact next action:

- start a healthy bundled session first, then reconnect the MCP client and retry the tool sequence:

```powershell
webots-kit session start --scenario line-follower --controller example --mode fast --render off
webots-kit mcp serve
```

## Benchmark Failure After Successful Install

Symptom:

- install and quick verification pass
- `verify_install.ps1 -Runtime` or `benchmark run` fails or returns `pass: false`

Likely cause:

- runtime is healthy, but the chosen controller or world is not meeting benchmark expectations
- a custom controller is missing telemetry keys, device bindings, or stable control behavior
- or you are trying to run the real benchmark on a GitHub-hosted Windows runner that cannot provide the supported interactive runtime

Exact commands to diagnose:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1 -Runtime
webots-kit benchmark run line-follower --controller example --output .\report.json --duration-s 3
webots-kit benchmark report .\report.json
```

Exact next action:

- inspect the benchmark report and controller validation output, then either switch back to the bundled example controller or repair the custom controller before rerunning:

```powershell
webots-kit controller validate .\controllers\my_agent.py --scenario line-follower --strict --json
webots-kit benchmark run line-follower --controller .\controllers\my_agent.py --output .\report.json --duration-s 3
```

Next: go back to [First hour guide](./first-hour-guide.md) once the blocking issue is cleared.
