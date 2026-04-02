from __future__ import annotations

import json
from pathlib import Path

from webots_mcp_kit.controller_validation import validate_controller
from webots_mcp_kit.models import SESSION_EXPORT_ARTIFACT_STANDARD_VERSION, SESSION_EXPORT_STANDARD_ARTIFACTS, SessionExport, SessionManifest
from webots_mcp_kit.scenario_ops import (
    build_scenario,
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
    assert report.normalized["benchmark"]["profile"] == "waypoint-nav"
    assert report.normalized["environment"]["arena"]["floor"] == "plain"
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
    assert "floor-style-light" in world_text


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
    assert payload["benchmark_readiness"]["ready"] is True
    assert payload["controller_contract_readiness"]["ready"] is True
    assert payload["build_readiness"]["ready"] is True
    assert payload["runtime_smoke_readiness"]["ready"] is True
    assert "support_tier: experimental-foundation" in format_scenario_doctor_report(payload)
    assert "benchmark_readiness: True" in format_scenario_doctor_report(payload)


def test_all_builtin_templates_validate_and_build(tmp_path: Path) -> None:
    project_root = tmp_path / "all-templates"
    init_project(project_root)
    templates = {
        "epuck-line-track": "line-follow",
        "epuck-waypoint": "waypoint-nav",
        "epuck-obstacle-course": "obstacle-avoidance",
    }
    for template, expected_kind in templates.items():
        scenario_dir = project_root / "scenarios" / template
        init_scenario(scenario_dir, template=template)
        report = validate_scenario(scenario_dir / "webots-kit.scenario.json")
        assert report.valid is True
        assert report.scenario_kind == expected_kind
        generated = build_scenario(scenario_dir / "webots-kit.scenario.json")
        assert Path(generated.world_path).exists()
        assert Path(generated.controller_path).exists()


def test_validate_line_follow_rejects_dark_floor(tmp_path: Path) -> None:
    project_root = tmp_path / "dark-floor"
    init_project(project_root)
    scenario_dir = project_root / "scenarios" / "demo-line"
    init_scenario(scenario_dir, template="epuck-line-track")
    spec_path = scenario_dir / "webots-kit.scenario.json"
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    payload["environment"]["arena"]["floor"] = "dark"
    spec_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = validate_scenario(spec_path)
    assert report.valid is False
    assert any(issue.code == "unsupported-floor-task-combination" for issue in report.issues)


def test_validate_goal_region_mismatch_is_rejected(tmp_path: Path) -> None:
    project_root = tmp_path / "goal-mismatch"
    init_project(project_root)
    scenario_dir = project_root / "scenarios" / "demo-waypoint"
    init_scenario(scenario_dir, template="epuck-waypoint")
    spec_path = scenario_dir / "webots-kit.scenario.json"
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    payload["layout"]["goal_region"] = {"center": [0.1, 0.1], "radius": 0.16}
    spec_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = validate_scenario(spec_path)
    assert report.valid is False
    assert any(issue.code == "goal-region-waypoint-mismatch" for issue in report.issues)


def test_validate_obstacle_shape_field_mismatch_is_rejected(tmp_path: Path) -> None:
    project_root = tmp_path / "obstacle-mismatch"
    init_project(project_root)
    scenario_dir = project_root / "scenarios" / "demo-obstacle"
    init_scenario(scenario_dir, template="epuck-obstacle-course")
    spec_path = scenario_dir / "webots-kit.scenario.json"
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    payload["layout"]["obstacles"][0]["radius"] = 0.2
    spec_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = validate_scenario(spec_path)
    assert report.valid is False
    assert any(issue.code == "obstacle-shape-field-mismatch" for issue in report.issues)


def test_validate_line_track_out_of_bounds_is_rejected(tmp_path: Path) -> None:
    project_root = tmp_path / "line-bounds"
    init_project(project_root)
    scenario_dir = project_root / "scenarios" / "demo-line"
    init_scenario(scenario_dir, template="epuck-line-track")
    spec_path = scenario_dir / "webots-kit.scenario.json"
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    payload["layout"]["line_track"]["points"] = [[-2.5, 0.0], [2.5, 0.0]]
    spec_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = validate_scenario(spec_path)
    assert report.valid is False
    assert any(issue.code == "line-track-point-out-of-bounds" for issue in report.issues)


def test_project_import_creates_metadata(tmp_path: Path) -> None:
    world = tmp_path / "sample.wbt"
    controller = tmp_path / "agent.py"
    world.write_text(
        '#VRML_SIM R2025a utf8\nDEF IMPORTED_BOT E-puck {\n  name "imported-bot"\n  controller "<extern>"\n}\nWorldInfo { title "waypoint" }\n',
        encoding="utf-8",
    )
    controller.write_text(
        'from controller import Robot\nrobot = Robot()\ncamera = robot.getDevice("camera")\nleft = robot.getDevice("left wheel motor")\n',
        encoding="utf-8",
    )

    payload = import_project(world=world, controller=controller, project_root=tmp_path / "imported-project")
    metadata_path = Path(payload["scenario_metadata_path"])
    assert metadata_path.exists()
    imported = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert imported["import_source"]["world_path"] == str(world)
    assert imported["import_source"]["discovered_robot_name"] == "imported-bot"
    assert imported["import_source"]["discovered_robot_def"] == "IMPORTED_BOT"
    assert imported["import_source"]["discovered_devices"] == ["camera", "left wheel motor"]
    assert imported["robot"]["name"] == "imported-bot"
    assert payload["inferred_scenario_kind"] == "waypoint-nav"
    assert payload["suggested_benchmark_name"] == "waypoint-nav"
    assert payload["discovered_robot_name"] == "imported-bot"
    assert payload["discovered_robot_def"] == "IMPORTED_BOT"
    assert payload["discovered_devices"] == ["camera", "left wheel motor"]
    assert payload["minimal_scenario_metadata"]["benchmark_name"] == "waypoint-nav"
    assert payload["support_tier"] == "experimental-foundation"


def test_replay_session_reads_canonical_export_manifest(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = export_dir / "logs"
    logs_dir.mkdir()
    artifacts_dir = export_dir / "artifacts"
    artifacts_dir.mkdir()
    session_dir = tmp_path / "session123"
    session_dir.mkdir()
    (session_dir / "artifacts").mkdir()
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
        runtime_summary={
            "agent": {"connected": True, "device_count": 3, "state_keys": ["robot_time"], "sensor_keys": ["camera_left_band"], "metric_keys": ["center_error"], "actuator_keys": ["left_velocity"]},
            "supervisor": {"connected": True, "device_count": 0, "state_keys": ["robot_position"], "sensor_keys": [], "metric_keys": [], "actuator_keys": []},
        },
    )
    standard_artifacts = {name: str(export_dir / filename) for name, filename in SESSION_EXPORT_STANDARD_ARTIFACTS}
    (export_dir / "doctor.json").write_text(json.dumps({"status": "ready"}), encoding="utf-8")
    (export_dir / "summary.json").write_text(
        json.dumps({"session_id": "session123", "runtime_environment": {"python_executable": "python.exe"}}, indent=2),
        encoding="utf-8",
    )
    (export_dir / "session.json").write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    (export_dir / "inspect.json").write_text(
        json.dumps({"session_state": {"status": manifest.status, "last_error_code": manifest.last_error_code, "last_error": manifest.last_error}}, indent=2),
        encoding="utf-8",
    )
    (export_dir / "log_inventory.json").write_text("[]", encoding="utf-8")
    (export_dir / "log_summary.json").write_text(json.dumps({"daemon.stdout.log": ["daemon"]}, indent=2), encoding="utf-8")
    (export_dir / "runtime_environment.json").write_text(json.dumps({"python_executable": "python.exe"}, indent=2), encoding="utf-8")
    copied_log = logs_dir / "daemon.stdout.log"
    copied_log.write_text("daemon\n", encoding="utf-8")
    copied_artifact = artifacts_dir / "daemon.stdout.log"
    copied_artifact.write_text("daemon\n", encoding="utf-8")
    exported = SessionExport(
        export_dir=str(export_dir),
        session_id="session123",
        manifest_path=standard_artifacts["session"],
        inspect_path=standard_artifacts["inspect"],
        log_inventory_path=standard_artifacts["log_inventory"],
        log_summary_path=standard_artifacts["log_summary"],
        runtime_environment_path=standard_artifacts["runtime_environment"],
        doctor_path=standard_artifacts["doctor"],
        summary_path=standard_artifacts["summary"],
        export_manifest_path=standard_artifacts["export_manifest"],
        artifact_standard_version=SESSION_EXPORT_ARTIFACT_STANDARD_VERSION,
        replay_mode="observability",
        standard_artifacts=standard_artifacts,
        copied_logs=[str(copied_log)],
        copied_artifacts=[str(copied_artifact)],
        scenario="waypoint-nav",
        status="failed",
        last_error_code="render-init-failed",
        result_reason="render-init-failed",
    )
    (export_dir / "export.json").write_text(json.dumps(exported.to_dict(), indent=2), encoding="utf-8")

    replay = replay_session(export_dir / "export.json")
    replay_from_dir = replay_session(export_dir)

    assert replay["session_id"] == "session123"
    assert replay["artifact_standard_version"] == 1
    assert replay["replay_mode"] == "observability"
    assert replay["standard_artifacts"]["doctor"] == str(export_dir / "doctor.json")
    assert replay["last_error_code"] == "render-init-failed"
    assert replay["session_state"]["status"] == "failed"
    assert replay["support_tier"] == "experimental-foundation"
    assert replay["benchmark_summary"]["benchmark_name"] == "waypoint-nav"
    assert replay["telemetry_summary"]["connected_roles"] == ["agent", "supervisor"]
    assert replay["runtime_failure_class"] == "rendering"
    assert replay["triage_recipe"]["focus"] == "rendering"
    assert "session_state_status: failed" in format_session_replay(replay)
    assert "replay_mode: observability" in format_session_replay(replay)
    assert "runtime_failure_class: rendering" in format_session_replay(replay)
    assert "triage_focus: rendering" in format_session_replay(replay)
    assert "summary:" in format_session_replay(replay)
    assert replay_from_dir["session_id"] == "session123"
