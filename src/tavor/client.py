"""Tavor SDK client implementation."""

import os
import time
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Generator
import requests
from urllib.parse import urljoin

from .exceptions import (
    TavorError,
    BoxNotFoundError,
    CommandTimeoutError,
    map_status_to_exception,
)
from .models import (
    Box,
    BoxStatus,
    BoxConfig,
    CommandResult,
    CommandStatus,
    CommandOptions,
)


class BoxHandle:
    """Handle for interacting with a box."""

    def __init__(self, client: "Tavor", box_id: str, box: Optional[Box] = None):
        self._client = client
        self.id = box_id
        self._box = box
        self._closed = False

    @property
    def status(self) -> BoxStatus:
        """Get current box status."""
        self.refresh()
        return self._box.status if self._box else BoxStatus.QUEUED

    def refresh(self) -> "BoxHandle":
        """Refresh box status from the API."""
        if self._closed:
            raise TavorError("Box handle is closed")

        # TODO: GET /api/v2/boxes/{box_id} instead of list_boxes here
        boxes = self._client.list_boxes()
        for box in boxes:
            if box.id == self.id:
                self._box = box
                return self

        raise BoxNotFoundError(404, f"Box {self.id} not found")

    def wait_until_ready(
        self, timeout: Optional[float] = 300, poll_interval: float = 1.0
    ) -> "BoxHandle":
        """Wait until the box is in running state."""
        start_time = time.time()

        while True:
            self.refresh()

            if self.status == BoxStatus.RUNNING:
                return self

            if self.status in [
                BoxStatus.FAILED,
                BoxStatus.STOPPED,
                BoxStatus.FINISHED,
                BoxStatus.ERROR,
            ]:
                error_msg = f"Box failed to start: {self.status}"
                if self._box and self._box.details:
                    error_msg += f" - {self._box.details}"
                raise TavorError(error_msg)

            if timeout and (time.time() - start_time) > timeout:
                raise CommandTimeoutError(
                    f"Box did not become ready within {timeout} seconds"
                )

            time.sleep(poll_interval)

    def run(self, command: str, **kwargs) -> CommandResult:
        """Run a command in the box and wait for completion."""
        options = CommandOptions(**kwargs)

        # Wait for box to be ready
        self.wait_until_ready()

        # Queue the command
        cmd_response = self._client._queue_command(self.id, command)
        command_id = cmd_response["id"]

        # Poll for completion
        start_time = time.time()
        last_stdout_len = 0
        last_stderr_len = 0

        while True:
            cmd_data = self._client._get_command(self.id, command_id)

            # Stream output if callbacks provided
            if options.on_stdout and cmd_data.get("stdout"):
                new_output = cmd_data["stdout"][last_stdout_len:]
                if new_output:
                    for line in new_output.splitlines(keepends=True):
                        options.on_stdout(line)
                    last_stdout_len = len(cmd_data["stdout"])

            if options.on_stderr and cmd_data.get("stderr"):
                new_output = cmd_data["stderr"][last_stderr_len:]
                if new_output:
                    for line in new_output.splitlines(keepends=True):
                        options.on_stderr(line)
                    last_stderr_len = len(cmd_data["stderr"])

            # Check if command is complete
            status = CommandStatus(cmd_data["status"])
            if status in [
                CommandStatus.DONE,
                CommandStatus.FAILED,
                CommandStatus.ERROR,
            ]:
                # Determine exit code
                exit_code = 0 if status == CommandStatus.DONE else 1
                if status == CommandStatus.FAILED and cmd_data.get("stderr"):
                    # Try to extract exit code from stderr if available
                    # This is a simplified approach, actual implementation might need enhancement
                    exit_code = 1

                return CommandResult(
                    id=cmd_data["id"],
                    command=cmd_data.get("command", ""),
                    status=status,
                    stdout=cmd_data.get("stdout", ""),
                    stderr=cmd_data.get("stderr", ""),
                    exit_code=exit_code,
                    created_at=cmd_data.get("created_at"),
                )

            # Check timeout
            if options.timeout and (time.time() - start_time) > options.timeout:
                raise CommandTimeoutError(
                    f"Command timed out after {options.timeout} seconds"
                )

            time.sleep(options.poll_interval)

    def stop(self) -> None:
        """Stop the box."""
        if not self._closed:
            self._client._delete_box(self.id)
            self._closed = True

    def close(self) -> None:
        """Alias for stop()."""
        self.stop()

    def __enter__(self) -> "BoxHandle":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and clean up."""
        self.stop()


class Tavor:
    """Main Tavor client for interacting with boxes."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        session: Optional[requests.Session] = None,
    ):
        """Initialize Tavor client.

        Args:
            api_key: Your Tavor API key (sk-tavor-...). Defaults to TAVOR_API_KEY env var.
            base_url: Base URL for Tavor API. Defaults to TAVOR_BASE_URL env var or https://api.tavor.dev.
            timeout: Default timeout for HTTP requests
            session: Optional requests session to use
        """
        if api_key is None:
            api_key = os.environ.get("TAVOR_API_KEY")

        if not api_key:
            raise ValueError(
                "API key is required. Set TAVOR_API_KEY environment variable or pass api_key parameter."
            )

        if base_url is None:
            base_url = os.environ.get("TAVOR_BASE_URL", "https://api.tavor.dev")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {"X-API-Key": api_key, "Content-Type": "application/json"}
        )

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make an HTTP request to the API."""
        url = urljoin(self.base_url, path)
        kwargs.setdefault("timeout", self.timeout)

        response = self.session.request(method, url, **kwargs)

        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("error") or error_data.get("message")
            except Exception:
                message = response.text

            raise map_status_to_exception(
                response.status_code,
                message,
                response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else {},
            )

        return response

    def _create_box(self, config: BoxConfig) -> Dict[str, Any]:
        """Create a new box via API."""
        payload: Dict[str, Any] = {}

        if config.cpu is not None:
            payload["cpu"] = config.cpu

        if config.mib_ram is not None:
            payload["mib_ram"] = config.mib_ram

        if config.timeout is not None:
            payload["timeout"] = config.timeout

        if config.metadata:
            payload["metadata"] = config.metadata

        response = self._request("POST", "/api/v2/boxes", json=payload)
        return response.json()

    def _delete_box(self, box_id: str) -> None:
        """Delete a box via API."""
        self._request("DELETE", f"/api/v2/boxes/{box_id}")

    def _queue_command(self, box_id: str, command: str) -> Dict[str, Any]:
        """Queue a command on a box."""
        response = self._request(
            "POST", f"/api/v2/boxes/{box_id}", json={"command": command}
        )
        return response.json()

    def _get_command(self, box_id: str, command_id: str) -> Dict[str, Any]:
        """Get command status and output."""
        response = self._request("GET", f"/api/v2/boxes/{box_id}/commands/{command_id}")
        return response.json()

    def list_boxes(self) -> List[Box]:
        """List all boxes for the current organization."""
        response = self._request("GET", "/api/v2/boxes")
        data = response.json()

        boxes = []
        for box_data in data.get("data", []):
            boxes.append(
                Box(
                    id=box_data["id"],
                    status=BoxStatus(box_data["status"]),
                    timeout=box_data.get("timeout"),
                    created_at=box_data.get("created_at"),
                    details=box_data.get("details"),
                )
            )

        return boxes

    @contextmanager
    def box(
        self, config: Optional[BoxConfig] = None
    ) -> Generator[BoxHandle, None, None]:
        """Create a box with automatic cleanup.

        Args:
            config: Optional box configuration

        Yields:
            BoxHandle: Handle for interacting with the box

        Example:
            with tavor.box() as box:
                result = box.run("echo 'Hello, World!'")
                print(result.stdout)
        """
        if config is None:
            config = BoxConfig()

        box_data = self._create_box(config)
        box_handle = BoxHandle(self, box_data["id"])

        try:
            yield box_handle
        finally:
            box_handle.stop()

    def create_box(self, config: Optional[BoxConfig] = None) -> BoxHandle:
        """Create a box without automatic cleanup.

        Args:
            config: Optional box configuration

        Returns:
            BoxHandle: Handle for interacting with the box

        Note:
            You must manually call box.stop() when done.
        """
        if config is None:
            config = BoxConfig()

        box_data = self._create_box(config)
        return BoxHandle(self, box_data["id"])
