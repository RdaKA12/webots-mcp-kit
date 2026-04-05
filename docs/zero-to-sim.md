# Zero-to-Sim Guide

`webots-mcp-kit` supports a template-driven path from an empty folder to a runnable Webots scenario for both `e-puck` and `MonsterBorg 4WD` robot profiles.

Status:

- the CLI command names are stable
- the documented core `ScenarioSpec` subset is stable
- richer authoring, robot-profile metadata, MonsterBorg task-hardening fields, and physical-adapter metadata remain `experimental-foundation` and additive on the `v2.9.0` stable line

## Supported templates

- `epuck-arena`
- `epuck-line-track`
- `epuck-waypoint`
- `epuck-obstacle-course`
- `monsterborg-line-track`
- `monsterborg-waypoint`
- `monsterborg-obstacle-course`

These templates are deterministic. The toolkit generates a JSON scenario spec first, then builds a world and controller scaffold from that spec.

## Quick start

```powershell
webots-kit project init .\my-webots-project
webots-kit scenario init .\my-webots-project\scenarios\warehouse-demo --template epuck-waypoint
webots-kit scenario validate .\my-webots-project\scenarios\warehouse-demo\webots-kit.scenario.json
webots-kit scenario build .\my-webots-project\scenarios\warehouse-demo\webots-kit.scenario.json
webots-kit scenario describe .\my-webots-project\scenarios\warehouse-demo\webots-kit.scenario.json
webots-kit scenario doctor .\my-webots-project\scenarios\warehouse-demo\webots-kit.scenario.json
```

## Generated files

The build step writes:

- `scenarios/<name>/webots-kit.scenario.json`
- `scenarios/<name>/worlds/<name>.wbt`
- `scenarios/<name>/controllers/<name>_agent.py`
- `scenarios/<name>/benchmark.config.json`
- `scenarios/<name>/webots-kit.generated.json`

## Scenario spec shape

The generated spec is JSON-first and agent-friendly:

- `project`
- `scenario`
- `robot`
- `environment`
- `layout`
- `task`
- `controller`
- `benchmark`
- `sensors`
- `actuators`

The toolkit validates the spec before build. Unsupported template/task combinations fail fast with structured error codes.

## Stable core subset in `v1.1.0`

The documented core subset is:

- `project.name`
- `scenario.name`, `scenario.kind`
- `robot.template`, `robot.name`, `robot.def`
- `environment.template`, `environment.arena.dimensions`, `environment.arena.floor`
- `layout.spawn.translation`, `layout.spawn.rotation_z`
- `layout.line_track.width`, `layout.line_track.points`
- `layout.waypoints`
- `layout.goal_region.center`, `layout.goal_region.radius`
- `layout.obstacles[].shape`, `position`, `rotation_z`, `size`, `radius`, `height`
- `controller.path`, `controller.default_camera`
- `benchmark.profile`, `benchmark.duration_s`, `benchmark.threshold_overrides`
- `sensors.required`, `actuators.required`

Additional authoring fields in `v1.8.0-alpha.1`:

- `layout.walls[]`
- `layout.landmarks[]`
- `layout.zones[]`
- `layout.props[]`

These remain additive and `experimental-foundation`, but they already participate in `scenario validate`, `scenario doctor`, `scenario build`, `world inspect`, and runtime smoke in `v1.8.0-alpha.1`.

## Example specs

### Line-follow

```json
{
  "schema_version": 1,
  "project": { "name": "factory-demo" },
  "scenario": { "name": "demo-line", "kind": "line-follow" },
  "robot": { "template": "e-puck", "name": "epuck-demo-line-line-follow", "def": "EPUCK" },
  "environment": { "template": "epuck-line-track", "arena": { "dimensions": [1.8, 1.2], "floor": "light" } },
  "layout": {
    "spawn": { "translation": [-0.7, 0.03, 0.0], "rotation_z": 0.0 },
    "line_track": { "width": 0.06, "points": [[-0.75, 0.03], [-0.2, 0.03], [-0.2, 0.42], [0.55, 0.42], [0.55, -0.2]] },
    "obstacles": [],
    "waypoints": []
  },
  "task": { "kind": "line-follow", "description": "Generated line-follow task." },
  "controller": { "path": "controllers/demo-line_agent.py", "default_camera": "camera" },
  "benchmark": { "profile": "line-follower", "duration_s": 20.0, "threshold_overrides": {} },
  "sensors": { "required": ["camera_left_band", "camera_center_band", "camera_right_band"] },
  "actuators": { "required": ["left_velocity", "right_velocity"] }
}
```

### Waypoint-nav

```json
{
  "schema_version": 1,
  "project": { "name": "warehouse-demo" },
  "scenario": { "name": "demo-waypoint", "kind": "waypoint-nav" },
  "robot": { "template": "e-puck", "name": "epuck-demo-waypoint-waypoint-nav", "def": "EPUCK" },
  "environment": { "template": "epuck-waypoint", "arena": { "dimensions": [2.0, 2.0], "floor": "plain" } },
  "layout": {
    "spawn": { "translation": [-0.65, 0.0, 0.0], "rotation_z": 0.0 },
    "obstacles": [],
    "walls": [{ "name": "wall-waypoint-divider", "start": [-0.2, -0.3], "end": [-0.2, 0.3], "thickness": 0.02, "height": 0.08 }],
    "landmarks": [{ "name": "landmark-waypoint-marker", "position": [0.15, -0.18], "radius": 0.04 }],
    "zones": [{ "name": "zone-goal-buffer", "center": [0.4, 0.0], "size": [0.22, 0.22] }],
    "props": [{ "name": "prop-waypoint-prop", "position": [0.0, 0.45], "size": [0.08, 0.08, 0.08] }],
    "waypoints": [[0.55, 0.0]],
    "goal_region": { "center": [0.55, 0.0], "radius": 0.16 }
  },
  "task": { "kind": "waypoint-nav", "description": "Generated waypoint task." },
  "controller": { "path": "controllers/demo-waypoint_agent.py", "default_camera": "camera" },
  "benchmark": { "profile": "waypoint-nav", "duration_s": 20.0, "threshold_overrides": {} },
  "sensors": { "required": ["ps0", "ps1", "ps2", "ps3", "ps4", "ps5", "ps6", "ps7"] },
  "actuators": { "required": ["left_velocity", "right_velocity"] }
}
```

### Obstacle-avoidance

```json
{
  "schema_version": 1,
  "project": { "name": "maze-demo" },
  "scenario": { "name": "demo-obstacle", "kind": "obstacle-avoidance" },
  "robot": { "template": "e-puck", "name": "epuck-demo-obstacle-obstacle-avoidance", "def": "EPUCK" },
  "environment": { "template": "epuck-obstacle-course", "arena": { "dimensions": [2.0, 2.0], "floor": "grid" } },
  "layout": {
    "spawn": { "translation": [0.0, 0.0, 0.0], "rotation_z": 1.57 },
    "obstacles": [
      { "shape": "box", "position": [-0.68, 0.2], "size": [0.1, 0.1, 0.1], "rotation_z": 0.5 },
      { "shape": "box", "position": [0.35, 0.75], "size": [0.1, 0.1, 0.1], "rotation_z": 4.96782 }
    ],
    "waypoints": []
  },
  "task": { "kind": "obstacle-avoidance", "description": "Generated obstacle-avoidance task." },
  "controller": { "path": "controllers/demo-obstacle_agent.py", "default_camera": "camera" },
  "benchmark": { "profile": "obstacle-avoidance", "duration_s": 20.0, "threshold_overrides": {} },
  "sensors": { "required": ["ps0", "ps1", "ps2", "ps3", "ps4", "ps5", "ps6", "ps7"] },
  "actuators": { "required": ["left_velocity", "right_velocity"] }
}
```

## Runtime flow after build

The generated metadata includes suggested commands. The typical next steps are:

```powershell
webots-kit session start --scenario waypoint-nav --world .\scenarios\warehouse-demo\worlds\warehouse-demo.wbt --controller .\scenarios\warehouse-demo\controllers\warehouse-demo_agent.py --robot-name epuck-warehouse-demo-waypoint-nav --robot-def EPUCK --mode fast --render off
webots-kit benchmark run waypoint-nav --controller .\scenarios\warehouse-demo\controllers\warehouse-demo_agent.py --world .\scenarios\warehouse-demo\worlds\warehouse-demo.wbt --robot-name epuck-warehouse-demo-waypoint-nav --robot-def EPUCK --output .\scenarios\warehouse-demo\artifacts\report.json
```

## Current limits

- This is template-driven, not free-form natural language to `.wbt`.
- Official robot profiles are `e-puck` and `monsterborg-4wd`.
- Arena generation is currently rectangle-based.
- Richer generated task-world authoring currently targets supported task primitives like walls, landmarks, zones, props, obstacles, lines, and goal regions rather than arbitrary full-scene composition.
- Runtime smoke still requires an interactive self-hosted runner labeled `interactive-webots`.

Next: continue with [World authoring and editing](./world-authoring-and-editing.md) if you want to inspect or patch the generated `.wbt` after build.
