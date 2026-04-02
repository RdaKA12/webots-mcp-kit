from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .errors import KitError
from .world_document import WbtDocument, WbtNode, load_wbt_document, parse_wbt_document

__all__ = ["edit_world", "inspect_world", "validate_world"]


EDITABLE_NODE_TYPES = {"E-puck", "Robot", "Solid", "WoodenBox", "RectangleArena"}
ROBOT_NODE_TYPES = {"E-puck", "Robot"}


def inspect_world(path: Path) -> dict[str, Any]:
    document = load_wbt_document(path)
    return _inspect_document(document, path=str(path))


def validate_world(path: Path) -> dict[str, Any]:
    document = load_wbt_document(path)
    return _validate_document(document, path=str(path))


def edit_world(path: Path, plan: dict[str, Any] | list[dict[str, Any]] | str | Path) -> dict[str, Any]:
    document = load_wbt_document(path)
    operations = _load_operations(plan)
    applied: list[dict[str, Any]] = []
    edited_nodes: list[dict[str, Any]] = []

    for operation in operations:
        op_type = operation.get("type")
        if not isinstance(op_type, str) or not op_type:
            raise KitError("world-edit-plan-invalid", "Each world edit operation needs a non-empty `type`.")
        if op_type in {"set_spawn", "set_transform"}:
            node = _resolve_node(document, operation.get("selector"), default_target=True)
            new_raw = _apply_transform_edit(node.raw, translation=operation.get("translation"), rotation=operation.get("rotation"))
            document.replace_node_raw(node.index, new_raw)
            if operation.get("translation") is not None:
                node.translation = [float(value) for value in operation["translation"]]
            if operation.get("rotation") is not None:
                node.rotation = [float(value) for value in operation["rotation"]]
            edited_nodes.append(_node_edit_summary(document.nodes[node.index]))
        elif op_type == "set_robot_controller":
            node = _resolve_node(document, operation.get("selector"), default_target=True)
            controller = operation.get("controller")
            if not isinstance(controller, str) or not controller.strip():
                raise KitError("world-edit-plan-invalid", "set_robot_controller requires a non-empty `controller` value.")
            new_raw = _set_or_insert_field(node.raw, "controller", _quote_string(controller.strip()))
            document.replace_node_raw(node.index, new_raw)
            node.controller = controller.strip()
            edited_nodes.append(_node_edit_summary(document.nodes[node.index]))
        elif op_type == "rename_def":
            node = _resolve_node(document, operation.get("selector"), default_target=True)
            new_def = operation.get("def_name")
            if not isinstance(new_def, str) or not new_def.strip():
                raise KitError("world-edit-plan-invalid", "rename_def requires a non-empty `def_name` value.")
            new_raw = _rename_def(node.raw, new_def.strip())
            document.replace_node_raw(node.index, new_raw)
            node.def_name = new_def.strip()
            edited_nodes.append(_node_edit_summary(document.nodes[node.index]))
        elif op_type in {"add_obstacle", "add_wall", "add_landmark", "add_zone", "add_prop"}:
            spec = operation.get("node") if isinstance(operation.get("node"), dict) else operation.get("obstacle")
            if not isinstance(spec, dict):
                spec = operation
            new_raw = _build_supported_node(spec)
            node_index = document.append_node_raw(new_raw)
            edited_nodes.append(_node_edit_summary(document.nodes[node_index]))
        elif op_type in {"update_obstacle", "update_wall", "update_landmark", "update_zone", "update_prop"}:
            node = _resolve_node(document, operation.get("selector"), default_target=False)
            new_raw = node.raw
            if "translation" in operation:
                new_raw = _set_or_insert_field(new_raw, "translation", _format_vector(operation["translation"], expected=3))
                node.translation = [float(value) for value in operation["translation"]]
            if "rotation" in operation:
                new_raw = _set_or_insert_field(new_raw, "rotation", _format_vector(operation["rotation"], expected=4))
                node.rotation = [float(value) for value in operation["rotation"]]
            if "controller" in operation:
                new_raw = _set_or_insert_field(new_raw, "controller", _quote_string(str(operation["controller"])))
                node.controller = str(operation["controller"]).strip()
            if "name" in operation:
                new_raw = _set_or_insert_field(new_raw, "name", _quote_string(str(operation["name"])))
                node.name = str(operation["name"]).strip()
            if "size" in operation:
                new_raw = _set_or_insert_field(new_raw, "size", _format_vector(operation["size"], expected=3))
                node.size = [float(value) for value in operation["size"]]
            if "radius" in operation:
                new_raw = _set_or_insert_field(new_raw, "radius", _format_number(operation["radius"]))
                node.radius = float(operation["radius"])
            if "height" in operation:
                new_raw = _set_or_insert_field(new_raw, "height", _format_number(operation["height"]))
                node.height = float(operation["height"])
            document.replace_node_raw(node.index, new_raw)
            edited_nodes.append(_node_edit_summary(document.nodes[node.index]))
        elif op_type == "remove_node":
            node = _resolve_node(document, operation.get("selector"), default_target=False)
            document.delete_node(node.index)
            edited_nodes.append(_node_edit_summary(node, deleted=True))
        else:
            raise KitError("world-edit-plan-unsupported", f"Unsupported world edit operation '{op_type}'.")
        applied.append(operation)

    rendered = document.render()
    validation = _validate_document(parse_wbt_document(rendered, path=path), path=str(path))
    if not validation["valid"]:
        raise KitError(
            "world-edit-validation-failed",
            "Edited world did not pass validation.",
            details={"issues": validation["issues"]},
        )
    path.write_text(rendered, encoding="utf-8")
    return {
        "status": "ready",
        "path": str(path),
        "applied_operations": applied,
        "edited_nodes": edited_nodes,
        "validation": validation,
        "support_tier": "experimental-foundation",
        "next_step": "Run `session start` or `benchmark run` with the edited world.",
    }


def _issue(code: str, message: str, *, field: str | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "field": field, "level": "error"}


def _inspect_document(document: WbtDocument, *, path: str) -> dict[str, Any]:
    target_robot = _find_target_robot(document)
    nodes = [node.to_dict() for node in document.nodes]
    def_map = {
        node.def_name: {"index": node.index, "type": node.node_type, "name": node.name}
        for node in document.nodes
        if node.def_name
    }
    controller_bindings = [
        {
            "index": node.index,
            "selector": _preferred_selector(node),
            "type": node.node_type,
            "name": node.name,
            "controller": node.controller,
        }
        for node in document.nodes
        if node.controller
    ]
    supported_edit_targets = [
        {
            "index": node.index,
            "selector": _preferred_selector(node),
            "type": node.node_type,
            "name": node.name,
            "editable": node.editable,
        }
        for node in document.nodes
        if node.editable
    ]
    summary = {
        "node_count": len(document.nodes),
        "editable_node_count": sum(1 for node in document.nodes if node.editable),
        "externproto_count": len(document.externprotos),
        "controller_binding_count": len(controller_bindings),
        "target_robot_found": target_robot is not None,
    }
    return {
        "status": "ready",
        "path": path,
        "title": document.title,
        "externprotos": list(document.externprotos),
        "nodes": nodes,
        "def_map": def_map,
        "controller_bindings": controller_bindings,
        "supported_edit_targets": supported_edit_targets,
        "target_robot": target_robot.to_dict() if target_robot else None,
        "summary": summary,
        "support_tier": "experimental-foundation",
        "next_step": "Run `world validate` or apply a structured `world edit` plan.",
    }


def _validate_document(document: WbtDocument, *, path: str) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    defs: dict[str, int] = {}
    target_robot = _find_target_robot(document)
    use_refs = _collect_use_references(document.text)

    for node in document.nodes:
        if node.def_name:
            if node.def_name in defs:
                issues.append(_issue("duplicate-def", f"Duplicate DEF name '{node.def_name}'.", field=f"nodes[{node.index}].def"))
            else:
                defs[node.def_name] = node.index
        if node.node_type in EDITABLE_NODE_TYPES:
            if node.translation is not None and len(node.translation) != 3:
                issues.append(_issue("invalid-translation", "translation must contain three numeric values.", field=f"nodes[{node.index}].translation"))
            if node.rotation is not None and len(node.rotation) != 4:
                issues.append(_issue("invalid-rotation", "rotation must contain four numeric values.", field=f"nodes[{node.index}].rotation"))

    for ref in use_refs:
        if ref not in defs:
            issues.append(_issue("broken-use-reference", f"USE reference '{ref}' does not match a known DEF.", field="uses"))

    if target_robot is None:
        issues.append(_issue("missing-target-robot", "No editable top-level robot node with a controller was found.", field="target_robot"))
    elif not target_robot.controller:
        issues.append(_issue("missing-controller", "The target robot node is missing a controller field.", field=f"nodes[{target_robot.index}].controller"))

    summary = {
        "node_count": len(document.nodes),
        "editable_node_count": sum(1 for node in document.nodes if node.editable),
        "externproto_count": len(document.externprotos),
        "target_robot_found": target_robot is not None,
        "issue_count": len(issues),
    }
    return {
        "status": "ready" if not issues else "misconfigured",
        "path": path,
        "valid": not issues,
        "issues": issues,
        "summary": summary,
        "support_tier": "experimental-foundation",
        "next_step": "Run `world edit` with a structured plan, then rerun validation." if issues else "The world is structurally ready for supported preserve-first edits.",
    }


def _collect_use_references(text: str) -> list[str]:
    return re.findall(r"\bUSE\s+([A-Za-z0-9_]+)\b", text)


def _find_target_robot(document: WbtDocument) -> WbtNode | None:
    for node in document.nodes:
        if node.node_type not in ROBOT_NODE_TYPES:
            continue
        if node.supervisor:
            continue
        return node
    for node in document.nodes:
        if node.node_type in ROBOT_NODE_TYPES:
            return node
    return None


def _preferred_selector(node: WbtNode) -> dict[str, Any]:
    if node.def_name:
        return {"by_def": node.def_name}
    if node.name:
        return {"by_name": node.name}
    return {"by_path": f"nodes/{node.index}"}


def _node_edit_summary(node: WbtNode, *, deleted: bool = False) -> dict[str, Any]:
    return {
        "index": node.index,
        "type": node.node_type,
        "def_name": node.def_name,
        "name": node.name,
        "controller": node.controller,
        "deleted": deleted,
    }


def _load_operations(plan: dict[str, Any] | list[dict[str, Any]] | str | Path) -> list[dict[str, Any]]:
    if isinstance(plan, Path):
        payload = json.loads(plan.read_text(encoding="utf-8"))
    elif isinstance(plan, str):
        path = Path(plan)
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
        else:
            payload = json.loads(plan)
    else:
        payload = plan
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        operations = payload.get("operations")
        if isinstance(operations, list):
            return operations
    raise KitError("world-edit-plan-invalid", "World edit plan must contain an `operations` list.")


def _resolve_node(document: WbtDocument, selector: Any, *, default_target: bool) -> WbtNode:
    if selector is None and default_target:
        target = _find_target_robot(document)
        if target is None:
            raise KitError("world-edit-target-missing", "No target robot node was found for the requested operation.")
        return target
    if not isinstance(selector, dict):
        raise KitError("world-edit-selector-invalid", "World edit operations need a selector object.")
    if "by_def" in selector:
        value = selector["by_def"]
        for node in document.nodes:
            if node.def_name == value:
                return node
    if "by_name" in selector:
        value = selector["by_name"]
        for node in document.nodes:
            if node.name == value:
                return node
    if "by_type" in selector:
        value = selector["by_type"]
        for node in document.nodes:
            if node.node_type == value:
                return node
    if "by_path" in selector:
        value = selector["by_path"]
        index = _parse_index(value)
        if index is not None and 0 <= index < len(document.nodes):
            return document.nodes[index]
    raise KitError("world-edit-target-not-found", f"Could not resolve selector {selector!r}.")


def _parse_index(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        match = re.search(r"(\d+)$", value)
        if match:
            return int(match.group(1))
    return None


def _apply_transform_edit(raw: str, *, translation: Any = None, rotation: Any = None) -> str:
    new_raw = raw
    if translation is not None:
        new_raw = _set_or_insert_field(new_raw, "translation", _format_vector(translation, expected=3))
    if rotation is not None:
        new_raw = _set_or_insert_field(new_raw, "rotation", _format_vector(rotation, expected=4))
    return new_raw


def _rename_def(raw: str, new_def: str) -> str:
    return re.sub(r"^(?P<indent>\s*)DEF\s+[A-Za-z0-9_]+\s+", rf"\g<indent>DEF {new_def} ", raw, count=1, flags=re.MULTILINE)


def _set_or_insert_field(raw: str, field: str, value_text: str) -> str:
    pattern = re.compile(rf"^(?P<indent>\s*){re.escape(field)}\s+.*$", re.MULTILINE)
    replacement = None

    def _replace(match: re.Match[str]) -> str:
        nonlocal replacement
        replacement = f"{match.group('indent')}{field} {value_text}"
        return replacement

    new_raw, count = pattern.subn(_replace, raw, count=1)
    if count:
        return new_raw
    indent = re.match(r"^(?P<indent>\s*)", raw).group("indent")  # type: ignore[union-attr]
    insertion = f"{indent}  {field} {value_text}\n"
    close_index = raw.rfind("}")
    if close_index < 0:
        return raw
    before = raw[:close_index]
    after = raw[close_index:]
    if not before.endswith("\n"):
        before += "\n"
    return before + insertion + after


def _format_vector(values: Any, *, expected: int) -> str:
    if not isinstance(values, (list, tuple)) or len(values) != expected:
        raise KitError("world-edit-plan-invalid", f"Expected a {expected}-item numeric vector.")
    try:
        return " ".join(_format_number(value) for value in values)
    except (TypeError, ValueError):
        raise KitError("world-edit-plan-invalid", f"Expected a {expected}-item numeric vector.") from None


def _format_number(value: Any) -> str:
    if not isinstance(value, (int, float)):
        raise KitError("world-edit-plan-invalid", "Expected a numeric value.")
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def _quote_string(value: str) -> str:
    return json.dumps(value)


def _build_supported_node(spec: dict[str, Any]) -> str:
    node_type = str(spec.get("type") or spec.get("node_type") or spec.get("shape") or "Solid")
    name = spec.get("name")
    translation = spec.get("translation", [0.0, 0.0, 0.0])
    rotation = spec.get("rotation", [0.0, 0.0, 1.0, 0.0])
    if node_type == "WoodenBox":
        size = spec.get("size", [0.1, 0.1, 0.1])
        lines = [
            "WoodenBox {",
            f"  translation {_format_vector(translation, expected=3)}",
            f"  rotation {_format_vector(rotation, expected=4)}",
        ]
        if name:
            lines.append(f"  name {_quote_string(str(name))}")
        lines.append(f"  size {_format_vector(size, expected=3)}")
        lines.append("}")
        return "\n".join(lines)
    if node_type in {"Robot", "E-puck"}:
        controller = spec.get("controller", "<extern>")
        lines = [
            f"DEF {spec.get('def_name', 'EPUCK')} {node_type} {{",
            f"  translation {_format_vector(translation, expected=3)}",
            f"  rotation {_format_vector(rotation, expected=4)}",
        ]
        if name:
            lines.append(f"  name {_quote_string(str(name))}")
        lines.append(f"  controller {_quote_string(str(controller))}")
        lines.append("}")
        return "\n".join(lines)
    size = spec.get("size")
    radius = spec.get("radius")
    height = spec.get("height")
    shape = str(spec.get("shape") or ("cylinder" if radius is not None else "box"))
    lines = [f"{node_type} {{"]
    lines.append(f"  translation {_format_vector(translation, expected=3)}")
    lines.append(f"  rotation {_format_vector(rotation, expected=4)}")
    if shape == "cylinder" or radius is not None:
        lines.extend(
            [
                "  children [",
                "    Shape {",
                "      appearance PBRAppearance {",
                "        baseColor 0.59 0.4 0.24",
                "        roughness 1",
                "        metalness 0",
                "      }",
                "      geometry Cylinder {",
                f"        height {_format_number(height or 0.12)}",
                f"        radius {_format_number(radius or 0.06)}",
                "      }",
                "    }",
                "  ]",
            ]
        )
    else:
        lines.extend(
            [
                "  children [",
                "    Shape {",
                "      appearance PBRAppearance {",
                "        baseColor 0.59 0.4 0.24",
                "        roughness 1",
                "        metalness 0",
                "      }",
                "      geometry Box {",
                f"        size {_format_vector(size or [0.1, 0.1, 0.1], expected=3)}",
                "      }",
                "    }",
                "  ]",
            ]
        )
    if name:
        lines.append(f"  name {_quote_string(str(name))}")
    lines.append("}")
    return "\n".join(lines)
