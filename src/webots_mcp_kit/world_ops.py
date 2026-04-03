from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .errors import KitError


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
}


@dataclass(slots=True)
class ParsedWorldNode:
    index: int
    start: int
    end: int
    raw: str
    node_type: str
    def_name: str | None
    name: str | None
    translation: list[float] | None
    rotation_z: float | None
    controller: str | None

    def selector_path(self) -> str:
        if self.def_name:
            return f"/World/DEF:{self.def_name}"
        if self.name:
            return f"/World/NAME:{self.name}"
        return f"/World/{self.index}"

    def to_summary(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "path": self.selector_path(),
            "node_type": self.node_type,
            "def_name": self.def_name,
            "name": self.name,
            "translation": self.translation,
            "rotation_z": self.rotation_z,
            "controller": self.controller,
        }


@dataclass(slots=True)
class ParsedWorldDocument:
    path: str
    text: str
    nodes: list[ParsedWorldNode]

    def to_text(self) -> str:
        return self.text


def inspect_world(path: Path) -> dict[str, Any]:
    world_path = _resolve_world_path(path)
    document = parse_world_document(world_path)
    lines = document.text.splitlines()
    externproto = [line.strip() for line in lines if line.strip().startswith("EXTERNPROTO ")]
    robots = [node.to_summary() for node in document.nodes if node.node_type in {"E-puck", "Robot"} or node.controller is not None]
    supported_targets = [_supported_target_summary(node) for node in document.nodes if _is_supported_edit_target(node)]
    inferred_task_cues = {
        "has_line_segments": any((node.name or "").startswith("line-segment-") for node in document.nodes),
        "has_goal_region": any(node.name == "goal-region" for node in document.nodes),
        "has_obstacles": any(_classify_node_family(node) in {"obstacle", "prop"} for node in document.nodes),
        "has_walls": any(_classify_node_family(node) == "wall" for node in document.nodes),
    }
    spatial_summary = {
        "node_count": len(document.nodes),
        "robot_count": len(robots),
        "obstacle_count": sum(1 for node in document.nodes if _classify_node_family(node) == "obstacle"),
        "wall_count": sum(1 for node in document.nodes if _classify_node_family(node) == "wall"),
        "landmark_count": sum(1 for node in document.nodes if _classify_node_family(node) == "landmark"),
        "zone_count": sum(1 for node in document.nodes if _classify_node_family(node) == "zone"),
        "prop_count": sum(1 for node in document.nodes if _classify_node_family(node) == "prop"),
    }
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
        "externproto": externproto,
        "robots": robots,
        "target_robot": target_robot,
        "def_map": sorted(node.def_name for node in document.nodes if node.def_name),
        "controller_bindings": [node.to_summary() for node in document.nodes if node.controller is not None],
        "supported_edit_targets": supported_targets,
        "spatial_summary": spatial_summary,
        "summary": summary,
        "inferred_task_cues": inferred_task_cues,
        "support_tier": "experimental-foundation",
        "next_step": f"Run `webots-kit world validate \"{world_path}\"` or apply `webots-kit world edit` with a plan file.",
    }


def validate_world(path: Path) -> dict[str, Any]:
    world_path = _resolve_world_path(path)
    document = parse_world_document(world_path)
    issues: list[dict[str, Any]] = []
    def_names = [node.def_name for node in document.nodes if node.def_name]
    duplicates = sorted({name for name in def_names if def_names.count(name) > 1})
    for name in duplicates:
        issues.append({"code": "duplicate-def", "message": f"DEF '{name}' is declared more than once.", "field": "def_name"})
    robots = [node for node in document.nodes if node.node_type in {"E-puck", "Robot"} or node.controller is not None]
    if not robots:
        issues.append({"code": "missing-robot-node", "message": "World must contain a robot or controller-bearing node.", "field": "robots"})
    target_robot = next((node for node in robots if node.node_type == "E-puck"), None)
    if target_robot is None:
        issues.append({"code": "missing-target-robot", "message": "World does not expose an E-puck target robot.", "field": "robots"})
    elif not target_robot.controller:
        issues.append({"code": "missing-controller", "message": "Target robot does not define a controller field.", "field": target_robot.selector_path()})
    for node in document.nodes:
        if node.translation is not None and len(node.translation) != 3:
            issues.append({"code": "invalid-translation", "message": f"{node.selector_path()} has an invalid translation field.", "field": node.selector_path()})
    inspection = inspect_world(world_path)
    return {
        "world_path": str(world_path),
        "valid": not issues,
        "status": "ready" if not issues else "misconfigured",
        "issues": issues,
        "supported_edit_targets": inspection["supported_edit_targets"],
        "spatial_summary": inspection["spatial_summary"],
        "summary": inspection["summary"],
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
    document = parse_world_document(world_path)
    text = document.text
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
        document = parse_world_document_from_text(world_path, text)
        text, summary = _apply_world_operation(document, op_type, operation)
        applied.append(summary)
    world_path.write_text(text, encoding="utf-8")
    validation = validate_world(world_path)
    return {
        "world_path": str(world_path),
        "applied_operations": applied,
        "status": validation["status"],
        "issues": validation["issues"],
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
        f"spatial_summary: {payload.get('spatial_summary')}",
        f"inferred_task_cues: {payload.get('inferred_task_cues')}",
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
    lines.append(f"support_tier: {payload.get('support_tier')}")
    lines.append(f"next_step: {payload.get('next_step')}")
    return "\n".join(lines)


def parse_world_document(path: Path) -> ParsedWorldDocument:
    return parse_world_document_from_text(path, path.read_text(encoding="utf-8"))


def parse_world_document_from_text(path: Path, text: str) -> ParsedWorldDocument:
    nodes = _parse_top_level_nodes(text)
    return ParsedWorldDocument(path=str(path), text=text, nodes=nodes)


def _resolve_world_path(path: Path) -> Path:
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def _parse_top_level_nodes(text: str) -> list[ParsedWorldNode]:
    nodes: list[ParsedWorldNode] = []
    depth = 0
    node_start: int | None = None
    line_start = 0
    index = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if depth == 0 and stripped and "{" in stripped and not stripped.startswith("#") and not stripped.startswith("EXTERNPROTO"):
            if re.match(r"^(DEF\s+[A-Za-z0-9_]+\s+)?[A-Za-z0-9_+\-]+\s*{", stripped):
                node_start = line_start
        depth += line.count("{")
        depth -= line.count("}")
        line_end = line_start + len(line)
        if node_start is not None and depth == 0:
            raw = text[node_start:line_end]
            metadata = _parse_node_metadata(raw)
            nodes.append(
                ParsedWorldNode(
                    index=index,
                    start=node_start,
                    end=line_end,
                    raw=raw,
                    node_type=metadata["node_type"],
                    def_name=metadata["def_name"],
                    name=metadata["name"],
                    translation=metadata["translation"],
                    rotation_z=metadata["rotation_z"],
                    controller=metadata["controller"],
                )
            )
            index += 1
            node_start = None
        line_start = line_end
    return nodes


def _parse_node_metadata(raw: str) -> dict[str, Any]:
    header = raw.strip().splitlines()[0].strip()
    def_name: str | None = None
    node_type = "Unknown"
    match = re.match(r"^DEF\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_+\-]+)\s*{", header)
    if match:
        def_name, node_type = match.groups()
    else:
        plain = re.match(r"^([A-Za-z0-9_+\-]+)\s*{", header)
        if plain:
            node_type = plain.group(1)
    name = _search_string_field(raw, "name")
    controller = _search_string_field(raw, "controller")
    translation = _search_numeric_vector(raw, "translation", 3)
    rotation = _search_numeric_vector(raw, "rotation", 4)
    rotation_z = rotation[3] if rotation and rotation[:3] == [0.0, 0.0, 1.0] else None
    return {
        "node_type": node_type,
        "def_name": def_name,
        "name": name,
        "translation": translation,
        "rotation_z": rotation_z,
        "controller": controller,
    }


def _search_string_field(raw: str, field: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(field)}\s+\"([^\"]+)\"", raw)
    return match.group(1) if match else None


def _search_numeric_vector(raw: str, field: str, length: int) -> list[float] | None:
    match = re.search(rf"(?m)^\s*{re.escape(field)}\s+([\-0-9.eE\s]+)$", raw)
    if not match:
        return None
    try:
        values = [float(item) for item in match.group(1).split()]
    except ValueError:
        return None
    if len(values) != length:
        return None
    return values


def _supported_target_summary(node: ParsedWorldNode) -> dict[str, Any]:
    return {
        **node.to_summary(),
        "family": _classify_node_family(node),
        "selectors": _node_selectors(node),
    }


def _node_selectors(node: ParsedWorldNode) -> dict[str, Any]:
    return {
        "by_def": node.def_name,
        "by_name": node.name,
        "by_type": node.node_type,
        "by_path": node.selector_path(),
    }


def _is_supported_edit_target(node: ParsedWorldNode) -> bool:
    return _classify_node_family(node) != "opaque"


def _classify_node_family(node: ParsedWorldNode) -> str:
    lowered_name = (node.name or "").lower()
    lowered_type = node.node_type.lower()
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
    return "opaque"


def _apply_world_operation(document: ParsedWorldDocument, op_type: str, operation: dict[str, Any]) -> tuple[str, dict[str, Any]]:
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
    if op_type == "remove_node":
        selector = operation.get("selector")
        target = _select_node(document.nodes, selector)
        return _remove_node_text(document.text, target), {"type": op_type, "target": target.selector_path()}

    family, mode = _operation_family_mode(op_type)
    if mode == "add":
        block = _build_family_block(family, operation)
        return _insert_before_supervisor(document, block), {"type": op_type, "family": family}
    selector = operation.get("selector")
    target = _select_node(document.nodes, selector)
    if mode == "remove":
        return _remove_node_text(document.text, target), {"type": op_type, "target": target.selector_path()}
    replacement = _build_family_block(family, {**operation, "name": operation.get("name") or target.name, "def_name": operation.get("def_name") or target.def_name})
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


def _select_node(nodes: list[ParsedWorldNode], selector: Any) -> ParsedWorldNode:
    if not isinstance(selector, dict):
        raise KitError("invalid-world-selector", "world edit operations require a selector object.")
    matches: list[ParsedWorldNode] = []
    if selector.get("by_def"):
        value = str(selector["by_def"])
        matches = [node for node in nodes if node.def_name == value]
    elif selector.get("by_name"):
        value = str(selector["by_name"])
        matches = [node for node in nodes if node.name == value]
    elif selector.get("by_type"):
        value = str(selector["by_type"])
        matches = [node for node in nodes if node.node_type == value]
    elif selector.get("by_path"):
        value = str(selector["by_path"])
        if value.startswith("nodes/"):
            try:
                index = int(value.split("/", 1)[1])
            except ValueError:
                index = -1
            matches = [node for node in nodes if node.index == index]
        else:
            matches = [node for node in nodes if node.selector_path() == value]
    if not matches:
        raise KitError("world-selector-not-found", "Unable to find a world node matching the selector.", details={"selector": selector})
    if len(matches) > 1:
        raise KitError("world-selector-ambiguous", "Selector matched more than one world node.", details={"selector": selector})
    return matches[0]


def _replace_node_text(text: str, node: ParsedWorldNode, replacement: str) -> str:
    return text[: node.start] + replacement + text[node.end :]


def _remove_node_text(text: str, node: ParsedWorldNode) -> str:
    return text[: node.start] + text[node.end :]


def _insert_before_supervisor(document: ParsedWorldDocument, block: str) -> str:
    supervisor = next((node for node in document.nodes if (node.name or "") == "kit-supervisor"), None)
    if supervisor is None:
        return document.text.rstrip() + "\n\n" + block.rstrip() + "\n"
    return document.text[: supervisor.start] + block.rstrip() + "\n\n" + document.text[supervisor.start :]


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
    indent = "  "
    if insertion_point == -1:
        return raw
    return raw[: insertion_point + 1] + f"{indent}{replacement}\n" + raw[insertion_point + 1 :]


def _replace_string_field(raw: str, field: str, value: str) -> str:
    replacement = f'{field} "{value}"'
    pattern = rf'(?m)^(\s*){re.escape(field)}\s+"[^"]*"$'
    if re.search(pattern, raw):
        return re.sub(pattern, rf"\1{replacement}", raw, count=1)
    insertion_point = raw.find("\n")
    indent = "  "
    if insertion_point == -1:
        return raw
    return raw[: insertion_point + 1] + f"{indent}{replacement}\n" + raw[insertion_point + 1 :]


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
    rotation = 0.0 if length <= 0 else __import__("math").atan2(dy, dx)
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
