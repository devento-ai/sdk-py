"""Tavor SDK - Python client for Tavor cloud sandboxes.

Tavor provides secure, isolated execution environments for running code.

Basic usage:
    from tavor import Tavor

    tavor = Tavor(api_key="sk-tavor-...")

    with tavor.box() as box:
        result = box.run("echo 'Hello, World!'")
        print(result.stdout)
"""

__version__ = "1.0.1"

from .client import Tavor, BoxHandle
from .models import (
    Box,
    BoxConfig,
    BoxStatus,
    CommandResult,
    CommandStatus,
    CommandOptions,
)
from .exceptions import (
    TavorError,
    APIError,
    AuthenticationError,
    ForbiddenError,
    NotFoundError,
    BoxNotFoundError,
    ConflictError,
    ValidationError,
    ServerError,
    CommandTimeoutError,
    BoxTimeoutError,
)

# Optional async client - only import if aiohttp is available
try:
    from .async_client import AsyncTavor, AsyncBoxHandle  # noqa: F401

    _async_available = True
except ImportError:
    _async_available = False

__all__ = [
    # Main client
    "Tavor",
    "BoxHandle",
    # Models
    "Box",
    "BoxConfig",
    "BoxStatus",
    "CommandResult",
    "CommandStatus",
    "CommandOptions",
    # Exceptions
    "TavorError",
    "APIError",
    "AuthenticationError",
    "ForbiddenError",
    "NotFoundError",
    "BoxNotFoundError",
    "ConflictError",
    "ValidationError",
    "ServerError",
    "CommandTimeoutError",
    "BoxTimeoutError",
]

if _async_available:
    __all__.extend(["AsyncTavor", "AsyncBoxHandle"])
