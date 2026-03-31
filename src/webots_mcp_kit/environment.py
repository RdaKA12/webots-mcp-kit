from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


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


def build_process_env(*, include_src: bool = True) -> dict[str, str]:
    env = os.environ.copy()
    webots = get_webots_environment()
    env["WEBOTS_HOME"] = str(webots.webots_home)
    env["PATH"] = os.pathsep.join([str(webots.controller_library_path), env.get("PATH", "")])
    if include_src:
        env["PYTHONPATH"] = python_path_entries(webots.controller_python_path)
    else:
        env["PYTHONPATH"] = python_path_entries()
    return env


def current_python() -> str:
    return sys.executable
