# MCP Contracts

`webots-mcp-kit` keeps MCP tool names stable. The payloads below are the stable baseline for the current pre-1.0 contract.

## Stable response shapes

### `webots_list_devices`

Response shape:

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

Response shape:

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

Typical response:

```json
{
  "path": "C:\\Users\\...\\capture-123.ppm",
  "width": 40,
  "height": 1
}
```

### `webots_run_benchmark`

Typical response fields:

```json
{
  "benchmark": "line-follower",
  "world": "D:\\Projects\\webots-mcp-kit\\examples\\line-follower\\worlds\\line_follower_benchmark.wbt",
  "controller": "D:\\Projects\\webots-mcp-kit\\examples\\line-follower\\controllers\\line_follower_agent.py",
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

## Notes

- `examples/` contains runnable bundled controllers and worlds.
- Benchmark thresholds are scenario-specific and come from the registry in `src/webots_mcp_kit/benchmarks.py`.
- Hosted GitHub runners do not execute real Webots runtime smoke; use the self-hosted Windows workflow for runtime verification.
