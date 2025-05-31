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


class BoxTemplate(str, Enum):
    """Predefined box templates."""

    BASIC = "Basic"
    PRO = "Pro"


@dataclass
class BoxConfig:
    """Configuration for creating a box."""

    template: Optional[str] = None
    template_id: Optional[str] = None
    timeout: Optional[int] = 600
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.template and self.template_id:
            raise ValueError("Cannot specify both template and template_id")
        if not self.template and not self.template_id:
            # Check environment variable for default template
            env_template = os.environ.get("TAVOR_BOX_TEMPLATE")
            if env_template:
                # Try to match against BoxTemplate enum values
                try:
                    self.template = BoxTemplate(env_template)
                except ValueError:
                    self.template_id = env_template
            else:
                self.template = BoxTemplate.BASIC

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
