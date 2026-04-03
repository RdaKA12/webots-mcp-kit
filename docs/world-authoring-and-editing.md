# World Authoring and Editing

This page documents the `experimental-foundation` world authoring/editing surface in `v1.6.0`.

## Supported scope

The current world layer is `preserve-first`.

That means:

- supported target node families can be inspected and edited structurally
- unrelated text and unsupported node blocks are left unchanged whenever possible
- the toolkit is not yet a general-purpose full-scene Webots editor

Current first-class edit surface is task-world oriented:

- target robot spawn
- target robot controller binding
- obstacles
- walls
- landmarks
- zones
- props
- rename/remove supported top-level nodes

The same authoring surface is also exposed through MCP:

- `webots_world_inspect`
- `webots_world_validate`
- `webots_world_edit`

## Inspect

```powershell
webots-kit world inspect .\worlds\demo.wbt --json
```

`world inspect` returns:

- header
- `EXTERNPROTO` lines
- robot inventory
- target robot summary
- controller bindings
- DEF map
- supported edit targets
- spatial summary
- inferred task cues

## Validate

```powershell
webots-kit world validate .\worlds\demo.wbt --json
```

The current validator checks:

- duplicate `DEF`
- missing target robot
- missing target robot controller
- malformed supported transforms
- preserve-first task-world inventory for supported node families

## Edit

```powershell
webots-kit world edit .\worlds\demo.wbt --plan .\plans\world-edit.json
```

Example plan:

```json
{
  "schema_version": 1,
  "operations": [
    {
      "type": "set_spawn",
      "translation": [-0.4, 0.1, 0.0],
      "rotation_z": 0.5
    },
    {
      "type": "add_obstacle",
      "name": "obstacle-generated",
      "position": [0.2, 0.3],
      "size": [0.1, 0.1, 0.1]
    }
  ]
}
```

Supported selector shapes:

- `by_def`
- `by_name`
- `by_type`
- `by_path`

Current operation families:

- `set_spawn`
- `set_transform`
- `set_robot_controller`
- `rename_def`
- `remove_node`
- `add_obstacle`
- `update_obstacle`
- `remove_obstacle`
- `add_wall`
- `update_wall`
- `remove_wall`
- `add_landmark`
- `update_landmark`
- `remove_landmark`
- `add_zone`
- `update_zone`
- `remove_zone`
- `add_prop`
- `update_prop`
- `remove_prop`

## From-scratch world authoring

The main from-scratch path is still the `scenario` flow rather than a separate `world init` command:

```powershell
webots-kit project init .\demo-project
webots-kit scenario init .\demo-project\scenarios\demo-waypoint --template epuck-waypoint
webots-kit scenario validate .\demo-project\scenarios\demo-waypoint\webots-kit.scenario.json
webots-kit scenario build .\demo-project\scenarios\demo-waypoint\webots-kit.scenario.json
```

Richer generated scenarios can now carry:

- `layout.walls[]`
- `layout.landmarks[]`
- `layout.zones[]`
- `layout.props[]`

`scenario validate` and `scenario doctor` now surface authoring-specific checks such as:

- wall overlap
- blocked spawn states
- zone bounds
- landmark name collisions
- obstacle/prop collisions

`scenario build` writes these structures into the generated `.wbt` and stores additive authoring metadata such as `recommended_next_edit_ops`, `world_inventory_summary`, and `benchmark_mapping` in `webots-kit.generated.json`.

## Recommended loop

1. `world inspect`
2. `world validate`
3. `world edit`
4. `world validate`
5. `session start`
6. `benchmark run` when the world maps to a benchmarked task
