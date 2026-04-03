from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .errors import KitError
from .world_document import WbtDocument, WbtNode, load_wbt_document


SUPPORTED_WORLD_EDIT_OPERATIONS = {
    "set_spawn",
    "set_line_track",
    "set_waypoints",
    "set_goal_region",
    "add_obstacle",
    "update_obstacle",
    "remove_obstacle",
    "add_wall",
    "update_wall",
    "remove_wall",
    "add_landmark",
    "update_landmark",
    "remove_landmark",
    "add_zone",
    "update_zone",
    "remove_zone",
    "add_prop",
    "update_prop",
    "remove_prop",
    "set_robot_controller",
    "rename_def",
    "set_transform",
    "remove_node",
    "remove_child",
    "set_field",
    "unset_field",
    "add_node",
    "insert_child",
}


def inspect_world(path: Path) -> dict[str, Any]:
    world_path = _resolve_world_path(path)
    document = _load_document(world_path)
    lines = document.text.splitlines()
    robots = [_node_summary(node) for node in document.nodes if node.node_type in {"E-puck", "Robot"} or node.controller is not None]
    supported_targets = [_supported_target_summary(node) for node in document.nodes if _is_supported_edit_target(node)]
    inferred_task_cues = {
        "has_line_segments": any((node.name or "").startswith("line-segment-") for node in document.nodes),
        "has_goal_region": any(node.name == "goal-region" for node in document.nodes),
        "has_obstacles": any(_classify_node_family(node) in {"obstacle", "prop"} for node in document.nodes),
        "has_walls": any(_classify_node_family(node) == "wall" for node in document.nodes),
    }
    spatial_summary = _spatial_summary(document.nodes)
    target_robot = next((node for node in robots if node["node_type"] == "E-puck"), None)
    summary = {
        "node_count": len(document.nodes),
        "target_robot_found": target_robot is not None,
        **spatial_summary,
    }
    return {
        "status": "ready",
        "world_path": str(world_path),
        "header": lines[0] if lines else None,
        "externproto": document.externprotos,
        "robots": robots,
        "target_robot": target_robot,
        "def_map": sorted(document.def_use_map.get("defs", {})),
        "controller_bindings": [_node_summary(node) for node in document.nodes if node.controller is not None],
        "supported_edit_targets": supported_targets,
        "spatial_summary": spatial_summary,
        "summary": summary,
        "scene_node_summary": summary,
        "node_tree": [_node_tree(document, index) for index in document.root_indexes],
        "field_inventory": {node.selector_path(): [field.to_dict() for field in node.fields] for node in document.nodes},
        "def_use_map": document.def_use_map,
        "editability": {node.selector_path(): node.editability for node in document.nodes},
        "opaque_regions": document.opaque_regions,
        "preserve_notes": document.preserve_notes,
        "supported_mutation_modes": {node.selector_path(): node.supported_mutation_modes for node in document.nodes if node.supported_mutation_modes},
        "inferred_task_cues": inferred_task_cues,
        "support_tier": "experimental-foundation",
        "next_step": f"Run `webots-kit world validate \"{world_path}\"` or apply `webots-kit world edit` with a plan file.",
    }


def validate_world(path: Path) -> dict[str, Any]:
    world_path = _resolve_world_path(path)
    document = _load_document(world_path)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for name in document.def_use_map.get("duplicate_defs", []):
        issues.append({"code": "duplicate-def", "message": f"DEF '{name}' is declared more than once.", "field": "def_name"})
    for name in document.def_use_map.get("broken_uses", []):
        issues.append({"code": "broken-use", "message": f"USE '{name}' does not resolve to a defined DEF.", "field": "use_refs"})

    robots = [node for node in document.nodes if node.node_type in {"E-puck", "Robot"} or node.controller is not None]
    if not robots:
        issues.append({"code": "missing-robot-node", "message": "World must contain a robot or controller-bearing node.", "field": "robots"})
    target_robot = next((node for node in robots if node.node_type == "E-puck"), None)
    if target_robot is None:
        issues.append({"code": "missing-target-robot", "message": "World does not expose an E-puck target robot.", "field": "robots"})
    elif not target_robot.controller:
        issues.append({"code": "missing-controller", "message": "Target robot does not define a controller field.", "field": target_robot.selector_path()})

    path_counts: dict[str, int] = {}
    for node in document.nodes:
        path_counts[node.selector_path()] = path_counts.get(node.selector_path(), 0) + 1
        _append_field_validation_issues(node, issues)
        if node.parent_index is not None and not node.field_name:
            issues.append(
                {
                    "code": "invalid-parent-child-placement",
                    "message": f"{node.selector_path()} is nested but does not have a parent field context.",
                    "field": node.selector_path(),
                }
            )
    for path_value, count in path_counts.items():
        if count > 1:
            issues.append({"code": "duplicate-node-path", "message": f"Node path '{path_value}' is not unique.", "field": path_value})

    if document.opaque_regions:
        warnings.append(
            {
                "code": "preserve-first-opaque-regions",
                "message": "World contains interstitial text regions that will stay preserve-first during edits.",
                "field": "opaque_regions",
            }
        )

    inspection = inspect_world(world_path)
    return {
        "world_path": str(world_path),
        "valid": not issues,
        "status": "ready" if not issues else "misconfigured",
        "issues": issues,
        "warnings": warnings,
        "supported_edit_targets": inspection["supported_edit_targets"],
        "spatial_summary": inspection["spatial_summary"],
        "summary": {**inspection["summary"], "warning_count": len(warnings)},
        "def_use_map": inspection["def_use_map"],
        "opaque_regions": inspection["opaque_regions"],
        "preserve_notes": inspection["preserve_notes"],
        "support_tier": "experimental-foundation",
        "next_step": (
            f"Apply `webots-kit world edit \"{world_path}\" --plan <world-edit.json>`."
            if not issues
            else "Fix the listed world issues before editing or starting a session."
        ),
    }


def edit_world(path: Path, plan: dict[str, Any] | Path | None = None, *, plan_path: Path | None = None) -> dict[str, Any]:
    world_path = _resolve_world_path(path)
    if isinstance(plan, dict):
        plan_payload = plan
    elif isinstance(plan, Path):
        plan_payload = json.loads(plan.read_text(encoding="utf-8"))
    elif plan_path is not None:
        plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
    else:
        raise KitError("invalid-world-edit-plan", "world edit requires an inline plan or --plan JSON path.")
    operations = plan_payload.get("operations")
    if not isinstance(operations, list):
        raise KitError("invalid-world-edit-plan", "world edit plan must define operations[].")

    text = world_path.read_text(encoding="utf-8")
    applied: list[dict[str, Any]] = []
    for operation in operations:
        if not isinstance(operation, dict):
            raise KitError("invalid-world-edit-operation", "world edit operations must be objects.")
        op_type = str(operation.get("type") or "")
        if op_type not in SUPPORTED_WORLD_EDIT_OPERATIONS:
            raise KitError(
                "unsupported-world-edit-operation",
                f"Unsupported world edit operation '{op_type}'.",
                details={"supported_operations": sorted(SUPPORTED_WORLD_EDIT_OPERATIONS)},
            )
        document = _load_document_from_text(world_path, text)
        text, summary = _apply_world_operation(document, op_type, operation)
        applied.append(summary)
    world_path.write_text(text, encoding="utf-8")
    validation = validate_world(world_path)
    return {
        "world_path": str(world_path),
        "applied_operations": applied,
        "status": validation["status"],
        "issues": validation["issues"],
        "warnings": validation.get("warnings", []),
        "validation": validation,
        "support_tier": "experimental-foundation",
        "next_step": validation["next_step"],
    }


def format_world_inspection(payload: dict[str, Any]) -> str:
    lines = [
        "world_inspect: ready",
        f"world_path: {payload['world_path']}",
        f"robots: {len(payload.get('robots', []))}",
        f"supported_edit_targets: {len(payload.get('supported_edit_targets', []))}",
        f"scene_node_summary: {payload.get('scene_node_summary')}",
        f"def_use_map: {payload.get('def_use_map')}",
        f"opaque_regions: {len(payload.get('opaque_regions', []))}",
        f"support_tier: {payload.get('support_tier')}",
        f"next_step: {payload.get('next_step')}",
    ]
    return "\n".join(lines)


def format_world_validation(payload: dict[str, Any]) -> str:
    lines = [
        f"world_validate: {payload['status']}",
        f"world_path: {payload['world_path']}",
        f"summary: {len(payload.get('issues', []))} issues",
        f"spatial_summary: {payload.get('spatial_summary')}",
    ]
    issues = payload.get("issues") or []
    if issues:
        lines.append("issues:")
        lines.extend(f"- {issue['code']}: {issue['message']}" for issue in issues)
    warnings = payload.get("warnings") or []
    if warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning['code']}: {warning['message']}" for warning in warnings)
    lines.append(f"support_tier: {payload.get('support_tier')}")
    lines.append(f"next_step: {payload.get('next_step')}")
    return "\n".join(lines)


def _load_document(path: Path) -> WbtDocument:
    try:
        return load_wbt_document(path)
    except ValueError as exc:
        raise KitError("world-parse-failed", str(exc), details={"world_path": str(path)}) from exc


def _load_document_from_text(path: Path, text: str) -> WbtDocument:
    try:
        from .world_document import parse_wbt_document

        return parse_wbt_document(text, path=path)
    except ValueError as exc:
        raise KitError("world-parse-failed", str(exc), details={"world_path": str(path)}) from exc


def _resolve_world_path(path: Path) -> Path:
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def _node_tree(document: WbtDocument, index: int) -> dict[str, Any]:
    node = document.nodes[index]
    return {
        "node_path": node.selector_path(),
        "parent_path": node.parent_path,
        "children_paths": list(node.children_paths),
        "node_type": node.node_type,
        "def_name": node.def_name,
        "name": node.name,
        "editable": node.editable,
        "supported_mutation_modes": list(node.supported_mutation_modes),
        "field_inventory": [field.to_dict() for field in node.fields],
        "children": [_node_tree(document, child_index) for child_index in node.children_indexes],
    }


def _node_summary(node: WbtNode) -> dict[str, Any]:
    return {
        "index": node.index,
        "path": node.selector_path(),
        "node_path": node.selector_path(),
        "parent_path": node.parent_path,
        "children_paths": list(node.children_paths),
        "node_type": node.node_type,
        "def_name": node.def_name,
        "name": node.name,
        "translation": node.translation,
        "rotation": node.rotation,
        "rotation_z": _rotation_z(node.rotation),
        "controller": node.controller,
        "field_name": node.field_name,
        "child_ordinal": node.child_ordinal,
    }


def _spatial_summary(nodes: list[WbtNode]) -> dict[str, Any]:
    return {
        "node_count": len(nodes),
        "robot_count": sum(1 for node in nodes if _classify_node_family(node) in {"robot", "supervisor"}),
        "obstacle_count": sum(1 for node in nodes if _classify_node_family(node) == "obstacle"),
        "wall_count": sum(1 for node in nodes if _classify_node_family(node) == "wall"),
        "landmark_count": sum(1 for node in nodes if _classify_node_family(node) == "landmark"),
        "zone_count": sum(1 for node in nodes if _classify_node_family(node) == "zone"),
        "prop_count": sum(1 for node in nodes if _classify_node_family(node) == "prop"),
    }


def _append_field_validation_issues(node: WbtNode, issues: list[dict[str, Any]]) -> None:
    field_kinds = {field.name: field.kind for field in node.fields}
    if "translation" in field_kinds and node.translation is None:
        issues.append({"code": "invalid-translation", "message": f"{node.selector_path()} has an invalid translation field.", "field": node.selector_path()})
    if "rotation" in field_kinds and node.rotation is None:
        issues.append({"code": "invalid-rotation", "message": f"{node.selector_path()} has an invalid rotation field.", "field": node.selector_path()})
    if node.node_type in {"Box", "Capsule"} and "size" in field_kinds and node.size is None:
        issues.append({"code": "invalid-size", "message": f"{node.selector_path()} has an invalid size field.", "field": node.selector_path()})
    if node.node_type in {"Cylinder", "Sphere", "Capsule"} and "radius" in field_kinds and node.radius is None:
        issues.append({"code": "invalid-radius", "message": f"{node.selector_path()} has an invalid radius field.", "field": node.selector_path()})
    if node.node_type in {"Cylinder", "Capsule"} and "height" in field_kinds and node.height is None:
        issues.append({"code": "invalid-height", "message": f"{node.selector_path()} has an invalid height field.", "field": node.selector_path()})


def _supported_target_summary(node: WbtNode) -> dict[str, Any]:
    return {
        **_node_summary(node),
        "family": _classify_node_family(node),
        "selectors": _node_selectors(node),
        "field_inventory": [field.to_dict() for field in node.fields],
        "editability": node.editability,
        "supported_mutation_modes": list(node.supported_mutation_modes),
    }


def _node_selectors(node: WbtNode) -> dict[str, Any]:
    return {
        "by_def": node.def_name,
        "by_name": node.name,
        "by_type": node.node_type,
        "by_path": node.selector_path(),
        "by_parent_path": node.parent_path,
        "by_child_index": node.child_ordinal,
    }


def _is_supported_edit_target(node: WbtNode) -> bool:
    return bool(node.editable)


def _classify_node_family(node: WbtNode) -> str:
    lowered_name = (node.name or "").lower()
    lowered_type = (node.node_type or "").lower()
    if node.node_type == "E-puck":
        return "robot"
    if lowered_name == "kit-supervisor":
        return "supervisor"
    if lowered_name == "goal-region":
        return "zone"
    if lowered_name.startswith("landmark-"):
        return "landmark"
    if lowered_name.startswith("zone-"):
        return "zone"
    if lowered_name.startswith("wall") or lowered_name.startswith("wall-"):
        return "wall"
    if lowered_name.startswith("obstacle-") or lowered_type in {"woodenbox"}:
        return "obstacle"
    if lowered_name.startswith("prop-"):
        return "prop"
    if lowered_name.startswith("line-segment-") or lowered_name.startswith("floor-"):
        return "task-geometry"
    if node.controller is not None:
        return "robot"
    if node.editable:
        return "scene-node"
    return "opaque"


def _apply_world_operation(document: WbtDocument, op_type: str, operation: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if op_type == "set_spawn":
        selector = operation.get("selector") or {"by_def": "EPUCK"}
        target = _select_node(document.nodes, selector)
        updated = _replace_transform(target.raw, translation=operation.get("translation"), rotation_z=operation.get("rotation_z"))
        return _replace_node_text(document.text, target, updated), {"type": op_type, "target": target.selector_path()}
    if op_type == "set_transform":
        selector = operation.get("selector")
        target = _select_node(document.nodes, selector)
        updated = _replace_transform(target.raw, translation=operation.get("translation"), rotation_z=operation.get("rotation_z"))
        return _replace_node_text(document.text, target, updated), {"type": op_type, "target": target.selector_path()}
    if op_type == "set_robot_controller":
        selector = operation.get("selector") or {"by_def": "EPUCK"}
        target = _select_node(document.nodes, selector)
        updated = _replace_string_field(target.raw, "controller", str(operation.get("controller") or "<extern>"))
        return _replace_node_text(document.text, target, updated), {"type": op_type, "target": target.selector_path()}
    if op_type == "rename_def":
        selector = operation.get("selector")
        target = _select_node(document.nodes, selector)
        new_def = str(operation.get("def_name") or "")
        if not new_def:
            raise KitError("invalid-world-edit-operation", "rename_def requires def_name.")
        updated = re.sub(r"^DEF\s+[A-Za-z0-9_]+\s+", f"DEF {new_def} ", target.raw, count=1)
        return _replace_node_text(document.text, target, updated), {"type": op_type, "target": target.selector_path(), "def_name": new_def}
    if op_type in {"remove_node", "remove_child"}:
        selector = operation.get("selector")
        target = _select_node(document.nodes, selector)
        return _remove_node_text(document.text, target), {"type": op_type, "target": target.selector_path()}
    if op_type == "set_field":
        selector = operation.get("selector")
        target = _select_node(document.nodes, selector)
        field_name = str(operation.get("field") or "")
        updated = _set_generic_field(target, field_name, operation)
        return _replace_node_text(document.text, target, updated), {"type": op_type, "target": target.selector_path(), "field": field_name}
    if op_type == "unset_field":
        selector = operation.get("selector")
        target = _select_node(document.nodes, selector)
        field_name = str(operation.get("field") or "")
        updated = _unset_generic_field(target, field_name)
        return _replace_node_text(document.text, target, updated), {"type": op_type, "target": target.selector_path(), "field": field_name}
    if op_type in {"add_node", "insert_child"}:
        node_raw = str(operation.get("node_raw") or "").strip()
        if not node_raw:
            raise KitError("invalid-world-edit-operation", f"{op_type} requires node_raw.")
        if op_type == "add_node" and not operation.get("parent_selector") and not operation.get("selector"):
            return _insert_before_supervisor(document.text, node_raw), {"type": op_type, "parent": "/World"}
        parent_selector = operation.get("parent_selector") or operation.get("selector")
        parent = _select_node(document.nodes, parent_selector)
        field_name = str(operation.get("field") or "children")
        updated = _insert_child_raw(parent, field_name, node_raw)
        return _replace_node_text(document.text, parent, updated), {
            "type": op_type,
            "parent": parent.selector_path(),
            "field": field_name,
        }

    family, mode = _operation_family_mode(op_type)
    if mode == "add":
        block = _build_family_block(family, operation)
        return _insert_before_supervisor(document.text, block), {"type": op_type, "family": family}
    selector = operation.get("selector")
    target = _select_node(document.nodes, selector)
    if mode == "remove":
        return _remove_node_text(document.text, target), {"type": op_type, "target": target.selector_path()}
    replacement = _build_family_block(
        family,
        {
            **operation,
            "name": operation.get("name") or target.name,
            "def_name": operation.get("def_name") or target.def_name,
        },
    )
    return _replace_node_text(document.text, target, replacement), {"type": op_type, "target": target.selector_path()}


def _operation_family_mode(op_type: str) -> tuple[str, str]:
    if op_type.startswith("add_"):
        return op_type.removeprefix("add_"), "add"
    if op_type.startswith("update_"):
        return op_type.removeprefix("update_"), "update"
    if op_type.startswith("remove_"):
        return op_type.removeprefix("remove_"), "remove"
    if op_type == "set_goal_region":
        return "zone", "add"
    raise KitError("unsupported-world-edit-operation", f"Unsupported world edit operation '{op_type}'.")


def _select_node(nodes: list[WbtNode], selector: Any) -> WbtNode:
    if not isinstance(selector, dict):
        raise KitError("invalid-world-selector", "world edit operations require a selector object.")
    matches = list(nodes)
    if selector.get("by_def") is not None:
        matches = [node for node in matches if node.def_name == str(selector["by_def"])]
    if selector.get("by_name") is not None:
        matches = [node for node in matches if node.name == str(selector["by_name"])]
    if selector.get("by_type") is not None:
        matches = [node for node in matches if node.node_type == str(selector["by_type"])]
    if selector.get("by_path") is not None:
        path_value = str(selector["by_path"])
        matches = [node for node in matches if node.selector_path() == path_value]
    if selector.get("by_parent_path") is not None:
        matches = [node for node in matches if node.parent_path == str(selector["by_parent_path"])]
    if selector.get("by_child_index") is not None:
        try:
            ordinal = int(selector["by_child_index"])
        except (TypeError, ValueError) as exc:
            raise KitError("invalid-world-selector", "by_child_index must be an integer.") from exc
        matches = [node for node in matches if node.child_ordinal == ordinal]
    if not matches:
        raise KitError("world-selector-not-found", "Unable to find a world node matching the selector.", details={"selector": selector})
    if len(matches) > 1:
        raise KitError("world-selector-ambiguous", "Selector matched more than one world node.", details={"selector": selector})
    return matches[0]


def _replace_node_text(text: str, node: WbtNode, replacement: str) -> str:
    return text[: node.start] + replacement + text[node.end :]


def _remove_node_text(text: str, node: WbtNode) -> str:
    return text[: node.start] + text[node.end :]


def _insert_before_supervisor(text: str, block: str) -> str:
    document = _load_document_from_text(Path.cwd() / "inline.wbt", text)
    supervisor = next((node for node in document.nodes if (node.name or "") == "kit-supervisor"), None)
    normalized = block.rstrip() + "\n"
    if supervisor is None:
        return text.rstrip() + "\n\n" + normalized
    return text[: supervisor.start] + normalized + "\n" + text[supervisor.start :]


def _replace_transform(raw: str, *, translation: Any = None, rotation_z: Any = None) -> str:
    updated = raw
    if translation is not None:
        if not isinstance(translation, list) or len(translation) != 3:
            raise KitError("invalid-world-edit-operation", "translation must be a three-item numeric list.")
        updated = _replace_numeric_field(updated, "translation", translation)
    if rotation_z is not None:
        updated = _replace_numeric_field(updated, "rotation", [0.0, 0.0, 1.0, float(rotation_z)])
    return updated


def _replace_numeric_field(raw: str, field: str, values: list[float]) -> str:
    replacement = f"{field} " + " ".join(_fmt(value) for value in values)
    pattern = rf"(?m)^(\s*){re.escape(field)}\s+[^\n]+$"
    if re.search(pattern, raw):
        return re.sub(pattern, rf"\1{replacement}", raw, count=1)
    insertion_point = raw.find("\n")
    if insertion_point == -1:
        return raw
    return raw[: insertion_point + 1] + f"  {replacement}\n" + raw[insertion_point + 1 :]


def _replace_string_field(raw: str, field: str, value: str) -> str:
    replacement = f'{field} "{value}"'
    pattern = rf'(?m)^(\s*){re.escape(field)}\s+"[^"]*"$'
    if re.search(pattern, raw):
        return re.sub(pattern, rf"\1{replacement}", raw, count=1)
    insertion_point = raw.find("\n")
    if insertion_point == -1:
        return raw
    return raw[: insertion_point + 1] + f"  {replacement}\n" + raw[insertion_point + 1 :]


def _set_generic_field(target: WbtNode, field_name: str, operation: dict[str, Any]) -> str:
    if not field_name:
        raise KitError("invalid-world-edit-operation", "set_field requires field.")
    value_text = operation.get("value_text")
    if not isinstance(value_text, str):
        if "value" not in operation:
            raise KitError("invalid-world-edit-operation", "set_field requires value or value_text.")
        value_text = _serialize_field_value(operation["value"])
    pattern = rf"(?m)^(\s*){re.escape(field_name)}\s+[^\n]+$"
    if re.search(pattern, target.raw):
        return re.sub(pattern, rf"\1{field_name} {value_text}", target.raw, count=1)
    insert_at = target.raw.rfind("}")
    if insert_at < 0:
        return target.raw
    return target.raw[:insert_at] + f"  {field_name} {value_text}\n" + target.raw[insert_at:]


def _unset_generic_field(target: WbtNode, field_name: str) -> str:
    if not field_name:
        raise KitError("invalid-world-edit-operation", "unset_field requires field.")
    target_field = next((field for field in target.fields if field.name == field_name), None)
    if target_field is None:
        raise KitError("world-field-not-found", f"Field '{field_name}' does not exist on {target.selector_path()}.")
    if target_field.kind not in {"scalar", "use"}:
        raise KitError(
            "unsupported-world-field-mutation",
            f"Field '{field_name}' is {target_field.kind}; use structural edit operations instead of unset_field.",
        )
    relative_start = target_field.start - target.start
    relative_end = target_field.end - target.start
    return target.raw[:relative_start] + target.raw[relative_end:]


def _serialize_field_value(value: Any) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return _fmt(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return " ".join(_serialize_field_item(item) for item in value)
    raise KitError("unsupported-world-field-value", f"Unsupported field value type '{type(value).__name__}'.")


def _serialize_field_item(value: Any) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return _fmt(value)
    if isinstance(value, str):
        return json.dumps(value)
    raise KitError("unsupported-world-field-value", f"Unsupported list item type '{type(value).__name__}'.")


def _insert_child_raw(parent: WbtNode, field_name: str, node_raw: str) -> str:
    normalized = node_raw.rstrip()
    field = next((item for item in parent.fields if item.name == field_name), None)
    if field is not None:
        if field.kind not in {"list", "mfnode"}:
            raise KitError(
                "unsupported-world-field-mutation",
                f"Field '{field_name}' on {parent.selector_path()} is not a node list.",
            )
        insert_at = field.end - parent.start - 1
        indented = _indent_block(normalized, 4)
        prefix = "" if parent.raw[max(insert_at - 1, 0)] == "\n" else "\n"
        suffix = "\n  "
        return parent.raw[:insert_at] + prefix + indented + suffix + parent.raw[insert_at:]

    insert_at = parent.raw.rfind("}")
    if insert_at < 0:
        return parent.raw
    block = f"  {field_name} [\n{_indent_block(normalized, 4)}\n  ]\n"
    return parent.raw[:insert_at] + block + parent.raw[insert_at:]


def _indent_block(text: str, spaces: int) -> str:
    indent = " " * spaces
    return "\n".join(f"{indent}{line}" if line.strip() else line for line in text.splitlines())


def _rotation_z(values: list[float] | None) -> float | None:
    if values and len(values) == 4 and values[:3] == [0.0, 0.0, 1.0]:
        return values[3]
    return None


def _build_family_block(family: str, operation: dict[str, Any]) -> str:
    if family == "obstacle":
        return _build_obstacle_block(operation)
    if family == "wall":
        return _build_wall_block(operation)
    if family == "landmark":
        return _build_landmark_block(operation)
    if family == "zone":
        return _build_zone_block(operation)
    if family == "prop":
        return _build_prop_block(operation)
    raise KitError("unsupported-world-edit-operation", f"Unsupported world node family '{family}'.")


def _build_obstacle_block(operation: dict[str, Any]) -> str:
    name = str(operation.get("name") or "obstacle-generated")
    position = operation.get("position") or [0.0, 0.0]
    rotation_z = float(operation.get("rotation_z", 0.0))
    size = operation.get("size") or [0.1, 0.1, 0.1]
    z = float(size[2]) / 2.0
    return (
        "Solid {\n"
        f"  translation {_fmt(position[0])} {_fmt(position[1])} {_fmt(z)}\n"
        f"  rotation 0 0 1 {_fmt(rotation_z)}\n"
        "  children [\n"
        "    Shape {\n"
        "      appearance PBRAppearance {\n"
        "        baseColor 0.59 0.4 0.24\n"
        "        roughness 1\n"
        "        metalness 0\n"
        "      }\n"
        "      geometry Box {\n"
        f"        size {_fmt(size[0])} {_fmt(size[1])} {_fmt(size[2])}\n"
        "      }\n"
        "    }\n"
        "  ]\n"
        f'  name "{name}"\n'
        "  boundingObject Box {\n"
        f"    size {_fmt(size[0])} {_fmt(size[1])} {_fmt(size[2])}\n"
        "  }\n"
        "}\n"
    )


def _build_wall_block(operation: dict[str, Any]) -> str:
    name = str(operation.get("name") or "wall-generated")
    start = operation.get("start") or [-0.3, 0.0]
    end = operation.get("end") or [0.3, 0.0]
    thickness = float(operation.get("thickness", 0.02))
    height = float(operation.get("height", 0.08))
    center_x = (float(start[0]) + float(end[0])) / 2.0
    center_y = (float(start[1]) + float(end[1])) / 2.0
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    length = (dx * dx + dy * dy) ** 0.5
    rotation = 0.0 if length <= 0 else math.atan2(dy, dx)
    return (
        "Solid {\n"
        f"  translation {_fmt(center_x)} {_fmt(center_y)} {_fmt(height / 2.0)}\n"
        f"  rotation 0 0 1 {_fmt(rotation)}\n"
        "  children [\n"
        "    DEF WALL_SHAPE Shape {\n"
        "      appearance PBRAppearance {\n"
        "        baseColor 0.4 0.4 0.4\n"
        "        roughness 1\n"
        "        metalness 0\n"
        "      }\n"
        "      geometry Box {\n"
        f"        size {_fmt(length)} {_fmt(thickness)} {_fmt(height)}\n"
        "      }\n"
        "    }\n"
        "  ]\n"
        f'  name "{name}"\n'
        "  boundingObject USE WALL_SHAPE\n"
        "}\n"
    )


def _build_landmark_block(operation: dict[str, Any]) -> str:
    name = str(operation.get("name") or "landmark-generated")
    position = operation.get("position") or [0.0, 0.0]
    radius = float(operation.get("radius", 0.04))
    return (
        "Solid {\n"
        f"  translation {_fmt(position[0])} {_fmt(position[1])} 0.005\n"
        "  children [\n"
        "    Shape {\n"
        "      appearance PBRAppearance {\n"
        "        baseColor 0.15 0.3 0.9\n"
        "        roughness 1\n"
        "        metalness 0\n"
        "      }\n"
        "      geometry Cylinder {\n"
        "        height 0.01\n"
        f"        radius {_fmt(radius)}\n"
        "      }\n"
        "    }\n"
        "  ]\n"
        f'  name "{name}"\n'
        "  locked TRUE\n"
        "}\n"
    )


def _build_zone_block(operation: dict[str, Any]) -> str:
    name = str(operation.get("name") or "zone-generated")
    center = operation.get("center") or operation.get("position") or [0.0, 0.0]
    size = operation.get("size") or [0.2, 0.2]
    return (
        "Solid {\n"
        f"  translation {_fmt(center[0])} {_fmt(center[1])} 0.001\n"
        "  children [\n"
        "    Shape {\n"
        "      appearance PBRAppearance {\n"
        "        baseColor 0.08 0.7 0.38\n"
        "        transparency 0.35\n"
        "        roughness 1\n"
        "        metalness 0\n"
        "      }\n"
        "      geometry Box {\n"
        f"        size {_fmt(size[0])} {_fmt(size[1])} 0.002\n"
        "      }\n"
        "    }\n"
        "  ]\n"
        f'  name "{name}"\n'
        "  locked TRUE\n"
        "}\n"
    )


def _build_prop_block(operation: dict[str, Any]) -> str:
    name = str(operation.get("name") or "prop-generated")
    position = operation.get("position") or [0.0, 0.0]
    size = operation.get("size") or [0.08, 0.08, 0.08]
    return (
        "Solid {\n"
        f"  translation {_fmt(position[0])} {_fmt(position[1])} {_fmt(float(size[2]) / 2.0)}\n"
        "  children [\n"
        "    Shape {\n"
        "      appearance PBRAppearance {\n"
        "        baseColor 0.72 0.53 0.27\n"
        "        roughness 1\n"
        "        metalness 0\n"
        "      }\n"
        "      geometry Box {\n"
        f"        size {_fmt(size[0])} {_fmt(size[1])} {_fmt(size[2])}\n"
        "      }\n"
        "    }\n"
        "  ]\n"
        f'  name "{name}"\n'
        "  boundingObject Box {\n"
        f"    size {_fmt(size[0])} {_fmt(size[1])} {_fmt(size[2])}\n"
        "  }\n"
        "}\n"
    )


def _fmt(value: float | int) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".")
