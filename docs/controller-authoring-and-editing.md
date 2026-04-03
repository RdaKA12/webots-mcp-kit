# Controller Authoring and Editing

This page documents the `experimental-foundation` controller authoring surface in `v1.9.0-alpha.1`.

## Supported scope

- Python controller scaffolds and edits
- C++ controller scaffolds, inspect, validate, and compile smoke
- `ControllerAgent`-style controllers
- bundled task families:
  - `line-follower`
  - `obstacle-avoidance`
  - `waypoint-nav`

The public controller-side contract stays:

- `ControllerAgent.from_robot(...)`
- `begin_step()`
- `report_step(...)`

## Scaffold

Python scaffold:

```powershell
webots-kit controller scaffold .\controllers\demo_agent.py --scenario line-follower --language python
```

C++ scaffold:

```powershell
webots-kit controller scaffold .\controllers\demo_agent.cpp --scenario waypoint-nav --language cpp
```

The same authoring surface is available through MCP:

- `webots_controller_scaffold`
- `webots_controller_inspect`
- `webots_controller_validate`
- `webots_controller_edit`

The generated scaffold exposes these editable regions:

- `DEVICE_INIT`
- `CONTROL_POLICY`
- `TELEMETRY_REPORT`
- `HELPERS`

## Inspect

```powershell
webots-kit controller inspect .\controllers\demo_agent.py --scenario line-follower --json
```

`controller inspect` returns:

- detected language
- integration mode
- editable regions
- function inventory
- editable symbols
- device bindings
- device access inventory
- default camera
- telemetry sections
- telemetry contract
- benchmark readiness
- benchmark contract gaps
- compile readiness
- runtime readiness
- controller fix hints

## Edit

```powershell
webots-kit controller edit .\controllers\demo_agent.py --plan .\plans\controller-edit.json
```

Example plan:

```json
{
  "schema_version": 1,
  "operations": [
    {
      "type": "update_control_constants",
      "constants": {
        "CRUISE": 180
      }
    }
  ]
}
```

Current edit operations:

- `set_symbol_value`
- `replace_function_body`
- `add_import_or_include`
- `remove_import_or_include`
- `replace_control_policy`
- `set_goal_logic`
- `set_line_follow_logic`
- `set_obstacle_avoidance_logic`
- `inject_helper_function`
- `remove_helper_function`
- `set_device_bindings`
- `set_default_camera`
- `update_control_constants`
- `update_report_step_keys`
- `set_manual_override_behavior`

## Validate

```powershell
webots-kit controller validate .\controllers\demo_agent.py --scenario line-follower --strict --json
```

Validation checks:

- robot initialization
- step loop
- `ControllerAgent` usage
- default camera
- benchmark-facing telemetry keys
- benchmark contract gaps
- runtime readiness
- controller fix hints
- C++ compile smoke when the source language is `cpp`

## Recommended loop

1. `controller scaffold`
2. `controller inspect`
3. `controller edit`
4. `controller validate --strict`
5. `benchmark run`
