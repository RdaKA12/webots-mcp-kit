# First Hour Guide

Use this guide when you want the shortest supported path from install to a real `line-follower` benchmark on Windows.

## 1. Install From A Repo Checkout

Primary path:

```powershell
pipx install webots-mcp-kit
```

If you want the repo helper to install `pipx` and the package for you:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

## 2. Run The Public Verification Script

Quick verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1
```

Runtime verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1 -Runtime
```

MonsterBorg verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_install.ps1 -RobotProfile monsterborg-4wd -Runtime
```

The script checks:

- `webots-kit --version`
- `webots-kit doctor --json`
- `webots-kit benchmark list`
- temporary Python controller scaffold + strict validate
- bundled world inspect
- a short real `line-follower` benchmark when `-Runtime` is used

## 3. Understand What A Green Result Means

You are ready to continue when:

- `doctor` reports `status: ready`
- `benchmark list` returns the bundled scenarios
- the temporary controller validates cleanly
- bundled world inspect reports `status: ready`
- the short runtime benchmark passes in `-Runtime` mode

## 4. Start A Session Or Benchmark Manually

Start a bundled session:

```powershell
webots-kit session start --scenario line-follower --controller example --mode fast --render off
```

Run the canonical benchmark:

```powershell
webots-kit benchmark run line-follower --controller example --output .\report.json --duration-s 3
webots-kit benchmark report .\report.json
```

## 5. Choose The Next Workflow

- Live MCP session: [Onboarding flows](./onboarding-flows.md)
- Controller authoring: [Controller authoring and editing](./controller-authoring-and-editing.md)
- World authoring: [World authoring and editing](./world-authoring-and-editing.md)
- Import and replay: [Project import and session replay](./project-import-and-replay.md)
- Team route map: [Team flows](./team-flows.md)

## Notes

- The only supported runtime execution model is `interactive-webots`.
- Webots runtime smoke is not supported from a Windows service session.
- If Webots is not found or the benchmark fails, go straight to [Troubleshooting](./troubleshooting.md).
- If you want a ready workspace instead of starting from a blank folder, run `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_workspace.ps1 -Starter line-follower`.
- For the MonsterBorg lane, replace the starter with `monsterborg-line-follower`.

Next: continue with [Onboarding flows](./onboarding-flows.md).
