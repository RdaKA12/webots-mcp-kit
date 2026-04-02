# MCP Contracts

`webots-mcp-kit` keeps MCP tool names stable. The six tool surfaces below are part of the stable `v1.0.0` contract: success payloads stay additive-only, documented top-level keys do not get renamed or removed, and failure payloads use the structured shape documented below.

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

## Feature-branch authoring preview

On `feature/agent-authoring-platform`, the MCP server also exposes additive `experimental-foundation` authoring tools:

- `webots_world_inspect`
- `webots_world_validate`
- `webots_world_edit`
- `webots_controller_inspect`
- `webots_controller_scaffold`
- `webots_controller_validate`
- `webots_controller_edit`

These tool names are stable within the branch preview. Their payloads remain additive while the feature branch hardens toward merge.

### World authoring payloads

- `webots_world_inspect -> { status, world_path, robots, target_robot, supported_edit_targets, spatial_summary, ... }`
- `webots_world_validate -> { world_path, valid, status, issues, supported_edit_targets, spatial_summary, ... }`
- `webots_world_edit -> { world_path, applied_operations, status, issues, validation, support_tier, next_step }`

### Controller authoring payloads

- `webots_controller_scaffold -> { path, scenario, language, default_camera, editable_regions, source_controller, ... }`
- `webots_controller_inspect -> { path, language, scenario, integration_mode, editable_regions, default_camera, device_bindings, benchmark_ready, ... }`
- `webots_controller_validate -> { path, valid, integration_mode, errors, warnings, details }`
- `webots_controller_edit -> { path, language, applied_operations, editable_regions, next_step }`

The preview authoring tools use the same structured failure shape documented above.

## Contract notes

- Tool names stay fixed.
- Success payloads may add fields, but existing top-level keys should not be removed or renamed.
- The six success shapes above are the stable contract surface for `v1.0.0` and later additive releases.
- `webots_list_devices` and `webots_get_sensors` must always keep their documented top-level shape.
- Failure payloads should prefer structured `error.code` and `error.details` over free-form string dumps.

## Feature-branch authoring preview

On `feature/agent-authoring-platform`, the authoring tools below are additive preview tools. They are not part of the `v1.0.0` stable baseline, but their documented top-level success shapes are intentionally frozen for the preview branch so tests and agents can depend on them.

### `webots_world_inspect`

Stable preview top-level keys:

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
  "inferred_task_cues": {},
  "support_tier": "experimental-foundation",
  "next_step": "Run `webots-kit world validate ...`."
}
```

### `webots_world_validate`

Stable preview top-level keys:

```json
{
  "world_path": "C:\\Users\\...\\demo.wbt",
  "valid": true,
  "status": "ready",
  "issues": [],
  "supported_edit_targets": [],
  "spatial_summary": {},
  "summary": {},
  "support_tier": "experimental-foundation",
  "next_step": "Apply `webots-kit world edit ...`."
}
```

### `webots_world_edit`

Stable preview top-level keys:

```json
{
  "world_path": "C:\\Users\\...\\demo.wbt",
  "applied_operations": [],
  "status": "ready",
  "issues": [],
  "validation": {},
  "support_tier": "experimental-foundation",
  "next_step": "Apply `webots-kit world edit ...`."
}
```

### `webots_controller_inspect`

Stable preview top-level keys:

```json
{
  "path": "C:\\Users\\...\\demo_agent.py",
  "language": "python",
  "scenario": "line-follower",
  "integration_mode": "controller-agent",
  "valid_source": true,
  "editable_regions": [],
  "markers_present": true,
  "default_camera": "camera",
  "device_bindings": [],
  "telemetry_sections": {},
  "benchmark_readiness": {},
  "issues": []
}
```

### `webots_controller_scaffold`

Stable preview top-level keys:

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
  "target_robot_def": "EPUCK"
}
```

### `webots_controller_validate`

This tool uses the same normalized validation top-level shape as the stable controller-validation CLI JSON:

```json
{
  "path": "C:\\Users\\...\\demo_agent.py",
  "valid": true,
  "integration_mode": "controller-agent",
  "errors": [],
  "warnings": [],
  "details": {}
}
```

### `webots_controller_edit`

Stable preview top-level keys:

```json
{
  "path": "C:\\Users\\...\\demo_agent.py",
  "language": "python",
  "applied_operations": [],
  "editable_regions": [],
  "next_step": "Run `webots-kit controller validate ...`."
}
```
