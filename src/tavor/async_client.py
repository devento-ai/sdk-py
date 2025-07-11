"""Async Tavor SDK client implementation."""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, AsyncGenerator

try:
    import aiohttp
except ImportError:
    raise ImportError(
        "aiohttp is required for AsyncTavor. Install it with: pip install tavor[async]"
    )

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


class AsyncBoxHandle:
    """Async handle for interacting with a box."""

    def __init__(self, client: "AsyncTavor", box_id: str, box: Optional[Box] = None):
        self._client = client
        self.id = box_id
        self._box = box
        self._closed = False

    @property
    def status(self) -> BoxStatus:
        """Get current box status."""
        if not self._box:
            return BoxStatus.QUEUED
        return self._box.status

    async def refresh(self) -> "AsyncBoxHandle":
        """Refresh box status from the API."""
        if self._closed:
            raise TavorError("Box handle is closed")

        boxes = await self._client.list_boxes()
        for box in boxes:
            if box.id == self.id:
                self._box = box
                return self

        raise BoxNotFoundError(404, f"Box {self.id} not found")

    async def wait_until_ready(
        self, timeout: Optional[float] = 300, poll_interval: float = 1.0
    ) -> "AsyncBoxHandle":
        """Wait until the box is in running state."""
        start_time = time.time()

        while True:
            await self.refresh()

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

            await asyncio.sleep(poll_interval)

    async def run(self, command: str, **kwargs) -> CommandResult:
        """Run a command in the box and wait for completion."""
        options = CommandOptions(**kwargs)

        await self.wait_until_ready()

        cmd_response = await self._client._queue_command(self.id, command)
        command_id = cmd_response["id"]

        start_time = time.time()
        last_stdout_len = 0
        last_stderr_len = 0

        while True:
            cmd_data = await self._client._get_command(self.id, command_id)

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

            status = CommandStatus(cmd_data["status"])
            if status in [
                CommandStatus.DONE,
                CommandStatus.FAILED,
                CommandStatus.ERROR,
            ]:
                exit_code = 0 if status == CommandStatus.DONE else 1

                return CommandResult(
                    id=cmd_data["id"],
                    command=cmd_data.get("command", ""),
                    status=status,
                    stdout=cmd_data.get("stdout", ""),
                    stderr=cmd_data.get("stderr", ""),
                    exit_code=exit_code,
                    created_at=cmd_data.get("created_at"),
                )

            if options.timeout and (time.time() - start_time) > options.timeout:
                raise CommandTimeoutError(
                    f"Command timed out after {options.timeout} seconds"
                )

            await asyncio.sleep(options.poll_interval)

    async def stop(self) -> None:
        """Stop the box."""
        if not self._closed:
            await self._client._delete_box(self.id)
            self._closed = True

    async def close(self) -> None:
        """Alias for stop()."""
        await self.stop()

    def get_public_url(self, port: int) -> str:
        """Get the public web URL for accessing a specific port on the box.

        Args:
            port: The port number inside the VM to expose

        Returns:
            The public URL for accessing the port

        Raises:
            ValueError: If hostname is not available
        """
        if not self._box:
            raise TavorError("Box information not available")
        return self._box.get_public_url(port)

    async def expose_port(self, target_port: int) -> ExposedPort:
        """Expose a port from inside the sandbox to a random external port.

        This allows external access to services running inside the sandbox.

        Args:
            target_port: The port number inside the sandbox to expose

        Returns:
            ExposedPort: Contains the proxy_port (external), target_port, and expires_at

        Raises:
            TavorError: If the box is not in a running state or if no ports are available
        """
        response = await self._client._request(
            "POST", f"/api/v2/boxes/{self.id}/expose_port", json={"port": target_port}
        )
        data = response["data"]

        # Parse the expires_at timestamp
        from datetime import datetime

        expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))

        return ExposedPort(
            proxy_port=data["proxy_port"],
            target_port=data["target_port"],
            expires_at=expires_at,
        )

    async def pause(self) -> None:
        """Pause the execution of the sandbox.

        This temporarily stops the sandbox from running while preserving its state.

        Raises:
            TavorError: If the box cannot be paused
        """
        await self._client._request("POST", f"/api/v2/boxes/{self.id}/pause")
        await self.refresh()

    async def resume(self) -> None:
        """Resume the execution of a paused sandbox.

        This continues the sandbox execution from where it was paused.

        Raises:
            TavorError: If the box cannot be resumed
        """
        await self._client._request("POST", f"/api/v2/boxes/{self.id}/resume")
        await self.refresh()

    async def __aenter__(self) -> "AsyncBoxHandle":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager and clean up."""
        await self.stop()


class AsyncTavor:
    """Async Tavor client for interacting with boxes."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        """Initialize AsyncTavor client.

        Args:
            api_key: Your Tavor API key (sk-tavor-...). Defaults to TAVOR_API_KEY env var.
            base_url: Base URL for Tavor API. Defaults to TAVOR_BASE_URL env var or https://api.tavor.dev.
            timeout: Default timeout for HTTP requests
            session: Optional aiohttp session to use
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
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = session
        self._owns_session = session is None
        self._headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    async def __aenter__(self) -> "AsyncTavor":
        """Enter async context manager."""
        if self._owns_session:
            self._session = aiohttp.ClientSession(
                headers=self._headers, timeout=self.timeout
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        if self._owns_session and self._session:
            await self._session.close()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an active session."""
        if not self._session:
            self._session = aiohttp.ClientSession(
                headers=self._headers, timeout=self.timeout
            )
        return self._session

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make an async HTTP request to the API."""
        session = await self._ensure_session()
        url = f"{self.base_url}{path}"

        async with session.request(method, url, **kwargs) as response:
            try:
                data = await response.json()
            except Exception:
                data = {}

            if response.status >= 400:
                message = data.get("error") or data.get("message") or response.reason
                raise map_status_to_exception(response.status, message, data)

            return data

    async def _create_box(self, config: BoxConfig) -> Dict[str, Any]:
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

        return await self._request("POST", "/api/v2/boxes", json=payload)

    async def _delete_box(self, box_id: str) -> None:
        """Delete a box via API."""
        await self._request("DELETE", f"/api/v2/boxes/{box_id}")

    async def _queue_command(self, box_id: str, command: str) -> Dict[str, Any]:
        """Queue a command on a box."""
        return await self._request(
            "POST", f"/api/v2/boxes/{box_id}", json={"command": command}
        )

    async def _get_command(self, box_id: str, command_id: str) -> Dict[str, Any]:
        """Get command status and output."""
        return await self._request(
            "GET", f"/api/v2/boxes/{box_id}/commands/{command_id}"
        )

    async def list_boxes(self) -> List[Box]:
        """List all boxes for the current organization."""
        data = await self._request("GET", "/api/v2/boxes")

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

    @asynccontextmanager
    async def box(
        self, config: Optional[BoxConfig] = None
    ) -> AsyncGenerator[AsyncBoxHandle, None]:
        """Create a box with automatic cleanup.

        Args:
            config: Optional box configuration

        Yields:
            AsyncBoxHandle: Handle for interacting with the box

        Example:
            async with tavor.box() as box:
                result = await box.run("echo 'Hello, World!'")
                print(result.stdout)
        """
        if config is None:
            config = BoxConfig()

        box_data = await self._create_box(config)
        box_handle = AsyncBoxHandle(self, box_data["id"])

        try:
            yield box_handle
        finally:
            await box_handle.stop()

    async def create_box(self, config: Optional[BoxConfig] = None) -> AsyncBoxHandle:
        """Create a box without automatic cleanup.

        Args:
            config: Optional box configuration

        Returns:
            AsyncBoxHandle: Handle for interacting with the box

        Note:
            You must manually call await box.stop() when done.
        """
        if config is None:
            config = BoxConfig()

        box_data = await self._create_box(config)
        return AsyncBoxHandle(self, box_data["id"])
