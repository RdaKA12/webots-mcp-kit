from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from pathlib import Path
from typing import Any

__all__ = [
    "WbtChunk",
    "WbtDocument",
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
SUPERIOR_RE = re.compile(r'(?m)^\s*supervisor\s+TRUE\s*$')


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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

    def render(self) -> str:
        return "".join(chunk.text for chunk in self.chunks)

    def replace_node_raw(self, index: int, new_raw: str) -> None:
        node = self.nodes[index]
        node.raw = new_raw
        self.chunks[node.chunk_index].text = new_raw

    def delete_node(self, index: int) -> None:
        node = self.nodes[index]
        self.chunks[node.chunk_index].text = ""
        node.raw = ""
        node.editable = False

    def append_node_raw(self, new_raw: str) -> int:
        node_index = len(self.nodes)
        if self.chunks and self.chunks[-1].node_index is None:
            if self.chunks[-1].text and not self.chunks[-1].text.endswith("\n"):
                self.chunks[-1].text += "\n"
            chunk_index = len(self.chunks) - 1
            self.chunks.insert(chunk_index, WbtChunk(text=new_raw, node_index=node_index))
        else:
            chunk_index = len(self.chunks)
            self.chunks.append(WbtChunk(text=new_raw, node_index=node_index))
        current_text = self.render()
        node = _parse_node(new_raw, index=node_index, chunk_index=chunk_index, start=len(current_text) - len(new_raw), end=len(current_text))
        self.nodes.append(node)
        return node_index


def load_wbt_document(path: Path) -> WbtDocument:
    return parse_wbt_document(path.read_text(encoding="utf-8"), path=path)


def parse_wbt_document(text: str, path: Path | None = None) -> WbtDocument:
    chunks: list[WbtChunk] = []
    nodes: list[WbtNode] = []
    externprotos = EXTERNPROTO_RE.findall(text)
    title_match = TITLE_RE.search(text)
    title = title_match.group(1) if title_match else None

    spans = list(_iter_top_level_spans(text))
    cursor = 0
    for node_index, (start, end) in enumerate(spans):
        if cursor < start:
            chunks.append(WbtChunk(text=text[cursor:start]))
        raw = text[start:end]
        node = _parse_node(raw, index=node_index, chunk_index=len(chunks), start=start, end=end)
        nodes.append(node)
        chunks.append(WbtChunk(text=raw, node_index=node_index))
        cursor = end
    if cursor < len(text):
        chunks.append(WbtChunk(text=text[cursor:]))
    if not chunks:
        chunks = [WbtChunk(text=text)]
    return WbtDocument(path=str(path) if path else None, text=text, chunks=chunks, nodes=nodes, externprotos=externprotos, title=title)


def render_wbt_document(document: WbtDocument) -> str:
    return document.render()


def _iter_top_level_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    i = 0
    in_string = False
    in_comment = False
    escape = False
    while i < len(text):
        ch = text[i]
        if in_comment:
            if ch == "\n":
                in_comment = False
            i += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == "#":
            in_comment = True
            i += 1
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "{":
            start = text.rfind("\n", 0, i) + 1
            end = _matching_brace(text, i)
            spans.append((start, end + 1))
            i = end + 1
            continue
        i += 1
    return spans


def _matching_brace(text: str, open_index: int) -> int:
    depth = 1
    i = open_index + 1
    in_string = False
    in_comment = False
    escape = False
    while i < len(text):
        ch = text[i]
        if in_comment:
            if ch == "\n":
                in_comment = False
            i += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == "#":
            in_comment = True
            i += 1
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("Unbalanced braces in WBT document.")


def _parse_node(raw: str, *, index: int, chunk_index: int, start: int, end: int) -> WbtNode:
    header = raw.split("{", 1)[0].strip()
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
    supervisor = bool(SUPERIOR_RE.search(raw))
    editable = node_type in {"E-puck", "Robot", "Solid", "WoodenBox", "RectangleArena"}
    return WbtNode(
        index=index,
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
        editable=editable,
    )


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
