"""Devento SDK client implementation."""

import os
import time
import json
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Generator, Union
import requests
from urllib.parse import urljoin

from .exceptions import (
    DeventoError,
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
from .sse_utils import parse_sse_stream


_UNSET = object()


class BoxHandle:
    """Handle for interacting with a box."""

    def __init__(self, client: "Devento", box_id: str, box: Optional[Box] = None):
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
            raise DeventoError("Box handle is closed")

        try:
            response = self._client._request("GET", f"/api/v2/boxes/{self.id}")
            self._box = Box(**response.json()["data"])
            return self
        except BoxNotFoundError:
            raise
        except Exception as e:
            if hasattr(e, "status_code") and e.status_code == 404:
                raise BoxNotFoundError(404, f"Box {self.id} not found")
            raise

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
                raise DeventoError(error_msg)

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
            timeout_ms = int(options.timeout * 1000) if options.timeout else None
            cmd_response = self._client._queue_command(
                self.id, command, stream=False, timeout_ms=timeout_ms
            )
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
                    try:
                        self._cancel_command(command_id, "timeout")
                    except Exception:
                        # Ignore cancellation errors
                        pass
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

        timeout_ms = int(options.timeout * 1000) if options.timeout else None
        payload = {"command": command, "stream": True}
        if timeout_ms is not None:
            payload["timeout_ms"] = timeout_ms

        response = self._client.session.post(
            url,
            headers=headers,
            json=payload,
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
                                raise DeventoError(
                                    f"Command error: {data.get('error', 'Unknown error')}"
                                )

                            elif sse_event.event == "timeout":
                                raise CommandTimeoutError("Command timed out")

                        except json.JSONDecodeError:
                            # Ignore JSON parse errors
                            pass

                    if options.timeout and (time.time() - start_time) > options.timeout:
                        if command_id:
                            try:
                                self._cancel_command(command_id, "timeout")
                            except Exception:
                                # Ignore cancellation errors
                                pass
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
            raise DeventoError("Box information not available")
        return self._box.get_public_url(port)

    def expose_port(self, target_port: int) -> ExposedPort:
        """Expose a port from inside the sandbox to a random external port.

        This allows external access to services running inside the sandbox.

        Args:
            target_port: The port number inside the sandbox to expose

        Returns:
            ExposedPort: Contains the proxy_port (external), target_port, and expires_at

        Raises:
            DeventoError: If the box is not in a running state or if no ports are available
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
            DeventoError: If the box cannot be paused
        """
        self._client._request("POST", f"/api/v2/boxes/{self.id}/pause")
        self.refresh()

    def resume(self) -> None:
        """Resume the execution of a paused sandbox.

        This continues the sandbox execution from where it was paused.

        Raises:
            DeventoError: If the box cannot be resumed
        """
        self._client._request("POST", f"/api/v2/boxes/{self.id}/resume")
        self.refresh()

    @property
    def watermark_enabled(self) -> Optional[bool]:
        """Get whether the watermark is enabled for this sandbox's web previews."""
        return self._box.watermark_enabled if self._box else None

    def set_watermark(self, enabled: bool) -> None:
        """Set whether the watermark should be displayed for this sandbox's web previews.

        Args:
            enabled: Whether to enable the watermark

        Raises:
            DeventoError: If the watermark setting cannot be updated
        """
        self._client._request(
            "PATCH", f"/api/v2/boxes/{self.id}", json={"watermark_enabled": enabled}
        )
        self.refresh()

    def list_snapshots(self) -> List[Snapshot]:
        """List all snapshots for this box.

        Returns:
            List of snapshots

        Raises:
            DeventoError: If the request fails
        """
        r = self._client._request("GET", f"/api/v2/boxes/{self.id}/snapshots")
        data = r.json()["data"]
        return [Snapshot(**{**s, "status": SnapshotStatus(s["status"])}) for s in data]

    def get_snapshot(self, snapshot_id: str) -> Snapshot:
        """Get a specific snapshot by ID.

        Args:
            snapshot_id: The ID of the snapshot to fetch

        Returns:
            The snapshot details

        Raises:
            DeventoError: If the snapshot is not found
        """
        r = self._client._request(
            "GET", f"/api/v2/boxes/{self.id}/snapshots/{snapshot_id}"
        )
        s = r.json()["data"]
        return Snapshot(**{**s, "status": SnapshotStatus(s["status"])})

    def create_snapshot(
        self, label: Optional[str] = None, description: Optional[str] = None
    ) -> Snapshot:
        """Create a new snapshot of the box.

        The box must be in a running or paused state.

        Args:
            label: Optional label for the snapshot
            description: Optional description for the snapshot

        Returns:
            The created snapshot

        Raises:
            DeventoError: If the box is not in a valid state for snapshotting
        """
        payload = {}
        if label is not None:
            payload["label"] = label
        if description is not None:
            payload["description"] = description
        r = self._client._request(
            "POST", f"/api/v2/boxes/{self.id}/snapshots", json=payload
        )
        s = r.json()["data"]
        return Snapshot(**{**s, "status": SnapshotStatus(s["status"])})

    def restore_snapshot(self, snapshot_id: str) -> Snapshot:
        """Restore the box from a snapshot.

        The restore operation happens asynchronously.

        Args:
            snapshot_id: The ID of the snapshot to restore

        Returns:
            The snapshot with status "restoring"

        Raises:
            DeventoError: If the snapshot cannot be restored
        """
        r = self._client._request(
            "POST",
            f"/api/v2/boxes/{self.id}/restore",
            json={"snapshot_id": snapshot_id},
        )
        s = r.json()["data"]
        return Snapshot(**{**s, "status": SnapshotStatus(s["status"])})

    def delete_snapshot(self, snapshot_id: str) -> Snapshot:
        """Delete a snapshot.

        Cannot delete snapshots that are currently being created or restored.

        Args:
            snapshot_id: The ID of the snapshot to delete

        Returns:
            The deleted snapshot

        Raises:
            DeventoError: If the snapshot cannot be deleted
        """
        r = self._client._request(
            "DELETE", f"/api/v2/boxes/{self.id}/snapshots/{snapshot_id}"
        )
        s = r.json()["data"]
        return Snapshot(**{**s, "status": SnapshotStatus(s["status"])})

    def wait_snapshot_ready(
        self, snapshot_id: str, timeout: float = 300, poll_interval: float = 1.0
    ) -> None:
        """Wait for a snapshot to become ready.

        Polls the snapshot status until it's ready or fails.

        Args:
            snapshot_id: The ID of the snapshot to wait for
            timeout: Maximum time to wait in seconds (default: 5 minutes)
            poll_interval: Polling interval in seconds (default: 1 second)

        Raises:
            DeventoError: If the snapshot fails
            CommandTimeoutError: If the snapshot doesn't become ready within the timeout
        """
        t0 = time.time()
        while True:
            s = self.get_snapshot(snapshot_id)
            if s.status == SnapshotStatus.READY:
                return
            if s.status in (SnapshotStatus.ERROR, SnapshotStatus.DELETED):
                raise DeventoError(
                    f"Snapshot {snapshot_id} ended with status: {s.status.value}"
                )
            if time.time() - t0 > timeout:
                raise CommandTimeoutError(
                    f"Snapshot {snapshot_id} did not become ready within {timeout}s"
                )
            time.sleep(poll_interval)

    def __enter__(self) -> "BoxHandle":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and clean up."""
        self.stop()

    def _cancel_command(self, command_id: str, reason: Optional[str] = None) -> None:
        """Cancel a running command.

        Args:
            command_id: The ID of the command to cancel
            reason: Optional reason for cancelling
        """
        payload = {}
        if reason:
            payload["reason"] = reason
        self._client._request(
            "POST",
            f"/api/v2/boxes/{self.id}/commands/{command_id}/cancel",
            json=payload,
        )


class Devento:
    """Main Devento client for interacting with boxes."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        session: Optional[requests.Session] = None,
    ):
        """Initialize Devento client.

        Args:
            api_key: Your Devento API key (sk-devento-...). Defaults to DEVENTO_API_KEY env var.
            base_url: Base URL for Devento API. Defaults to DEVENTO_BASE_URL env var or https://api.devento.ai.
            timeout: Default timeout for HTTP requests
            session: Optional requests session to use
        """
        if api_key is None:
            api_key = os.environ.get("DEVENTO_API_KEY")

        if not api_key:
            raise ValueError(
                "API key is required. Set DEVENTO_API_KEY environment variable or pass api_key parameter."
            )

        if base_url is None:
            base_url = os.environ.get("DEVENTO_BASE_URL", "https://api.devento.ai")

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

        if config.watermark_enabled is not None:
            payload["watermark_enabled"] = config.watermark_enabled

        response = self._request("POST", "/api/v2/boxes", json=payload)
        return response.json()

    def _delete_box(self, box_id: str) -> None:
        """Delete a box via API."""
        self._request("DELETE", f"/api/v2/boxes/{box_id}")

    def _queue_command(
        self,
        box_id: str,
        command: str,
        stream: bool = False,
        timeout_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Queue a command on a box."""
        payload = {"command": command, "stream": False}
        if stream:
            payload["stream"] = True
        if timeout_ms is not None:
            payload["timeout_ms"] = timeout_ms
        response = self._request("POST", f"/api/v2/boxes/{box_id}", json=payload)
        return response.json()

    def _get_command(self, box_id: str, command_id: str) -> Dict[str, Any]:
        """Get command status and output."""
        response = self._request("GET", f"/api/v2/boxes/{box_id}/commands/{command_id}")
        return response.json()

    def list_domains(self) -> DomainsResponse:
        """List managed and custom domains."""
        response = self._request("GET", "/api/v2/domains")
        return self._build_domains_response(response.json())

    def get_domain(self, domain_id: str) -> DomainResponse:
        """Retrieve a single domain by its identifier."""
        response = self._request("GET", f"/api/v2/domains/{domain_id}")
        return self._build_domain_response(response.json())

    def create_domain(
        self,
        *,
        kind: Union[DomainKind, str],
        slug: Optional[str] = None,
        hostname: Optional[str] = None,
        status: Optional[Union[DomainStatus, str]] = None,
        target_port: Optional[int] = None,
        box_id: Optional[str] = None,
    ) -> DomainResponse:
        """Create a managed or custom domain."""
        payload: Dict[str, Any] = {
            "kind": kind.value if isinstance(kind, DomainKind) else str(kind),
        }

        if slug is not None:
            payload["slug"] = slug
        if hostname is not None:
            payload["hostname"] = hostname
        if status is not None:
            payload["status"] = (
                status.value if isinstance(status, DomainStatus) else str(status)
            )
        if target_port is not None:
            payload["target_port"] = target_port
        if box_id is not None:
            payload["box_id"] = box_id

        response = self._request("POST", "/api/v2/domains", json=payload)
        return self._build_domain_response(response.json())

    def update_domain(
        self,
        domain_id: str,
        *,
        slug: Union[str, None, object] = _UNSET,
        hostname: Union[str, None, object] = _UNSET,
        status: Union[DomainStatus, str, object] = _UNSET,
        target_port: Union[int, None, object] = _UNSET,
        box_id: Union[str, None, object] = _UNSET,
    ) -> DomainResponse:
        """Update domain routing or metadata."""
        payload: Dict[str, Any] = {}

        if slug is not _UNSET:
            payload["slug"] = slug
        if hostname is not _UNSET:
            payload["hostname"] = hostname
        if status is not _UNSET:
            payload["status"] = (
                status.value if isinstance(status, DomainStatus) else status
            )
        if target_port is not _UNSET:
            payload["target_port"] = target_port
        if box_id is not _UNSET:
            payload["box_id"] = box_id

        response = self._request("PATCH", f"/api/v2/domains/{domain_id}", json=payload)
        return self._build_domain_response(response.json())

    def delete_domain(self, domain_id: str) -> None:
        """Delete a domain."""
        self._request("DELETE", f"/api/v2/domains/{domain_id}")

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
            with devento.box() as box:
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

    def _build_domain(self, data: Dict[str, Any]) -> Domain:
        """Convert API domain payload into Domain model."""
        return Domain(
            id=data["id"],
            hostname=data["hostname"],
            slug=data.get("slug"),
            kind=data["kind"]
            if isinstance(data.get("kind"), DomainKind)
            else DomainKind(data["kind"]),
            status=data["status"]
            if isinstance(data.get("status"), DomainStatus)
            else DomainStatus(data["status"]),
            target_port=data.get("target_port"),
            box_id=data.get("box_id"),
            cloudflare_id=data.get("cloudflare_id"),
            verification_payload=data.get("verification_payload"),
            verification_errors=data.get("verification_errors"),
            inserted_at=data.get("inserted_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def _build_domain_meta(self, meta: Dict[str, Any]) -> DomainMeta:
        """Convert API domain meta payload into DomainMeta model."""
        meta = meta or {}
        return DomainMeta(
            managed_suffix=meta.get("managed_suffix", ""),
            cname_target=meta.get("cname_target", ""),
        )

    def _build_domains_response(self, payload: Dict[str, Any]) -> DomainsResponse:
        """Convert API payload into DomainsResponse model."""
        data = payload.get("data", [])
        meta = payload.get("meta", {})
        return DomainsResponse(
            data=[self._build_domain(item) for item in data],
            meta=self._build_domain_meta(meta),
        )

    def _build_domain_response(self, payload: Dict[str, Any]) -> DomainResponse:
        """Convert API payload into DomainResponse model."""
        return DomainResponse(
            data=self._build_domain(payload["data"]),
            meta=self._build_domain_meta(payload.get("meta", {})),
        )
