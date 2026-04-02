from __future__ import annotations

from pathlib import Path

from webots_mcp_kit.world_document import load_wbt_document, render_wbt_document
from webots_mcp_kit.world_ops import edit_world, inspect_world, validate_world


def _bundled_world_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "webots_mcp_kit" / "examples" / name / "worlds" / f"{name.replace('-', '_')}_benchmark.wbt"


def test_parse_and_render_round_trip_bundled_world() -> None:
    path = _bundled_world_path("line-follower")
    original = path.read_text(encoding="utf-8")
    document = load_wbt_document(path)

    assert render_wbt_document(document) == original
    assert document.title == "webots-mcp-kit Line Follower"
    assert document.externprotos


def test_inspect_world_reports_supported_edit_targets() -> None:
    path = _bundled_world_path("line-follower")
    result = inspect_world(path)

    assert result["status"] == "ready"
    assert result["summary"]["node_count"] >= 4
    assert result["summary"]["target_robot_found"] is True
    assert result["target_robot"]["name"] == "epuck-line-follower"
    assert result["target_robot"]["controller"] == "<extern>"
    assert any(target["type"] == "Solid" for target in result["supported_edit_targets"])
    assert any(binding["type"] == "E-puck" for binding in result["controller_bindings"])


def test_validate_detects_duplicate_def_and_missing_controller(tmp_path: Path) -> None:
    world = tmp_path / "broken.wbt"
    world.write_text(
        """#VRML_SIM R2025a utf8

EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/robots/gctronic/e-puck/protos/E-puck.proto"

DEF BOX Solid {
  translation 0 0 0
  name "box"
}
DEF BOX Solid {
  translation 0 1 0
  name "box-2"
}
DEF BOT E-puck {
  translation 0 0 0
  name "bot"
}
Solid {
  children [
    USE MISSING
  ]
  name "loose-solid"
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = validate_world(world)

    codes = {issue["code"] for issue in result["issues"]}
    assert result["valid"] is False
    assert "duplicate-def" in codes
    assert "missing-controller" in codes
    assert "broken-use-reference" in codes


def test_edit_world_preserves_unrelated_text_and_supports_selectors(tmp_path: Path) -> None:
    world = tmp_path / "editable.wbt"
    world.write_text(
        """#VRML_SIM R2025a utf8
# preserved comment

WorldInfo {
  title "editable world"
}
DEF BOT E-puck {
  translation 0 0 0
  name "bot"
  controller "<extern>"
}
WoodenBox {
  translation 0.2 0.3 0.05
  rotation 0 0 1 0
  name "crate"
  size 0.1 0.1 0.1
}
Robot {
  translation 0 -0.95 0.03
  name "kit-supervisor"
  controller "<extern>"
  supervisor TRUE
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = edit_world(
        world,
        {
            "operations": [
                {
                    "type": "set_spawn",
                    "selector": {"by_def": "BOT"},
                    "translation": [0.1, 0.2, 0.0],
                    "rotation": [0.0, 0.0, 1.0, 0.5],
                },
                {
                    "type": "set_robot_controller",
                    "selector": {"by_name": "bot"},
                    "controller": "controllers/agent.py",
                },
                {
                    "type": "update_obstacle",
                    "selector": {"by_type": "WoodenBox"},
                    "translation": [0.4, 0.5, 0.05],
                    "size": [0.2, 0.2, 0.2],
                },
                {
                    "type": "add_obstacle",
                    "node": {
                        "type": "WoodenBox",
                        "name": "temp-box",
                        "translation": [0.5, 0.0, 0.05],
                        "rotation": [0.0, 0.0, 1.0, 0.0],
                        "size": [0.1, 0.1, 0.1],
                    },
                },
                {
                    "type": "remove_node",
                    "selector": {"by_path": "nodes/4"},
                },
            ]
        },
    )

    text = world.read_text(encoding="utf-8")
    assert result["validation"]["valid"] is True
    assert "# preserved comment" in text
    assert 'controller "controllers/agent.py"' in text
    assert "translation 0.1 0.2 0" in text
    assert "translation 0.4 0.5 0.05" in text
    assert "temp-box" not in text


def test_edit_world_can_rename_and_remove(tmp_path: Path) -> None:
    world = tmp_path / "rename_remove.wbt"
    world.write_text(
        """#VRML_SIM R2025a utf8
DEF A Solid {
  translation 0 0 0
  name "alpha"
}
Robot {
  translation 0 0 0
  name "kit-supervisor"
  controller "<extern>"
  supervisor TRUE
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = edit_world(
        world,
        {
            "operations": [
                {"type": "rename_def", "selector": {"by_def": "A"}, "def_name": "RENAMED"},
                {
                    "type": "set_transform",
                    "selector": {"by_def": "RENAMED"},
                    "translation": [1.0, 2.0, 0.0],
                    "rotation": [0.0, 0.0, 1.0, 0.25],
                },
            ]
        },
    )

    assert result["validation"]["valid"] is True
    text = world.read_text(encoding="utf-8")
    assert "DEF RENAMED Solid" in text
    assert "translation 1 2 0" in text
    assert "rotation 0 0 1 0.25" in text
