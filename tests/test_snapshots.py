"""Tests for snapshot functionality."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from devento import Devento, BoxHandle, SnapshotStatus
from devento.exceptions import DeventoError, CommandTimeoutError


@pytest.fixture
def mock_client():
    """Create a mock Devento client."""
    client = Mock(spec=Devento)
    client.api_key = "test-key"
    client.base_url = "https://api.devento.ai"
    client._request = Mock()
    return client


@pytest.fixture
def box_handle(mock_client):
    """Create a BoxHandle with a mock client."""
    box_id = "box-123"
    handle = BoxHandle(mock_client, box_id)
    handle._box = Mock()
    handle._box.id = box_id
    handle._box.status = "running"
    return handle


class TestBoxHandleSnapshots:
    """Tests for BoxHandle snapshot methods."""

    def test_list_snapshots(self, box_handle, mock_client):
        """Test listing snapshots for a box."""
        mock_snapshots = [
            {
                "id": "snap-1",
                "box_id": "box-123",
                "snapshot_type": "disk",
                "status": "ready",
                "label": "backup-1",
                "size_bytes": 1024000,
                "checksum_sha256": "abc123",
                "created_at": datetime.now().isoformat(),
                "orchestrator_id": "orch-1",
            },
            {
                "id": "snap-2",
                "box_id": "box-123",
                "snapshot_type": "disk",
                "status": "creating",
                "created_at": datetime.now().isoformat(),
                "orchestrator_id": "orch-1",
            },
        ]

        mock_response = Mock()
        mock_response.json.return_value = {"data": mock_snapshots}
        mock_client._request.return_value = mock_response

        snapshots = box_handle.list_snapshots()

        mock_client._request.assert_called_once_with(
            "GET", "/api/v2/boxes/box-123/snapshots"
        )
        assert len(snapshots) == 2
        assert snapshots[0].id == "snap-1"
        assert snapshots[0].status == SnapshotStatus.READY
        assert snapshots[1].id == "snap-2"
        assert snapshots[1].status == SnapshotStatus.CREATING

    def test_get_snapshot(self, box_handle, mock_client):
        """Test fetching a specific snapshot."""
        mock_snapshot = {
            "id": "snap-1",
            "box_id": "box-123",
            "snapshot_type": "disk",
            "status": "ready",
            "label": "backup-1",
            "size_bytes": 1024000,
            "checksum_sha256": "abc123",
            "created_at": datetime.now().isoformat(),
            "orchestrator_id": "orch-1",
        }

        mock_response = Mock()
        mock_response.json.return_value = {"data": mock_snapshot}
        mock_client._request.return_value = mock_response

        snapshot = box_handle.get_snapshot("snap-1")

        mock_client._request.assert_called_once_with(
            "GET", "/api/v2/boxes/box-123/snapshots/snap-1"
        )
        assert snapshot.id == "snap-1"
        assert snapshot.status == SnapshotStatus.READY
        assert snapshot.label == "backup-1"

    def test_create_snapshot_with_params(self, box_handle, mock_client):
        """Test creating a snapshot with label and description."""
        mock_snapshot = {
            "id": "snap-new",
            "box_id": "box-123",
            "snapshot_type": "disk",
            "status": "creating",
            "label": "before-upgrade",
            "description": "Snapshot before system upgrade",
            "created_at": datetime.now().isoformat(),
            "orchestrator_id": "orch-1",
        }

        mock_response = Mock()
        mock_response.json.return_value = {"data": mock_snapshot}
        mock_client._request.return_value = mock_response

        snapshot = box_handle.create_snapshot(
            label="before-upgrade", description="Snapshot before system upgrade"
        )

        mock_client._request.assert_called_once_with(
            "POST",
            "/api/v2/boxes/box-123/snapshots",
            json={
                "label": "before-upgrade",
                "description": "Snapshot before system upgrade",
            },
        )
        assert snapshot.id == "snap-new"
        assert snapshot.status == SnapshotStatus.CREATING
        assert snapshot.label == "before-upgrade"

    def test_create_snapshot_without_params(self, box_handle, mock_client):
        """Test creating a snapshot without parameters."""
        mock_snapshot = {
            "id": "snap-new",
            "box_id": "box-123",
            "snapshot_type": "disk",
            "status": "creating",
            "created_at": datetime.now().isoformat(),
            "orchestrator_id": "orch-1",
        }

        mock_response = Mock()
        mock_response.json.return_value = {"data": mock_snapshot}
        mock_client._request.return_value = mock_response

        snapshot = box_handle.create_snapshot()

        mock_client._request.assert_called_once_with(
            "POST", "/api/v2/boxes/box-123/snapshots", json={}
        )
        assert snapshot.id == "snap-new"
        assert snapshot.status == SnapshotStatus.CREATING

    def test_restore_snapshot(self, box_handle, mock_client):
        """Test restoring a snapshot."""
        mock_snapshot = {
            "id": "snap-1",
            "box_id": "box-123",
            "snapshot_type": "disk",
            "status": "restoring",
            "created_at": datetime.now().isoformat(),
            "orchestrator_id": "orch-1",
        }

        mock_response = Mock()
        mock_response.json.return_value = {"data": mock_snapshot}
        mock_client._request.return_value = mock_response

        snapshot = box_handle.restore_snapshot("snap-1")

        mock_client._request.assert_called_once_with(
            "POST", "/api/v2/boxes/box-123/restore", json={"snapshot_id": "snap-1"}
        )
        assert snapshot.status == SnapshotStatus.RESTORING

    def test_delete_snapshot(self, box_handle, mock_client):
        """Test deleting a snapshot."""
        mock_snapshot = {
            "id": "snap-1",
            "box_id": "box-123",
            "snapshot_type": "disk",
            "status": "deleted",
            "created_at": datetime.now().isoformat(),
            "orchestrator_id": "orch-1",
        }

        mock_response = Mock()
        mock_response.json.return_value = {"data": mock_snapshot}
        mock_client._request.return_value = mock_response

        snapshot = box_handle.delete_snapshot("snap-1")

        mock_client._request.assert_called_once_with(
            "DELETE", "/api/v2/boxes/box-123/snapshots/snap-1"
        )
        assert snapshot.status == SnapshotStatus.DELETED

    @patch("time.sleep")
    def test_wait_snapshot_ready_success(self, mock_sleep, box_handle):
        """Test waiting for a snapshot to become ready."""
        # Mock the get_snapshot method to return creating then ready
        box_handle.get_snapshot = Mock()

        creating_snapshot = Mock()
        creating_snapshot.status = SnapshotStatus.CREATING

        ready_snapshot = Mock()
        ready_snapshot.status = SnapshotStatus.READY

        box_handle.get_snapshot.side_effect = [
            creating_snapshot,
            creating_snapshot,
            ready_snapshot,
        ]

        box_handle.wait_snapshot_ready("snap-1", timeout=5, poll_interval=0.1)

        assert box_handle.get_snapshot.call_count == 3
        assert mock_sleep.call_count == 2

    def test_wait_snapshot_ready_error(self, box_handle):
        """Test waiting for a snapshot that ends in error."""
        box_handle.get_snapshot = Mock()

        error_snapshot = Mock()
        error_snapshot.status = SnapshotStatus.ERROR

        box_handle.get_snapshot.return_value = error_snapshot

        with pytest.raises(DeventoError) as exc_info:
            box_handle.wait_snapshot_ready("snap-1")

        assert "ended with status: error" in str(exc_info.value)

    def test_wait_snapshot_ready_deleted(self, box_handle):
        """Test waiting for a snapshot that gets deleted."""
        box_handle.get_snapshot = Mock()

        deleted_snapshot = Mock()
        deleted_snapshot.status = SnapshotStatus.DELETED

        box_handle.get_snapshot.return_value = deleted_snapshot

        with pytest.raises(DeventoError) as exc_info:
            box_handle.wait_snapshot_ready("snap-1")

        assert "ended with status: deleted" in str(exc_info.value)

    @patch("time.time")
    @patch("time.sleep")
    def test_wait_snapshot_ready_timeout(self, mock_sleep, mock_time, box_handle):
        """Test waiting for a snapshot that times out."""
        box_handle.get_snapshot = Mock()

        creating_snapshot = Mock()
        creating_snapshot.status = SnapshotStatus.CREATING

        box_handle.get_snapshot.return_value = creating_snapshot

        # Mock time to simulate timeout
        mock_time.side_effect = [0, 0.5, 1, 2, 3, 4]  # Exceeds timeout of 3 seconds

        with pytest.raises(CommandTimeoutError) as exc_info:
            box_handle.wait_snapshot_ready("snap-1", timeout=3, poll_interval=0.1)

        assert "did not become ready within 3s" in str(exc_info.value)
