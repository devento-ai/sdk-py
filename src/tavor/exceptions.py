"""Tavor SDK exceptions."""

from typing import Optional, Dict, Any


class TavorError(Exception):
    """Base exception for all Tavor SDK errors."""

    pass


class APIError(TavorError):
    """Base exception for API-related errors."""

    def __init__(
        self,
        status_code: int,
        message: Optional[str] = None,
        response_data: Optional[Dict[str, Any]] = None,
    ):
        self.status_code = status_code
        self.message = message or f"API request failed with status {status_code}"
        self.response_data = response_data or {}
        super().__init__(self.message)


class AuthenticationError(APIError):
    """Raised when authentication fails (401)."""

    pass


class ForbiddenError(APIError):
    """Raised when access is forbidden (403)."""

    pass


class NotFoundError(APIError):
    """Raised when a resource is not found (404)."""

    pass


class BoxNotFoundError(NotFoundError):
    """Raised when a box is not found."""

    pass


class ConflictError(APIError):
    """Raised when there's a conflict (409)."""

    pass


class ValidationError(APIError):
    """Raised when validation fails (422)."""

    pass


class ServerError(APIError):
    """Raised when server encounters an error (5xx)."""

    pass


class CommandTimeoutError(TavorError):
    """Raised when a command execution times out."""

    def __init__(self, message: str = "Command execution timed out"):
        super().__init__(message)


class BoxTimeoutError(TavorError):
    """Raised when a box times out."""

    def __init__(self, message: str = "Box timed out"):
        super().__init__(message)


def map_status_to_exception(
    status_code: int,
    message: Optional[str] = None,
    response_data: Optional[Dict[str, Any]] = None,
) -> APIError:
    """Map HTTP status code to appropriate exception."""
    exception_map = {
        401: AuthenticationError,
        403: ForbiddenError,
        404: NotFoundError,
        409: ConflictError,
        422: ValidationError,
    }

    if status_code >= 500:
        return ServerError(status_code, message, response_data)

    exception_class = exception_map.get(status_code, APIError)
    return exception_class(status_code, message, response_data)
