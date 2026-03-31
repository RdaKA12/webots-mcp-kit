# Custom Controller Integration

Use this flow when the controller lives outside the bundled repo examples.

## Recommended path

1. Scaffold from the closest bundled scenario:

```powershell
webots-kit controller scaffold .\controllers\my_agent.py --scenario line-follower
```

2. Integrate your own logic while keeping the stable public API:

- `ControllerAgent.from_robot(...)`
- `begin_step()`
- `report_step(...)`

3. Validate the controller:

```powershell
webots-kit controller validate .\controllers\my_agent.py --scenario line-follower --strict --json
```

4. Benchmark it:

```powershell
webots-kit benchmark run line-follower --controller .\controllers\my_agent.py --output .\report.json
```

## Required contract

- A `Robot()` instance must exist
- A `robot.step(...)` loop must exist
- `ControllerAgent` must be used
- `begin_step()` must be called
- `report_step(...)` must publish `sensors`, `metrics`, and `actuators`

## Notes

- Camera tooling requires `default_camera="camera"` for bundled scenarios.
- `--strict` is intended for release-grade validation, not quick sketches.
