# Version Policy

Use this page to understand which surfaces are stable and which remain additive.

## Stable Public Surface

The following are treated as stable:

- CLI command names
- MCP tool names
- `ControllerAgent.from_robot(...)`
- `begin_step()`
- `report_step(...)`
- runtime/session/benchmark command families

## Additive Surface

The following remain additive and `experimental-foundation`:

- deeper controller edit-plan schema
- deeper world edit-plan schema
- richer `ScenarioSpec` authoring fields
- import metadata enrichment
- replay summary enrichment

Policy:

- additive fields may grow
- existing documented top-level keys should not be renamed or removed
- new helper fields should preserve old consumers

## Release Interpretation

- patch releases: hotfixes, adoption fixes, docs, scripts, release-pipeline polish
- minor releases: additive workflow or schema expansion without renaming the stable surface
- major releases: only when a stable public contract must move or support boundaries change materially

## Team Guidance

When a team automates against this toolkit:

- automate against stable CLI names and documented top-level JSON keys
- do not assume additive `experimental-foundation` schemas are frozen
- pin a version when building internal team automation around starter workspaces or authoring plans

Next: use [Release checklist](./release-checklist.md) before tagging or [Upgrade guide](./upgrade-guide.md) after upgrading.
