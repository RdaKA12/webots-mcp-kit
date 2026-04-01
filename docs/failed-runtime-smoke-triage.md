# Failed Runtime Smoke Triage

Use this order when a self-hosted runtime smoke run fails.

## 1. Readiness

- Run `webots-kit doctor --json`
- Confirm runner labels include `webots`
- Confirm `WEBOTS_HOME` and Python point to the expected install
- Confirm the failing change actually touched a runtime-triggering path or was manually dispatched

## 2. Session diagnostics

- Inspect uploaded workflow artifact bundle
- Read `inspect.json`, `log_inventory.json`, and `log_summary.json`
- If needed, inspect canonical logs:
  - `daemon.stdout.log`
  - `daemon.stderr.log`
  - `webots.stdout.log`
  - `webots.stderr.log`
  - `<robot-name>.stdout.log`
  - `<robot-name>.stderr.log`
  - `kit-supervisor.stdout.log`
  - `kit-supervisor.stderr.log`

## 3. Typical failure buckets

- Webots install missing or wrong version
- runner service account cannot access Webots or repo path
- session starts but runtime never connects
- packaged controller/world path is wrong
- self-hosted machine is slower than current timeout

## 4. Local repro

```powershell
$env:WEBOTS_KIT_RUN_RUNTIME_SMOKE='1'
python -m pytest -q -k "session_start_inspect_stop_smoke or benchmark_smoke"
```
