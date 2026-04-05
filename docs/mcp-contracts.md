# MCP Contracts

`webots-mcp-kit` keeps MCP tool names stable. The six tool surfaces below are part of the stable `v1.0.0` contract: success payloads stay additive-only, documented top-level keys do not get renamed or removed, and failure payloads use the structured shape documented below.

Robot-aware additive fields such as `robot_family`, `robot_profile`, and `runtime_target` are now returned on the relevant session, benchmark, controller, and replay payloads. Existing top-level keys remain stable.

## Stable success payloads

### `webots_session_start`

Typical request:

```json
{
  "scenario": "line-follower",
  "controller": "example",
  "mode": "fast",
  "render": false
}
```

Typical response:

```json
{
  "session_id": "abc123def456",
  "status": "ready",
  "scenario": "line-follower",
  "target_robot_name": "epuck-line-follower",
  "host": "127.0.0.1",
  "port": 55123,
  "environment": {
    "python_executable": "D:\\actions-runner\\python311-shared\\python.exe",
    "webots_executable": "C:\\Program Files\\Webots\\msys64\\mingw64\\bin\\webots.exe"
  }
}
```

### `webots_get_state`

Stable top-level response shape:

```json
{
  "session": {
    "session_id": "abc123def456",
    "status": "ready",
    "scenario": "line-follower"
  },
  "session_state": {
    "status": "ready",
    "scenario": "line-follower",
    "target_robot_name": "epuck-line-follower",
    "last_error_code": null,
    "last_error": null
  },
  "control_paused": false,
  "runtime_summary": {
    "agent": {
      "connected": true,
      "device_count": 5
    },
    "supervisor": {
      "connected": true,
      "device_count": 0
    }
  },
  "runtimes": {
    "agent": {
      "state": {
        "robot_time": 1.248,
        "step_index": 39
      }
    }
  }
}
```

### `webots_list_devices`

Stable top-level shape:

```json
{
  "robot": "epuck-line-follower",
  "scenario": "line-follower",
  "devices": [
    {
      "name": "camera",
      "type": "Camera",
      "category": "sensor",
      "capabilities": ["read-image", "capture-image"],
      "readable": true,
      "writable": false
    }
  ]
}
```

### `webots_get_sensors`

Stable top-level shape:

```json
{
  "robot": "epuck-line-follower",
  "scenario": "line-follower",
  "state": {
    "robot_time": 3.136,
    "step_index": 17,
    "basic_time_step": 32
  },
  "sensors": {
    "camera_left_band": 12.3
  },
  "metrics": {
    "line_visible": true,
    "center_error": 0.12
  },
  "actuators": {
    "left_velocity": 2.1,
    "right_velocity": 1.8
  },
  "meta": {
    "paused": false,
    "default_camera": "camera"
  }
}
```

### `webots_capture_camera`

Typical request:

```json
{
  "session": "abc123def456"
}
```

Stable top-level response shape:

```json
{
  "path": "C:\\Users\\...\\capture-123.ppm",
  "width": 40,
  "height": 1
}
```

### `webots_run_benchmark`

Typical request:

```json
{
  "scenario": "line-follower",
  "controller": "example",
  "duration_s": 3.0
}
```

Stable top-level response shape:

```json
{
  "benchmark": "line-follower",
  "session_mode": "fast",
  "sim_time_s": 3.136,
  "steps": 17,
  "line_loss_events": 0,
  "max_line_loss_streak": 0,
  "mean_center_error": 0.09375,
  "ir_balance_error": 0.670553,
  "pass": true,
  "artifacts": {
    "stdout": "...",
    "stderr": "...",
    "frames_dir": "..."
  },
  "notes": [],
  "extra_metrics": {}
}
```

## Structured failure payload

When a tool cannot complete successfully, it should return:

```json
{
  "ok": false,
  "error": {
    "code": "render-init-failed",
    "message": "Webots could not initialize the rendering system before the runtimes connected.",
    "details": {
      "session_id": "abc123def456"
    },
    "retriable": false
  }
}
```

Known error codes currently used by runtime/session flows:

- `render-init-failed`
- `controller-launch-failed`
- `supervisor-connect-timeout`
- `agent-connect-timeout`
- `session-start-timeout`
- `webots-unexpected-exit`
- `admin-request-failed`
- `mcp-tool-failed`

The code values above are frozen starting with `v1.0.0`. Future codes may be added, but existing codes should not be renamed or repurposed.

## Contract notes

- Tool names stay fixed.
- Success payloads may add fields, but existing top-level keys should not be removed or renamed.
- The six success shapes above are the stable contract surface for `v1.0.0` and later additive releases.
- `webots_list_devices` and `webots_get_sensors` must always keep their documented top-level shape.
- Failure payloads should prefer structured `error.code` and `error.details` over free-form string dumps.

## Authoring tools in `v2.8.0-alpha.1`

`v2.8.0-alpha.1` also exposes additive `experimental-foundation` authoring tools:

- `webots_world_inspect`
- `webots_world_validate`
- `webots_world_edit`
- `webots_controller_inspect`
- `webots_controller_scaffold`
- `webots_controller_validate`
- `webots_controller_edit`

These tools are not retroactively part of the `v1.0.0` stable baseline. In `v2.8.0-alpha.1` they remain additive and `experimental-foundation`, and their documented top-level keys are regression-tested. They use the same structured failure shape documented above.

### `webots_world_inspect`

Documented top-level keys:

```json
{
  "status": "ready",
  "world_path": "C:\\Users\\...\\demo.wbt",
  "externproto": [],
  "robots": [],
  "target_robot": null,
  "def_map": [],
  "controller_bindings": [],
  "supported_edit_targets": [],
  "spatial_summary": {},
  "summary": {},
  "scene_node_summary": {},
  "node_tree": [],
  "field_inventory": {},
  "inferred_task_cues": {},
  "def_use_map": {},
  "editability": {},
  "opaque_regions": [],
  "preserve_notes": [],
  "supported_mutation_modes": {},
  "support_tier": "experimental-foundation",
  "next_step": "Run `webots-kit world validate ...`."
}
```

### `webots_world_validate`

Documented top-level keys:

```json
{
  "world_path": "C:\\Users\\...\\demo.wbt",
  "valid": true,
  "status": "ready",
  "issues": [],
  "warnings": [],
  "supported_edit_targets": [],
  "spatial_summary": {},
  "summary": {},
  "def_use_map": {},
  "opaque_regions": [],
  "preserve_notes": [],
  "support_tier": "experimental-foundation",
  "next_step": "Apply `webots-kit world edit ...`."
}
```

### `webots_world_edit`

Documented top-level keys:

```json
{
  "world_path": "C:\\Users\\...\\demo.wbt",
  "applied_operations": [],
  "changed_paths": [],
  "status": "ready",
  "issues": [],
  "warnings": [],
  "summary": {},
  "validation": {},
  "supported_edit_targets": [],
  "def_use_map": {},
  "opaque_regions": [],
  "preserve_notes": [],
  "support_tier": "experimental-foundation",
  "next_step": "Apply `webots-kit world edit ...`."
}
```

### `webots_controller_inspect`

Documented top-level keys:

```json
{
  "path": "C:\\Users\\...\\demo_agent.py",
  "status": "ready",
  "language": "python",
  "scenario": "line-follower",
  "integration_mode": "controller-agent",
  "valid_source": true,
  "editable_regions": [],
  "markers_present": true,
  "function_inventory": [],
  "editable_symbols": [],
  "default_camera": "camera",
  "device_bindings": [],
  "device_access_inventory": [],
  "telemetry_sections": {},
  "telemetry_contract": {},
  "benchmark_readiness": {},
  "benchmark_contract_gaps": [],
  "compile_readiness": {},
  "runtime_readiness": {},
  "controller_fix_hints": [],
  "issues": [],
  "summary": {},
  "support_tier": "experimental-foundation",
  "next_step": "Run `webots-kit controller validate ...`."
}
```

### `webots_controller_scaffold`

Documented top-level keys:

```json
{
  "path": "C:\\Users\\...\\demo_agent.py",
  "scenario": "line-follower",
  "language": "python",
  "default_camera": "camera",
  "copied_files": [],
  "editable_regions": [],
  "source_controller": "C:\\Users\\...\\line_follower_agent.py",
  "spec_path": null,
  "world": null,
  "target_robot_name": "epuck-line-follower",
  "target_robot_def": "EPUCK",
  "support_tier": "experimental-foundation",
  "next_step": "Run `webots-kit controller inspect ...` or `webots-kit controller validate ...`."
}
```

### `webots_controller_validate`

This tool uses the same normalized validation top-level shape as the controller-validation CLI JSON:

```json
{
  "path": "C:\\Users\\...\\demo_agent.py",
  "valid": true,
  "status": "ready",
  "robot_family": "e-puck",
  "robot_profile": "e-puck",
  "integration_mode": "controller-agent",
  "errors": [],
  "warnings": [],
  "details": {},
  "summary": {},
  "support_tier": "experimental-foundation",
  "next_step": "Run `webots-kit benchmark run ...`."
}
```

### `webots_controller_edit`

Documented top-level keys:

```json
{
  "path": "C:\\Users\\...\\demo_agent.py",
  "language": "python",
  "applied_operations": [],
  "editable_regions": [],
  "status": "ready",
  "summary": {},
  "benchmark_readiness": {},
  "benchmark_contract_gaps": [],
  "controller_fix_hints": [],
  "support_tier": "experimental-foundation",
  "next_step": "Run `webots-kit controller validate ...`."
}
```
