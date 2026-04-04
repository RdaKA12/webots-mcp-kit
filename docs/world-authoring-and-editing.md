# World Authoring and Editing

This page documents the world authoring/editing surface in `v2.5.0-alpha.1`.

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

Supported robot profiles:

- `e-puck`
- preview `monsterborg-4wd`

The current release line keeps the general-scene inspection layer and mutation support:

- nested `node_tree`
- `def_use_map`
- field inventories per node
- editability and supported mutation modes per node
- opaque interstitial region reporting
- preserve-first generic node clone/move/reorder support
- `Shape` geometry and appearance replacement
- frozen top-level `status` / `summary` / `support_tier` / `next_step` shapes across inspect, validate, and edit

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
- nested `node_tree`
- `field_inventory`
- `def_use_map`
- `editability`
- `opaque_regions`
- `preserve_notes`
- controller bindings
- DEF map
- supported edit targets
- spatial summary
- inferred task cues
- explicit `status`, `summary`, `support_tier`, and `next_step`

## Validate

```powershell
webots-kit world validate .\worlds\demo.wbt --json
```

The current validator checks:

- duplicate `DEF`
- broken `USE`
- missing target robot
- missing target robot controller
- malformed supported transforms
- duplicate node paths
- preserve-first task-world inventory for supported node families
- explicit `status`, `summary`, `support_tier`, and `next_step`

## Edit

```powershell
webots-kit world edit .\worlds\demo.wbt --plan .\plans\world-edit.json
```

Use `--json` when an agent needs the frozen machine-readable payload:

```powershell
webots-kit world edit .\worlds\demo.wbt --plan .\plans\world-edit.json --json
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
- `by_parent_path`
- `by_child_index`

Current operation families:

- `set_spawn`
- `set_transform`
- `set_field`
- `unset_field`
- `set_robot_controller`
- `rename_def`
- `remove_node`
- `remove_child`
- `add_node`
- `insert_child`
- `clone_node`
- `move_node`
- `reorder_children`
- `replace_geometry`
- `replace_appearance`
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

Frozen top-level edit payload keys:

- `status`
- `summary`
- `changed_paths`
- `issues`
- `warnings`
- `validation`
- `support_tier`
- `next_step`

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

Status note:

- world authoring and editing is supported on the stable release line
- deeper plan/schema details remain `experimental-foundation` and additive
- a ready sample workspace is available under `examples/getting-started/world-edit`

Next: continue with [Project import and session replay](./project-import-and-replay.md) if you need to bring an existing world into a kit-managed workflow.
