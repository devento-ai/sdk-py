"""Data models for Tavor SDK."""

import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, Callable


class BoxStatus(str, Enum):
    """Box status enum."""

    CREATING = "creating"
    QUEUED = "queued"
    PROVISIONING = "provisioning"
    BOOTING = "booting"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    FINISHED = "finished"
    ERROR = "error"


class CommandStatus(str, Enum):
    """Command status enum."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class BoxConfig:
    """Configuration for creating a box."""

    cpu: Optional[int] = None
    mib_ram: Optional[int] = None
    timeout: Optional[int] = 600
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        # Check environment variables for defaults
        if self.cpu is None:
            env_cpu = os.environ.get("TAVOR_BOX_CPU")
            if env_cpu:
                try:
                    self.cpu = int(env_cpu)
                except ValueError:
                    pass

        if self.mib_ram is None:
            env_ram = os.environ.get("TAVOR_BOX_MIB_RAM")
            if env_ram:
                try:
                    self.mib_ram = int(env_ram)
                except ValueError:
                    pass

        if self.timeout == 600:
            env_timeout = os.environ.get("TAVOR_BOX_TIMEOUT")
            if env_timeout:
                try:
                    self.timeout = int(env_timeout)
                except ValueError:
                    pass


@dataclass
class CommandResult:
    """Result of a command execution."""

    id: str
    command: str
    status: CommandStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


@dataclass
class Box:
    """Represents a box."""

    id: str
    status: BoxStatus
    timeout: Optional[int] = None
    created_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    details: Optional[str] = None


@dataclass
class CommandOptions:
    """Options for command execution."""

    timeout: Optional[float] = None
    on_stdout: Optional[Callable[[str], None]] = None
    on_stderr: Optional[Callable[[str], None]] = None
    poll_interval: float = 1.0
