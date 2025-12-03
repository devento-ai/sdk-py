"""Devento SDK - Python client for Devento cloud sandboxes.

Devento provides secure, isolated execution environments for running code.

Basic usage:
    from devento import Devento

    devento = Devento(api_key="sk-devento-...")

    with devento.box() as box:
        result = box.run("echo 'Hello, World!'")
        print(result.stdout)
"""

__version__ = "0.1.6"

from .client import Devento, BoxHandle
from .models import (
    Box,
    BoxConfig,
    BoxStatus,
    CommandResult,
    CommandStatus,
    CommandOptions,
    Domain,
    DomainKind,
    DomainStatus,
    DomainResponse,
    DomainsResponse,
    DomainMeta,
    ExposedPort,
    Snapshot,
    SnapshotStatus,
)
from .exceptions import (
    DeventoError,
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
    from .async_client import AsyncDevento, AsyncBoxHandle  # noqa: F401

    _async_available = True
except ImportError:
    _async_available = False

__all__ = [
    # Main client
    "Devento",
    "BoxHandle",
    # Models
    "Box",
    "BoxConfig",
    "BoxStatus",
    "CommandResult",
    "CommandStatus",
    "CommandOptions",
    "Domain",
    "DomainKind",
    "DomainStatus",
    "DomainResponse",
    "DomainsResponse",
    "DomainMeta",
    "ExposedPort",
    "Snapshot",
    "SnapshotStatus",
    # Exceptions
    "DeventoError",
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
    __all__.extend(["AsyncDevento", "AsyncBoxHandle"])
