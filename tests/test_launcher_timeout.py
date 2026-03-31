from __future__ import annotations

from webots_mcp_kit.launcher import session_start_timeout


def test_session_start_timeout_uses_default_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("WEBOTS_KIT_SESSION_START_TIMEOUT", raising=False)
    assert session_start_timeout(30.0) == 30.0


def test_session_start_timeout_uses_env_override(monkeypatch) -> None:
    monkeypatch.setenv("WEBOTS_KIT_SESSION_START_TIMEOUT", "90")
    assert session_start_timeout(30.0) == 90.0


def test_session_start_timeout_ignores_invalid_env(monkeypatch) -> None:
    monkeypatch.setenv("WEBOTS_KIT_SESSION_START_TIMEOUT", "not-a-number")
    assert session_start_timeout(30.0) == 30.0
