# Onboarding Flows

Use this page to choose the shortest supported path for your job.

Team route map:

- use [Team flows](./team-flows.md) when you want the same workflow repeated across multiple developers
- use `bootstrap_workspace.ps1` when you want a ready starter workspace instead of a blank folder
- use `--robot-profile monsterborg-4wd` when you want the MonsterBorg lane instead of the default `e-puck` lane

## 1. Connect An Agent

Use this when you want a live Webots session plus MCP tools.

- start here: [First hour guide](./first-hour-guide.md)
- key commands:
  - `webots-kit doctor`
  - `webots-kit session start`
  - `webots-kit mcp serve`
  - `webots-kit benchmark run`

## 2. Write Or Edit A Controller

Use this when you want to scaffold a new controller, inspect an existing controller, or apply structured controller edits.

- start here: [Controller authoring and editing](./controller-authoring-and-editing.md)
- reference details: [Custom controller integration](./custom-controller-integration.md)
- key commands:
  - `webots-kit controller scaffold`
  - `webots-kit controller inspect`
  - `webots-kit controller edit`
  - `webots-kit controller validate`
  - `webots-kit benchmark run`

## 3. Inspect Or Edit A World

Use this when you want to inspect an existing `.wbt`, apply a structured world edit plan, or build a new task world from a spec.

- start here: [World authoring and editing](./world-authoring-and-editing.md)
- reference details: [Zero-to-sim guide](./zero-to-sim.md)
- key commands:
  - `webots-kit world inspect`
  - `webots-kit world validate`
  - `webots-kit world edit`
  - `webots-kit scenario validate`
  - `webots-kit scenario build`

## 4. Import And Replay

Use this when you already have a world/controller pair or an exported session that needs triage.

- start here: [Project import and session replay](./project-import-and-replay.md)
- key commands:
  - `webots-kit project import`
  - `webots-kit session export`
  - `webots-kit session replay`

Next: go to [First hour guide](./first-hour-guide.md) if you have not completed the install and runtime verify path yet.
