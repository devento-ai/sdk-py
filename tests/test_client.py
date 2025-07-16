"""Tests for Tavor client."""

import pytest
from unittest.mock import Mock, patch

from tavor import Tavor, BoxConfig, AuthenticationError


class TestTavorClient:
    """Test Tavor client functionality."""

    def test_init_requires_api_key(self, monkeypatch):
        """Test that API key is required."""
        # Clear any environment variable
        monkeypatch.delenv("TAVOR_API_KEY", raising=False)
        with pytest.raises(ValueError, match="API key is required"):
            Tavor()

    def test_init_with_api_key(self):
        """Test client initialization with API key."""
        client = Tavor(api_key="sk-tavor-test")
        assert client.api_key == "sk-tavor-test"
        assert client.base_url == "https://api.tavor.dev"
        assert client.timeout == 30

    def test_init_with_custom_base_url(self):
        """Test client initialization with custom base URL."""
        client = Tavor(api_key="sk-tavor-test", base_url="http://localhost:4000/")
        assert client.base_url == "http://localhost:4000"

    @patch("tavor.client.requests.Session")
    def test_headers_are_set(self, mock_session_class):
        """Test that headers are properly set."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        Tavor(api_key="sk-tavor-test")

        mock_session.headers.update.assert_called_with(
            {"X-API-Key": "sk-tavor-test", "Content-Type": "application/json"}
        )

    @patch("tavor.client.requests.Session")
    def test_request_error_handling(self, mock_session_class):
        """Test API error handling."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock 401 response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid API key"}
        mock_response.headers = {"content-type": "application/json"}
        mock_session.request.return_value = mock_response

        client = Tavor(api_key="sk-tavor-invalid")

        with pytest.raises(AuthenticationError) as exc_info:
            client._request("GET", "/api/v2/boxes")

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in str(exc_info.value)

    @patch("tavor.client.requests.Session")
    def test_list_boxes(self, mock_session_class):
        """Test listing boxes."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "box-123",
                    "status": "running",
                    "timeout": 3600,
                    "created_at": "2024-01-01T00:00:00Z",
                    "details": None,
                    "hostname": "box789.tavor.app",
                }
            ]
        }
        mock_session.request.return_value = mock_response

        client = Tavor(api_key="sk-tavor-test")
        boxes = client.list_boxes()

        assert len(boxes) == 1
        assert boxes[0].id == "box-123"
        assert boxes[0].status.value == "running"
        assert boxes[0].timeout == 3600
        assert boxes[0].hostname == "box789.tavor.app"

    @patch("tavor.client.requests.Session")
    def test_box_context_manager(self, mock_session_class):
        """Test box context manager."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock create box response
        create_response = Mock()
        create_response.status_code = 200
        create_response.json.return_value = {"id": "box-456"}

        # Mock delete box response
        delete_response = Mock()
        delete_response.status_code = 204

        # Mock list boxes response (for status check)
        list_response = Mock()
        list_response.status_code = 200
        list_response.json.return_value = {
            "data": [
                {
                    "id": "box-456",
                    "status": "running",
                    "timeout": 3600,
                    "created_at": "2024-01-01T00:00:00Z",
                    "hostname": "box-456.tavor.app",
                }
            ]
        }

        # Configure mock to return different responses
        mock_session.request.side_effect = [
            create_response,  # Create box
            list_response,  # Status check
            delete_response,  # Delete box
        ]

        client = Tavor(api_key="sk-tavor-test")

        with client.box() as box:
            assert box.id == "box-456"
            box.refresh()  # This triggers the list call

        # Verify create and delete were called
        assert mock_session.request.call_count == 3

        # Check create call
        create_call = mock_session.request.call_args_list[0]
        assert create_call[0][0] == "POST"
        assert "/api/v2/boxes" in create_call[0][1]

        # Check delete call
        delete_call = mock_session.request.call_args_list[2]
        assert delete_call[0][0] == "DELETE"
        assert "/api/v2/boxes/box-456" in delete_call[0][1]

    def test_box_config_validation(self):
        """Test BoxConfig validation."""
        # Test default values
        config = BoxConfig()
        assert config.cpu is None
        assert config.mib_ram is None
        assert config.timeout == 600
        assert config.metadata is None

        # Test with specific cpu and ram
        config = BoxConfig(cpu=2, mib_ram=4096)
        assert config.cpu == 2
        assert config.mib_ram == 4096

        # Test with all parameters
        config = BoxConfig(cpu=4, mib_ram=8192, timeout=1200, metadata={"env": "test"})
        assert config.cpu == 4
        assert config.mib_ram == 8192
        assert config.timeout == 1200
        assert config.metadata == {"env": "test"}

    @patch("tavor.client.requests.Session")
    def test_box_handle_get_public_url(self, mock_session_class):
        """Test BoxHandle.get_public_url method."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock create box response with hostname
        create_response = Mock()
        create_response.status_code = 200
        create_response.json.return_value = {
            "id": "box-888",
        }

        # Mock list boxes response for refresh
        list_response = Mock()
        list_response.status_code = 200
        list_response.json.return_value = {
            "data": [
                {
                    "id": "box-888",
                    "status": "running",
                    "timeout": 3600,
                    "created_at": "2024-01-01T00:00:00Z",
                    "hostname": "box888.tavor.app",
                }
            ]
        }

        # Mock delete box response
        delete_response = Mock()
        delete_response.status_code = 204

        mock_session.request.side_effect = [
            create_response,
            list_response,
            list_response,  # Second refresh call from get_public_url (port 8080)
            list_response,  # Third refresh call from get_public_url (port 3000)
            delete_response,
        ]

        client = Tavor(api_key="sk-tavor-test")

        with client.box() as box:
            box.refresh()  # This triggers the list call

            # Test get_public_url
            url = box.get_public_url(8080)
            assert url == "https://8080-box888.tavor.app"

            # Test with different port
            url = box.get_public_url(3000)
            assert url == "https://3000-box888.tavor.app"

    @patch("tavor.client.requests.Session")
    def test_box_pause_resume(self, mock_session_class):
        """Test box pause and resume functionality."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock create box response
        create_response = Mock()
        create_response.status_code = 200
        create_response.json.return_value = {"id": "box-pause-test"}

        # Mock list boxes response (for refresh after pause)
        list_response_paused = Mock()
        list_response_paused.status_code = 200
        list_response_paused.json.return_value = {
            "data": [
                {
                    "id": "box-pause-test",
                    "status": "paused",  # Paused state
                    "timeout": 3600,
                    "created_at": "2024-01-01T00:00:00Z",
                    "details": None,
                    "hostname": "box-pause.tavor.app",
                }
            ]
        }

        # Mock list boxes response (for refresh after resume)
        list_response_resumed = Mock()
        list_response_resumed.status_code = 200
        list_response_resumed.json.return_value = {
            "data": [
                {
                    "id": "box-pause-test",
                    "status": "running",  # Resumed state
                    "timeout": 3600,
                    "created_at": "2024-01-01T00:00:00Z",
                    "details": None,
                    "hostname": "box-pause.tavor.app",
                }
            ]
        }

        # Mock pause response
        pause_response = Mock()
        pause_response.status_code = 200
        pause_response.json.return_value = {}

        # Mock resume response
        resume_response = Mock()
        resume_response.status_code = 200
        resume_response.json.return_value = {}

        # Mock delete box response
        delete_response = Mock()
        delete_response.status_code = 204

        mock_session.request.side_effect = [
            create_response,
            pause_response,
            list_response_paused,  # Refresh after pause
            resume_response,
            list_response_resumed,  # Refresh after resume
            delete_response,
        ]

        client = Tavor(api_key="sk-tavor-test")

        with client.box() as box:
            # Test pause
            box.pause()

            # Verify pause request was made
            pause_call = mock_session.request.call_args_list[1]
            assert pause_call[0][0] == "POST"
            assert pause_call[0][1].endswith("/api/v2/boxes/box-pause-test/pause")

            # Test resume
            box.resume()

            # Verify resume request was made
            resume_call = mock_session.request.call_args_list[3]
            assert resume_call[0][0] == "POST"
            assert resume_call[0][1].endswith("/api/v2/boxes/box-pause-test/resume")
