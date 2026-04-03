from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from pathlib import Path
from typing import Any

__all__ = [
    "WbtChunk",
    "WbtDocument",
    "WbtField",
    "WbtNode",
    "load_wbt_document",
    "parse_wbt_document",
    "render_wbt_document",
]


HEADER_RE = re.compile(r"^(?:DEF\s+(?P<def_name>[A-Za-z0-9_]+)\s+)?(?P<node_type>[A-Za-z0-9_+\-]+)\s*$")
EXTERNPROTO_RE = re.compile(r'^\s*EXTERNPROTO\s+"([^"]+)"', re.MULTILINE)
TITLE_RE = re.compile(r'(?m)^\s*title\s+"([^"]+)"\s*$')
NAME_RE = re.compile(r'(?m)^\s*name\s+"([^"]+)"\s*$')
CONTROLLER_RE = re.compile(r'(?m)^\s*controller\s+"([^"]+)"\s*$')
TRANSLATION_RE = re.compile(r'(?m)^\s*translation\s+([^\n]+)$')
ROTATION_RE = re.compile(r'(?m)^\s*rotation\s+([^\n]+)$')
SIZE_RE = re.compile(r'(?m)^\s*size\s+([^\n]+)$')
RADIUS_RE = re.compile(r'(?m)^\s*radius\s+([^\n]+)$')
HEIGHT_RE = re.compile(r'(?m)^\s*height\s+([^\n]+)$')
SUPERVISOR_RE = re.compile(r'(?m)^\s*supervisor\s+TRUE\s*$')
USE_RE = re.compile(r"\bUSE\s+([A-Za-z0-9_]+)\b")

GENERAL_EDITABLE_NODE_TYPES = {
    "Appearance",
    "Box",
    "Capsule",
    "Cylinder",
    "E-puck",
    "Group",
    "ImageTexture",
    "Material",
    "PBRAppearance",
    "Robot",
    "Shape",
    "Solid",
    "Sphere",
    "Transform",
}
TRANSFORMABLE_NODE_TYPES = {"E-puck", "Robot", "Solid", "Transform"}
CHILD_CONTAINER_NODE_TYPES = {"E-puck", "Group", "Robot", "Solid", "Transform"}
GEOMETRY_PARENT_TYPES = {"Shape"}
APPEARANCE_PARENT_TYPES = {"Shape"}


@dataclass(slots=True)
class WbtField:
    name: str
    kind: str
    start: int
    end: int
    value_text: str | None = None
    child_indexes: list[int] = field(default_factory=list)
    child_paths: list[str] = field(default_factory=list)
    use_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WbtNode:
    index: int
    chunk_index: int
    raw: str
    start: int
    end: int
    header: str
    node_type: str | None
    def_name: str | None
    name: str | None
    controller: str | None
    translation: list[float] | None
    rotation: list[float] | None
    size: list[float] | None
    radius: float | None
    height: float | None
    supervisor: bool
    editable: bool
    parent_index: int | None = None
    parent_path: str | None = None
    field_name: str | None = None
    child_ordinal: int | None = None
    path: str = ""
    children_indexes: list[int] = field(default_factory=list)
    children_paths: list[str] = field(default_factory=list)
    fields: list[WbtField] = field(default_factory=list)
    use_refs: list[str] = field(default_factory=list)
    editability: dict[str, Any] = field(default_factory=dict)
    preserve_notes: list[str] = field(default_factory=list)
    supported_mutation_modes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def selector_path(self) -> str:
        return self.path or _node_path_segment(self.def_name, self.name, self.node_type, self.index)

    def to_summary(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "node_path": self.selector_path(),
            "parent_path": self.parent_path,
            "children_paths": list(self.children_paths),
            "node_type": self.node_type,
            "def_name": self.def_name,
            "name": self.name,
            "field_name": self.field_name,
            "child_ordinal": self.child_ordinal,
            "translation": self.translation,
            "rotation": self.rotation,
            "controller": self.controller,
            "editable": self.editable,
            "supported_mutation_modes": list(self.supported_mutation_modes),
            "field_inventory": [item.to_dict() for item in self.fields],
        }


@dataclass(slots=True)
class WbtChunk:
    text: str
    node_index: int | None = None


@dataclass(slots=True)
class WbtDocument:
    path: str | None
    text: str
    chunks: list[WbtChunk] = field(default_factory=list)
    nodes: list[WbtNode] = field(default_factory=list)
    externprotos: list[str] = field(default_factory=list)
    title: str | None = None
    root_indexes: list[int] = field(default_factory=list)
    opaque_regions: list[dict[str, Any]] = field(default_factory=list)
    preserve_notes: list[str] = field(default_factory=list)
    def_use_map: dict[str, Any] = field(default_factory=dict)
    parse_errors: list[str] = field(default_factory=list)

    def render(self) -> str:
        return "".join(chunk.text for chunk in self.chunks) if self.chunks else self.text

    def replace_node_raw(self, index: int, new_raw: str) -> None:
        node = self.nodes[index]
        if node.chunk_index < 0:
            raise ValueError("replace_node_raw only supports top-level nodes.")
        node.raw = new_raw
        self.chunks[node.chunk_index].text = new_raw

    def delete_node(self, index: int) -> None:
        node = self.nodes[index]
        if node.chunk_index < 0:
            raise ValueError("delete_node only supports top-level nodes.")
        self.chunks[node.chunk_index].text = ""
        node.raw = ""
        node.editable = False

    def append_node_raw(self, new_raw: str) -> int:
        node_index = len(self.nodes)
        insertion_index = len(self.chunks)
        if self.chunks and self.chunks[-1].node_index is None:
            if self.chunks[-1].text and not self.chunks[-1].text.endswith("\n"):
                self.chunks[-1].text += "\n"
            insertion_index = len(self.chunks) - 1
        self.chunks.insert(insertion_index, WbtChunk(text=new_raw, node_index=node_index))
        rendered = self.render()
        start = rendered.rfind(new_raw)
        if start < 0:
            start = len(rendered) - len(new_raw)
        end = start + len(new_raw)
        node = _parse_node_recursive(
            rendered,
            start,
            end,
            path_parent="/World",
            parent_index=None,
            field_name=None,
            child_ordinal=len([index for index in self.root_indexes]),
            chunk_index=insertion_index,
            document=self,
        )
        self.root_indexes.append(node.index)
        _finalize_document(self)
        return node.index


def load_wbt_document(path: Path) -> WbtDocument:
    return parse_wbt_document(path.read_text(encoding="utf-8"), path=path)


def parse_wbt_document(text: str, path: Path | None = None) -> WbtDocument:
    chunks: list[WbtChunk] = []
    externprotos = EXTERNPROTO_RE.findall(text)
    title_match = TITLE_RE.search(text)
    title = title_match.group(1) if title_match else None
    spans = list(_iter_top_level_spans(text))
    document = WbtDocument(path=str(path) if path else None, text=text, chunks=chunks, externprotos=externprotos, title=title)
    cursor = 0
    for root_ordinal, (start, end) in enumerate(spans):
        if cursor < start:
            chunks.append(WbtChunk(text=text[cursor:start]))
        chunk_index = len(chunks)
        raw = text[start:end]
        chunks.append(WbtChunk(text=raw, node_index=len(document.nodes)))
        node = _parse_node_recursive(
            text,
            start,
            end,
            path_parent="/World",
            parent_index=None,
            field_name=None,
            child_ordinal=root_ordinal,
            chunk_index=chunk_index,
            document=document,
        )
        document.root_indexes.append(node.index)
        cursor = end
    if cursor < len(text):
        chunks.append(WbtChunk(text=text[cursor:]))
    if not chunks:
        chunks.append(WbtChunk(text=text))
    _finalize_document(document)
    return document


def render_wbt_document(document: WbtDocument) -> str:
    return document.render()


def _finalize_document(document: WbtDocument) -> None:
    for node in document.nodes:
        node.children_paths = [document.nodes[index].selector_path() for index in node.children_indexes if index < len(document.nodes)]
        for field in node.fields:
            field.child_paths = [document.nodes[index].selector_path() for index in field.child_indexes if index < len(document.nodes)]
        node.editability = _build_editability(node)
        node.supported_mutation_modes = list(node.editability.get("supported_mutation_modes", []))
        node.preserve_notes = _build_preserve_notes(node)
    document.def_use_map = _build_def_use_map(document.nodes)
    document.opaque_regions = _build_opaque_regions(document)
    document.preserve_notes = [
        "Inter-node text, comments, and unsupported fields remain preserved verbatim.",
        "Unsupported mutations should fail fast instead of silently rewriting the world.",
    ]


def _parse_node_recursive(
    text: str,
    start: int,
    end: int,
    *,
    path_parent: str,
    parent_index: int | None,
    field_name: str | None,
    child_ordinal: int | None,
    chunk_index: int,
    document: WbtDocument,
) -> WbtNode:
    raw = text[start:end]
    open_brace = raw.find("{")
    if open_brace < 0:
        raise ValueError("Node block is missing an opening brace.")
    header = raw[:open_brace].strip()
    match = HEADER_RE.match(header)
    node_type = match.group("node_type") if match else None
    def_name = match.group("def_name") if match else None
    name = _first_string_field(raw, NAME_RE)
    controller = _first_string_field(raw, CONTROLLER_RE)
    translation = _parse_float_list(_first_field_value(raw, TRANSLATION_RE), expected=3)
    rotation = _parse_float_list(_first_field_value(raw, ROTATION_RE), expected=4)
    size = _parse_float_list(_first_field_value(raw, SIZE_RE), expected=3)
    radius = _parse_float_value(_first_field_value(raw, RADIUS_RE))
    height = _parse_float_value(_first_field_value(raw, HEIGHT_RE))
    supervisor = bool(SUPERVISOR_RE.search(raw))
    path = _compose_node_path(
        path_parent=path_parent,
        field_name=field_name,
        child_ordinal=child_ordinal,
        def_name=def_name,
        name=name,
        node_type=node_type,
        index=len(document.nodes),
    )
    node = WbtNode(
        index=len(document.nodes),
        chunk_index=chunk_index,
        raw=raw,
        start=start,
        end=end,
        header=header,
        node_type=node_type,
        def_name=def_name,
        name=name,
        controller=controller,
        translation=translation,
        rotation=rotation,
        size=size,
        radius=radius,
        height=height,
        supervisor=supervisor,
        editable=_is_editable_node(node_type),
        parent_index=parent_index,
        parent_path=path_parent if parent_index is not None else None,
        field_name=field_name,
        child_ordinal=child_ordinal,
        path=path,
    )
    document.nodes.append(node)
    body_start = start + open_brace + 1
    body_end = end - 1
    _parse_node_fields(document, node, text, body_start, body_end)
    return node


def _parse_node_fields(document: WbtDocument, node: WbtNode, text: str, body_start: int, body_end: int) -> None:
    cursor = body_start
    while cursor < body_end:
        cursor = _skip_ws_and_comments(text, cursor, body_end)
        if cursor >= body_end:
            break
        if text[cursor] in "}]":
            cursor += 1
            continue
        if not _is_identifier_start(text[cursor]):
            cursor += 1
            continue
        field_start = cursor
        field_name, cursor = _read_identifier(text, cursor, body_end)
        value_start = _skip_ws_and_comments(text, cursor, body_end)
        if value_start >= body_end:
            break
        if text[value_start] == "[":
            list_end = _matching_delimiter(text, value_start, "[", "]", body_end=body_end)
            field = WbtField(name=field_name, kind="list", start=field_start, end=list_end + 1, value_text=text[value_start : list_end + 1])
            list_cursor = value_start + 1
            child_ordinal = 0
            while list_cursor < list_end:
                list_cursor = _skip_ws_and_comments(text, list_cursor, list_end)
                if list_cursor >= list_end:
                    break
                if _starts_with_use(text, list_cursor, list_end):
                    use_name, list_cursor = _read_use_reference(text, list_cursor, list_end)
                    field.use_refs.append(use_name)
                    node.use_refs.append(use_name)
                    continue
                child_bounds = _try_node_bounds(text, list_cursor, list_end)
                if child_bounds is not None:
                    child_start, child_end = child_bounds
                    child_node = _parse_node_recursive(
                        text,
                        child_start,
                        child_end,
                        path_parent=node.selector_path(),
                        parent_index=node.index,
                        field_name=field_name,
                        child_ordinal=child_ordinal,
                        chunk_index=-1,
                        document=document,
                    )
                    field.child_indexes.append(child_node.index)
                    node.children_indexes.append(child_node.index)
                    child_ordinal += 1
                    list_cursor = child_end
                    continue
                list_cursor += 1
            if field.child_indexes:
                field.kind = "mfnode"
            node.fields.append(field)
            cursor = list_end + 1
            continue

        if _starts_with_use(text, value_start, body_end):
            use_name, use_end = _read_use_reference(text, value_start, body_end)
            node.use_refs.append(use_name)
            node.fields.append(
                WbtField(
                    name=field_name,
                    kind="use",
                    start=field_start,
                    end=_line_end(text, use_end, body_end),
                    value_text=text[value_start:use_end].strip(),
                    use_refs=[use_name],
                )
            )
            cursor = _line_end(text, use_end, body_end)
            continue

        child_bounds = _try_node_bounds(text, value_start, body_end)
        if child_bounds is not None:
            child_start, child_end = child_bounds
            child_node = _parse_node_recursive(
                text,
                child_start,
                child_end,
                path_parent=node.selector_path(),
                parent_index=node.index,
                field_name=field_name,
                child_ordinal=None,
                chunk_index=-1,
                document=document,
            )
            node.children_indexes.append(child_node.index)
            node.fields.append(
                WbtField(
                    name=field_name,
                    kind="sfnode",
                    start=field_start,
                    end=child_end,
                    value_text=text[value_start:child_end].strip(),
                    child_indexes=[child_node.index],
                )
            )
            cursor = child_end
            continue

        scalar_end = _line_end(text, value_start, body_end)
        node.fields.append(
            WbtField(
                name=field_name,
                kind="scalar",
                start=field_start,
                end=scalar_end,
                value_text=text[value_start:scalar_end].strip(),
            )
        )
        cursor = scalar_end


def _iter_top_level_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    while cursor < len(text):
        cursor = _skip_ws_and_comments(text, cursor, len(text))
        if cursor >= len(text):
            break
        bounds = _try_node_bounds(text, cursor, len(text))
        if bounds is None:
            cursor += 1
            continue
        start, end = bounds
        spans.append((start, end))
        cursor = end
    return spans


def _try_node_bounds(text: str, start: int, end: int) -> tuple[int, int] | None:
    cursor = _skip_ws_and_comments(text, start, end)
    if cursor >= end:
        return None
    header_end = cursor
    while header_end < end and text[header_end] != "{":
        if text[header_end] in "\r\n":
            return None
        if text[header_end] == "#":
            return None
        header_end += 1
    if header_end >= end or text[header_end] != "{":
        return None
    header = text[cursor:header_end].strip()
    if not HEADER_RE.match(header):
        return None
    close = _matching_delimiter(text, header_end, "{", "}", body_end=end)
    return cursor, close + 1


def _matching_delimiter(text: str, open_index: int, open_char: str, close_char: str, *, body_end: int | None = None) -> int:
    limit = len(text) if body_end is None else min(len(text), body_end)
    depth = 1
    cursor = open_index + 1
    in_string = False
    in_comment = False
    escape = False
    while cursor < limit:
        ch = text[cursor]
        if in_comment:
            if ch == "\n":
                in_comment = False
            cursor += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            cursor += 1
            continue
        if ch == "#":
            in_comment = True
            cursor += 1
            continue
        if ch == '"':
            in_string = True
            cursor += 1
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return cursor
        cursor += 1
    raise ValueError(f"Unbalanced delimiter pair '{open_char}{close_char}' in WBT document.")


def _skip_ws_and_comments(text: str, start: int, end: int) -> int:
    cursor = start
    while cursor < end:
        if text[cursor].isspace():
            cursor += 1
            continue
        if text[cursor] == "#":
            newline = text.find("\n", cursor, end)
            return end if newline < 0 else newline + 1
        break
    return cursor


def _is_identifier_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def _read_identifier(text: str, start: int, end: int) -> tuple[str, int]:
    cursor = start
    while cursor < end and (text[cursor].isalnum() or text[cursor] in {"_", "-"}):
        cursor += 1
    return text[start:cursor], cursor


def _starts_with_use(text: str, start: int, end: int) -> bool:
    if start + 3 > end or text[start : start + 3] != "USE":
        return False
    tail = text[start + 3 : min(end, start + 4)]
    return not tail or tail.isspace()


def _read_use_reference(text: str, start: int, end: int) -> tuple[str, int]:
    cursor = _skip_ws_and_comments(text, start + 3, end)
    use_name, cursor = _read_identifier(text, cursor, end)
    return use_name, cursor


def _line_end(text: str, start: int, end: int) -> int:
    newline = text.find("\n", start, end)
    return end if newline < 0 else newline + 1


def _first_string_field(raw: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(raw)
    if match:
        return match.group(1)
    return None


def _first_field_value(raw: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(raw)
    if match:
        return match.group(1).strip()
    return None


def _parse_float_list(value: str | None, *, expected: int) -> list[float] | None:
    if value is None:
        return None
    tokens = value.split()
    if len(tokens) != expected:
        return None
    try:
        return [float(token) for token in tokens]
    except ValueError:
        return None


def _parse_float_value(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.split()[0])
    except (ValueError, IndexError):
        return None


def _compose_node_path(
    *,
    path_parent: str,
    field_name: str | None,
    child_ordinal: int | None,
    def_name: str | None,
    name: str | None,
    node_type: str | None,
    index: int,
) -> str:
    if field_name is None:
        return f"{path_parent}/{_node_path_segment(def_name, name, node_type, index)}"
    if child_ordinal is None:
        return f"{path_parent}/{field_name}"
    return f"{path_parent}/{field_name}[{child_ordinal}]"


def _node_path_segment(def_name: str | None, name: str | None, node_type: str | None, index: int) -> str:
    if def_name:
        return f"DEF:{def_name}"
    if name:
        return f"NAME:{name}"
    return f"{node_type or 'Unknown'}[{index}]"


def _is_editable_node(node_type: str | None) -> bool:
    return bool(node_type and node_type in GENERAL_EDITABLE_NODE_TYPES)


def _build_editability(node: WbtNode) -> dict[str, Any]:
    supported = bool(node.editable)
    modes = ["clone_node", "move_node", "remove_node", "set_field", "unset_field"]
    if node.node_type in TRANSFORMABLE_NODE_TYPES:
        modes.append("set_transform")
    if node.node_type in CHILD_CONTAINER_NODE_TYPES:
        modes.extend(["add_node", "insert_child", "reorder_children"])
    if node.node_type in GEOMETRY_PARENT_TYPES:
        modes.append("replace_geometry")
    if node.node_type in APPEARANCE_PARENT_TYPES:
        modes.append("replace_appearance")
    if node.parent_index is not None:
        modes.append("remove_child")
    if node.def_name:
        modes.append("rename_def")
    return {
        "supported": supported,
        "reason": None if supported else f"Node type '{node.node_type}' is currently opaque for structured mutation.",
        "supported_mutation_modes": sorted(set(modes if supported else [])),
    }


def _build_preserve_notes(node: WbtNode) -> list[str]:
    notes = ["Unsupported child fields remain preserved verbatim."]
    if not node.editable:
        notes.append(f"Node type '{node.node_type}' is parsed for inspection but not rewritten structurally.")
    return notes


def _build_def_use_map(nodes: list[WbtNode]) -> dict[str, Any]:
    defs: dict[str, str] = {}
    duplicate_defs: list[str] = []
    uses: list[dict[str, Any]] = []
    references: dict[str, list[str]] = {}
    for node in nodes:
        if node.def_name:
            if node.def_name in defs:
                duplicate_defs.append(node.def_name)
            else:
                defs[node.def_name] = node.selector_path()
    for node in nodes:
        for field in node.fields:
            for use_name in field.use_refs:
                uses.append({"name": use_name, "node_path": node.selector_path(), "field": field.name})
                references.setdefault(use_name, []).append(node.selector_path())
    broken_uses = sorted({entry["name"] for entry in uses if entry["name"] not in defs})
    return {
        "defs": defs,
        "uses": uses,
        "references": references,
        "duplicate_defs": sorted(set(duplicate_defs)),
        "broken_uses": broken_uses,
    }


def _build_opaque_regions(document: WbtDocument) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    cursor = 0
    top_level_nodes = [document.nodes[index] for index in document.root_indexes]
    for node in top_level_nodes:
        if cursor < node.start and document.text[cursor:node.start].strip():
            regions.append({"start": cursor, "end": node.start, "kind": "interstitial"})
        cursor = node.end
    if cursor < len(document.text) and document.text[cursor:].strip():
        regions.append({"start": cursor, "end": len(document.text), "kind": "interstitial"})
    return regions
