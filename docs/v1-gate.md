# v1.0.0 Gate

This page documents the no-mock release gate used to cut `v1.0.0`.

## Important distinction

- unit and regression tests in `tests/` may still use monkeypatching or fake payloads to lock contracts
- the stable release gate must also pass a real-runtime CLI validation run with no mocked runtime components

## Real-runtime gate script

Run the explicit gate script on a Windows machine with Webots `R2025a` installed:

```powershell
python scripts\v1_gate_check.py --workspace .\artifacts\v1-gate
```

This script validates:

- `doctor`
- the clean-user acceptance flow
- all 3 bundled scenario benchmarks
- generated scenario init/validate/build
- generated scenario `session start`
- generated scenario `benchmark run`
- imported-project metadata creation
- imported-project `session export`
- imported-project `session replay`

## Release expectation

`v1.0.0` was cut only after the documented release checklist and this no-mock gate both passed. Keep this gate green for later stable releases.
