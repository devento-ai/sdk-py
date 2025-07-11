"""Tavor SDK client implementation."""

import os
import time
import json
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
    ExposedPort,
)
from .sse_utils import parse_sse_stream


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

        use_streaming = bool(options.on_stdout or options.on_stderr)

        if use_streaming:
            return self._run_with_streaming(command, options)
        else:
            cmd_response = self._client._queue_command(self.id, command, stream=False)
            command_id = cmd_response["id"]

            start_time = time.time()

            while True:
                cmd_data = self._client._get_command(self.id, command_id)

                status = CommandStatus(cmd_data["status"])
                if status in [
                    CommandStatus.DONE,
                    CommandStatus.FAILED,
                    CommandStatus.ERROR,
                ]:
                    exit_code = 0 if status == CommandStatus.DONE else 1
                    if status == CommandStatus.FAILED and cmd_data.get("stderr"):
                        exit_code = 1

                    return CommandResult(
                        id=cmd_data["id"],
                        command=cmd_data.get("command", ""),
                        status=status,
                        stdout=cmd_data.get("stdout") or "",
                        stderr=cmd_data.get("stderr") or "",
                        exit_code=exit_code,
                        created_at=cmd_data.get("created_at"),
                    )

                if options.timeout and (time.time() - start_time) > options.timeout:
                    raise CommandTimeoutError(
                        f"Command timed out after {options.timeout} seconds"
                    )

                time.sleep(1.0)

    def _run_with_streaming(
        self, command: str, options: CommandOptions
    ) -> CommandResult:
        """Run a command with SSE streaming."""
        url = urljoin(self._client.base_url, f"/api/v2/boxes/{self.id}")
        headers = {
            "X-API-Key": self._client.api_key,
            "Content-Type": "application/json",
        }

        start_time = time.time()
        stdout = ""
        stderr = ""
        exit_code = 0
        status = CommandStatus.QUEUED
        command_id = None

        response = self._client.session.post(
            url,
            headers=headers,
            json={"command": command, "stream": True},
            stream=True,
            timeout=None,  # Disable timeout for streaming
        )

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

        buffer = ""
        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            if chunk:
                buffer += chunk
                messages = buffer.split("\n\n")
                buffer = messages.pop() if messages else ""

                for message in messages:
                    if not message.strip():
                        continue

                    for sse_event in parse_sse_stream(message + "\n\n"):
                        try:
                            data = json.loads(sse_event.data)

                            if sse_event.event == "start":
                                command_id = data.get("command_id")

                            elif sse_event.event == "output":
                                if data.get("stdout"):
                                    stdout += data["stdout"]
                                    if options.on_stdout:
                                        for line in data["stdout"].splitlines(
                                            keepends=True
                                        ):
                                            if line:
                                                options.on_stdout(line.rstrip("\n"))

                                if data.get("stderr"):
                                    stderr += data["stderr"]
                                    if options.on_stderr:
                                        for line in data["stderr"].splitlines(
                                            keepends=True
                                        ):
                                            if line:
                                                options.on_stderr(line.rstrip("\n"))

                            elif sse_event.event == "status":
                                status = CommandStatus(data.get("status"))
                                if data.get("exit_code") is not None:
                                    exit_code = data.get("exit_code")

                            elif sse_event.event == "end":
                                if data.get("status") == "error":
                                    status = CommandStatus.ERROR
                                elif data.get("status") == "timeout":
                                    raise CommandTimeoutError("Command timed out")

                                return CommandResult(
                                    id=command_id or "",
                                    command=command,
                                    status=status,
                                    stdout=stdout,
                                    stderr=stderr,
                                    exit_code=exit_code,
                                    created_at=None,
                                )

                            elif sse_event.event == "error":
                                raise TavorError(
                                    f"Command error: {data.get('error', 'Unknown error')}"
                                )

                            elif sse_event.event == "timeout":
                                raise CommandTimeoutError("Command timed out")

                        except json.JSONDecodeError:
                            # Ignore JSON parse errors
                            pass

                    if options.timeout and (time.time() - start_time) > options.timeout:
                        raise CommandTimeoutError(
                            f"Command timed out after {options.timeout} seconds"
                        )

        # If we get here, the stream ended without a proper completion
        return CommandResult(
            id=command_id or "",
            command=command,
            status=status,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            created_at=None,
        )

    def stop(self) -> None:
        """Stop the box."""
        if not self._closed:
            self._client._delete_box(self.id)
            self._closed = True

    def close(self) -> None:
        """Alias for stop()."""
        self.stop()

    def get_public_url(self, port: int) -> str:
        """Get the public web URL for accessing a specific port on the box.

        Args:
            port: The port number inside the VM to expose

        Returns:
            The public URL for accessing the port

        Raises:
            ValueError: If hostname is not available
        """
        self.refresh()
        if not self._box:
            raise TavorError("Box information not available")
        return self._box.get_public_url(port)

    def expose_port(self, target_port: int) -> ExposedPort:
        """Expose a port from inside the sandbox to a random external port.

        This allows external access to services running inside the sandbox.

        Args:
            target_port: The port number inside the sandbox to expose

        Returns:
            ExposedPort: Contains the proxy_port (external), target_port, and expires_at

        Raises:
            TavorError: If the box is not in a running state or if no ports are available
        """
        response = self._client._request(
            "POST", f"/api/v2/boxes/{self.id}/expose_port", json={"port": target_port}
        )
        data = response.json()["data"]

        # Parse the expires_at timestamp
        from datetime import datetime

        expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))

        return ExposedPort(
            proxy_port=data["proxy_port"],
            target_port=data["target_port"],
            expires_at=expires_at,
        )

    def pause(self) -> None:
        """Pause the execution of the sandbox.

        This temporarily stops the sandbox from running while preserving its state.

        Raises:
            TavorError: If the box cannot be paused
        """
        self._client._request("POST", f"/api/v2/boxes/{self.id}/pause")
        self.refresh()

    def resume(self) -> None:
        """Resume the execution of a paused sandbox.

        This continues the sandbox execution from where it was paused.

        Raises:
            TavorError: If the box cannot be resumed
        """
        self._client._request("POST", f"/api/v2/boxes/{self.id}/resume")
        self.refresh()

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

    def _queue_command(
        self, box_id: str, command: str, stream: bool = False
    ) -> Dict[str, Any]:
        """Queue a command on a box."""
        payload = {"command": command, "stream": False}
        if stream:
            payload["stream"] = True
        response = self._request("POST", f"/api/v2/boxes/{box_id}", json=payload)
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
                    hostname=box_data.get("hostname"),
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
