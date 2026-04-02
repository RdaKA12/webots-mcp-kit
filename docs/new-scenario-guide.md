# Add a New Scenario

There are now two scenario paths in the toolkit:

- bundled scenarios registered in `src/webots_mcp_kit/benchmarks.py`
- generated scenarios created through `webots-kit scenario init/build`

Bundled scenarios are two-layered:

- repo-local demo assets under `examples/`
- package-local runtime assets under `src/webots_mcp_kit/examples/`

Keep both in sync when adding a scenario.

## Minimum additions

1. Add a world file.
2. Add a bundled controller file.
3. Register the scenario in `src/webots_mcp_kit/benchmarks.py`.
4. Define benchmark thresholds and required telemetry keys.
5. Add at least one registry test and one benchmark/report assertion.

## Required benchmark registry fields

- scenario name
- description
- world path
- controller path
- target robot name and DEF
- benchmark kind
- required telemetry keys
- benchmark thresholds

## Acceptance rule

A new bundled scenario is only complete when:

- `webots-kit benchmark list` shows it
- the controller validates
- the scenario can produce a JSON benchmark report

For template-driven generated scenarios, the minimum acceptance flow is:

- `webots-kit project init`
- `webots-kit scenario init`
- `webots-kit scenario validate`
- `webots-kit scenario build`
- generated world/controller can be used with `session start` and `benchmark run`
