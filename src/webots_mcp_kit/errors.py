from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

STABLE_RUNTIME_ERROR_CODES: tuple[str, ...] = (
    "render-init-failed",
    "controller-launch-failed",
    "supervisor-connect-timeout",
    "agent-connect-timeout",
    "session-start-timeout",
    "webots-unexpected-exit",
    "admin-request-failed",
    "mcp-tool-failed",
)


@dataclass(slots=True)
class StructuredError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    retriable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class KitError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        retriable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.retriable = retriable

    def to_dict(self) -> dict[str, Any]:
        return StructuredError(
            code=self.code,
            message=self.message,
            details=self.details,
            retriable=self.retriable,
        ).to_dict()


def error_dict(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    retriable: bool = False,
) -> dict[str, Any]:
    return StructuredError(code=code, message=message, details=details or {}, retriable=retriable).to_dict()


def coerce_error_payload(
    error: str | dict[str, Any] | None,
    *,
    fallback_code: str = "runtime-request-failed",
    fallback_message: str = "Runtime request failed.",
) -> dict[str, Any]:
    if isinstance(error, dict):
        return {
            "code": str(error.get("code") or fallback_code),
            "message": str(error.get("message") or fallback_message),
            "details": error.get("details") if isinstance(error.get("details"), dict) else {},
            "retriable": bool(error.get("retriable", False)),
        }
    if isinstance(error, str) and error.strip():
        return error_dict(fallback_code, error.strip())
    return error_dict(fallback_code, fallback_message)


def error_from_exception(
    exc: Exception,
    *,
    fallback_code: str,
    fallback_message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(exc, KitError):
        payload = exc.to_dict()
    else:
        raw_error = exc.args[0] if getattr(exc, "args", ()) else None
        payload = coerce_error_payload(
            raw_error,
            fallback_code=fallback_code,
            fallback_message=fallback_message,
        )
    merged_details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    if details:
        merged_details = {**merged_details, **details}
    payload["details"] = merged_details
    return payload
