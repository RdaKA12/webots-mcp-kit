from __future__ import annotations

import json
from pathlib import Path

from webots_mcp_kit.controller_validation import validate_controller
from webots_mcp_kit.models import SessionManifest
from webots_mcp_kit.scenario_ops import (
    build_scenario,
    export_session,
    format_scenario_doctor_report,
    format_scenario_validation_report,
    format_session_replay,
    import_project,
    init_project,
    init_scenario,
    replay_session,
    scenario_doctor,
    validate_scenario,
)
from webots_mcp_kit.session_store import SessionStore
from webots_mcp_kit.utils import utc_now_iso


def test_project_init_creates_manifest(tmp_path: Path) -> None:
    project_root = tmp_path / "kit-project"
    payload = init_project(project_root)
    manifest = json.loads((project_root / "webots-kit.project.json").read_text(encoding="utf-8"))
    assert payload["project_root"] == str(project_root)
    assert payload["support_tier"] == "experimental-foundation"
    assert manifest["project_name"] == "kit-project"
    assert (project_root / "scenarios").exists()


def test_scenario_init_validate_build_creates_assets(tmp_path: Path) -> None:
    project_root = tmp_path / "generated-project"
    init_project(project_root)
    scenario_dir = project_root / "scenarios" / "demo-waypoint"
    init_scenario(scenario_dir, template="epuck-waypoint")

    report = validate_scenario(scenario_dir / "webots-kit.scenario.json")
    assert report.valid is True
    assert report.benchmark_name == "waypoint-nav"
    assert "summary:" in format_scenario_validation_report(report)

    generated = build_scenario(scenario_dir / "webots-kit.scenario.json")
    world_path = Path(generated.world_path)
    controller_path = Path(generated.controller_path)

    assert world_path.exists()
    assert controller_path.exists()
    assert Path(generated.benchmark_config_path).exists()
    assert "RectangleArena" in world_path.read_text(encoding="utf-8")
    assert "goal-region" in world_path.read_text(encoding="utf-8")

    validation = validate_controller(controller_path, scenario="waypoint-nav", strict=False)
    assert validation.valid is True


def test_line_track_build_writes_track_segments(tmp_path: Path) -> None:
    project_root = tmp_path / "line-project"
    init_project(project_root)
    scenario_dir = project_root / "scenarios" / "demo-line"
    init_scenario(scenario_dir, template="epuck-line-track")
    generated = build_scenario(scenario_dir / "webots-kit.scenario.json")
    world_text = Path(generated.world_path).read_text(encoding="utf-8")
    assert "line-segment-1" in world_text


def test_scenario_doctor_reports_ready_for_valid_spec(tmp_path: Path) -> None:
    project_root = tmp_path / "doctor-project"
    init_project(project_root)
    scenario_dir = project_root / "scenarios" / "doctor-waypoint"
    init_scenario(scenario_dir, template="epuck-waypoint")
    payload = scenario_doctor(scenario_dir / "webots-kit.scenario.json")
    assert payload["status"] == "ready"
    assert payload["support_tier"] == "experimental-foundation"
    assert payload["benchmark_ready"] is True
    assert payload["mcp_ready"] is True
    assert "support_tier: experimental-foundation" in format_scenario_doctor_report(payload)


def test_project_import_creates_metadata(tmp_path: Path) -> None:
    world = tmp_path / "sample.wbt"
    controller = tmp_path / "agent.py"
    world.write_text("#VRML_SIM R2025a utf8\nWorldInfo { title \"waypoint\" }\n", encoding="utf-8")
    controller.write_text("print('controller')\n", encoding="utf-8")

    payload = import_project(world=world, controller=controller, project_root=tmp_path / "imported-project")
    metadata_path = Path(payload["scenario_metadata_path"])
    assert metadata_path.exists()
    imported = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert imported["import_source"]["world_path"] == str(world)
    assert payload["support_tier"] == "experimental-foundation"


def test_export_and_replay_session(tmp_path: Path, monkeypatch) -> None:
    store = SessionStore(root=tmp_path / "sessions")
    session_dir = store.create_session_dir("session123")
    manifest = SessionManifest(
        session_id="session123",
        host="127.0.0.1",
        port=5555,
        daemon_pid=1234,
        status="failed",
        scenario="waypoint-nav",
        world="world.wbt",
        mode="fast",
        render=False,
        robot_controller="controller.py",
        target_robot_name="epuck-demo",
        target_robot_def="EPUCK",
        created_at=utc_now_iso(),
        session_dir=str(session_dir),
        artifacts_dir=str(session_dir / "artifacts"),
        last_error="Render init failed.",
        last_error_code="render-init-failed",
        environment={"python_executable": "python.exe", "webots_executable": "webots.exe"},
    )
    store.write_manifest(manifest)
    (session_dir / "artifacts" / "daemon.stdout.log").write_text("daemon\n", encoding="utf-8")

    def fake_collect_runtime_diagnostics(*, output_dir: Path, session_id: str | None = None) -> dict[str, object]:
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "session_id": session_id,
            "runtime_environment": {"python_executable": "python.exe"},
        }
        (output_dir / "doctor.json").write_text(json.dumps({"status": "ready"}), encoding="utf-8")
        (output_dir / "summary.json").write_text(json.dumps(payload), encoding="utf-8")
        (output_dir / "session.json").write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
        (output_dir / "inspect.json").write_text(
            json.dumps({"session_state": {"status": manifest.status, "last_error_code": manifest.last_error_code, "last_error": manifest.last_error}}),
            encoding="utf-8",
        )
        (output_dir / "log_inventory.json").write_text("[]", encoding="utf-8")
        (output_dir / "log_summary.json").write_text("{}", encoding="utf-8")
        (output_dir / "runtime_environment.json").write_text(json.dumps(payload["runtime_environment"]), encoding="utf-8")
        return payload

    monkeypatch.setattr("webots_mcp_kit.scenario_ops.collect_runtime_diagnostics", fake_collect_runtime_diagnostics)
    exported = export_session("session123", output=tmp_path / "export", store=store)
    replay = replay_session(Path(exported.export_manifest_path))

    assert Path(exported.export_dir).exists()
    assert Path(exported.doctor_path).exists()
    assert Path(exported.summary_path).exists()
    assert Path(exported.export_manifest_path).exists()
    assert replay["session_id"] == "session123"
    assert replay["last_error_code"] == "render-init-failed"
    assert replay["session_state"]["status"] == "failed"
    assert replay["support_tier"] == "experimental-foundation"
    assert "session_state_status: failed" in format_session_replay(replay)
    assert "summary:" in format_session_replay(replay)
