# Onboarding Flows

Use this page as the index for the authoring and runtime onboarding paths supported in the current branch preview.

## 1. Connect An Agent

Use this when you want a live Webots session plus MCP tools.

- start here: [First hour guide](./first-hour-guide.md)
- key commands:
  - `webots-kit doctor`
  - `webots-kit session start`
  - `webots-kit mcp serve`
  - `webots-kit benchmark run`

## 2. Integrate A Controller

Use this when your controller lives outside the bundled examples.

- start here: [Custom controller integration](./custom-controller-integration.md)
- key commands:
  - `webots-kit controller scaffold`
  - `webots-kit controller validate`
  - `webots-kit benchmark run`

## 3. Generate A Scenario From A Spec

Use this when you want the template-driven zero-to-sim path.

- start here: [Zero-to-sim guide](./zero-to-sim.md)
- key commands:
  - `webots-kit project init`
  - `webots-kit scenario init`
  - `webots-kit scenario validate`
  - `webots-kit scenario build`
  - `webots-kit scenario doctor`

## 4. Import And Replay

Use this when you already have a world/controller pair or a finished exported session.

- start here: [Project import and session replay](./project-import-and-replay.md)
- key commands:
  - `webots-kit project import`
  - `webots-kit session export`
  - `webots-kit session replay`

## 5. Author A World From Scratch

Use this when an agent is shaping a new task-world through `ScenarioSpec` rather than patching an existing `.wbt`.

- start here: [Zero-to-sim guide](./zero-to-sim.md)
- reference details: [World authoring and editing](./world-authoring-and-editing.md)
- key commands:
  - `webots-kit scenario init`
  - `webots-kit scenario validate`
  - `webots-kit scenario build`
  - `webots-kit scenario doctor`

## 6. Edit An Existing World

Use this when an agent needs structured visibility into an existing `.wbt` file and a safe patch plan.

- start here: [World authoring and editing](./world-authoring-and-editing.md)
- key commands:
  - `webots-kit world inspect`
  - `webots-kit world validate`
  - `webots-kit world edit`

## 7. Author A Controller From Scratch

Use this when an agent should scaffold a fresh controller and validate it against a scenario contract.

- start here: [Controller authoring and editing](./controller-authoring-and-editing.md)
- reference details: [Custom controller integration](./custom-controller-integration.md)
- key commands:
  - `webots-kit controller scaffold`
  - `webots-kit controller inspect`
  - `webots-kit controller validate`

## 8. Edit An Existing Controller

Use this when an agent needs structured controller metadata and marker-safe edits on an existing source file.

- start here: [Controller authoring and editing](./controller-authoring-and-editing.md)
- key commands:
  - `webots-kit controller inspect`
  - `webots-kit controller edit`
  - `webots-kit controller validate`
