from __future__ import annotations

from webots_mcp_kit.environment import FORCE_SOFTWARE_OPENGL_ENV, SOFTWARE_OPENGL_ENV, detect_software_opengl_dir, software_opengl_requested


def test_detect_software_opengl_dir_prefers_configured_directory(tmp_path, monkeypatch) -> None:
    dll = tmp_path / "opengl32sw.dll"
    dll.write_text("stub", encoding="utf-8")
    monkeypatch.setenv(SOFTWARE_OPENGL_ENV, str(tmp_path))
    assert detect_software_opengl_dir() == tmp_path


def test_detect_software_opengl_dir_accepts_configured_file_path(tmp_path, monkeypatch) -> None:
    dll = tmp_path / "opengl32sw.dll"
    dll.write_text("stub", encoding="utf-8")
    monkeypatch.setenv(SOFTWARE_OPENGL_ENV, str(dll))
    assert detect_software_opengl_dir() == tmp_path


def test_software_opengl_requested_defaults_false(monkeypatch) -> None:
    monkeypatch.delenv(FORCE_SOFTWARE_OPENGL_ENV, raising=False)
    assert software_opengl_requested() is False


def test_software_opengl_requested_true_values(monkeypatch) -> None:
    monkeypatch.setenv(FORCE_SOFTWARE_OPENGL_ENV, "1")
    assert software_opengl_requested() is True
