from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SOFTWARE_OPENGL_ENV = "WEBOTS_KIT_OPENGL32SW_DIR"
FORCE_SOFTWARE_OPENGL_ENV = "WEBOTS_KIT_FORCE_SOFTWARE_OPENGL"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def app_state_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "webots-mcp-kit"
    return Path.home() / ".webots-mcp-kit"


@dataclass(slots=True)
class WebotsEnvironment:
    webots_home: Path
    webots_executable: Path
    controller_python_path: Path
    controller_library_path: Path
    version: str | None


def detect_webots_home() -> Path:
    candidates = []
    env_home = os.environ.get("WEBOTS_HOME")
    if env_home:
        candidates.append(Path(env_home))
    candidates.append(Path("C:/Program Files/Webots"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Unable to locate Webots installation. Set WEBOTS_HOME.")


def get_webots_environment() -> WebotsEnvironment:
    home = detect_webots_home()
    executable = home / "msys64" / "mingw64" / "bin" / "webots.exe"
    controller_python_path = home / "lib" / "controller" / "python"
    controller_library_path = home / "lib" / "controller"
    version_file = home / "resources" / "version.txt"
    version = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else None
    return WebotsEnvironment(
        webots_home=home,
        webots_executable=executable,
        controller_python_path=controller_python_path,
        controller_library_path=controller_library_path,
        version=version,
    )


def python_path_entries(*extra: Path | str) -> str:
    entries = [str(repo_root() / "src")]
    entries.extend(str(Path(item)) for item in extra if item)
    existing = os.environ.get("PYTHONPATH")
    if existing:
        entries.append(existing)
    return os.pathsep.join(entries)


def detect_software_opengl_dir() -> Path | None:
    configured = os.environ.get(SOFTWARE_OPENGL_ENV)
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        candidates.append(Path(conda_prefix) / "Library" / "bin")
    candidates.extend(
        [
            Path("C:/Program Files/anaconda3/Library/bin"),
            Path("C:/Program Files/Orange/Library/bin"),
            Path("C:/Program Files (x86)/AMD/Chipset_Software/Qt_Dependencies"),
        ]
    )
    for candidate in candidates:
        candidate = candidate.expanduser()
        dll = candidate if candidate.name.lower() == "opengl32sw.dll" else candidate / "opengl32sw.dll"
        if dll.exists():
            return dll.parent
    return None


def software_opengl_requested() -> bool:
    return os.environ.get(FORCE_SOFTWARE_OPENGL_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def detect_runner_mode() -> dict[str, Any]:
    session_name = (os.environ.get("SESSIONNAME") or "").strip()
    if session_name.lower() == "services":
        mode = "windows-service"
    elif session_name:
        mode = "interactive-session"
    else:
        mode = "unknown"
    return {
        "mode": mode,
        "session_name": session_name or None,
        "user": os.environ.get("USERNAME"),
        "computer": os.environ.get("COMPUTERNAME"),
    }


def build_process_env(*, include_src: bool = True, prefer_software_opengl: bool = False) -> dict[str, str]:
    env = os.environ.copy()
    webots = get_webots_environment()
    path_entries = [str(webots.controller_library_path)]
    if prefer_software_opengl:
        software_gl_dir = detect_software_opengl_dir()
        if software_gl_dir is not None:
            env["QT_OPENGL"] = "software"
            env["WEBOTS_KIT_SOFTWARE_OPENGL_DIR"] = str(software_gl_dir)
            path_entries.insert(0, str(software_gl_dir))
    env["WEBOTS_HOME"] = str(webots.webots_home)
    path_entries.append(env.get("PATH", ""))
    env["PATH"] = os.pathsep.join(path_entries)
    if include_src:
        env["PYTHONPATH"] = python_path_entries(webots.controller_python_path)
    else:
        env["PYTHONPATH"] = python_path_entries()
    return env


def describe_launch_environment(*, prefer_software_opengl: bool = False) -> dict[str, Any]:
    software_gl_dir = detect_software_opengl_dir() if prefer_software_opengl else None
    return {
        "runner": detect_runner_mode(),
        "python_executable": current_python(),
        "software_opengl_requested": prefer_software_opengl,
        "software_opengl_dir": str(software_gl_dir) if software_gl_dir is not None else None,
        "qt_opengl": "software" if software_gl_dir is not None and prefer_software_opengl else None,
    }


def current_python() -> str:
    return sys.executable
