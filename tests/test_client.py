"""Tests for Tavor client."""

import pytest
from unittest.mock import Mock, patch

from tavor import Tavor, BoxConfig, BoxTemplate, AuthenticationError


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
        # Test with both template and template_id
        with pytest.raises(
            ValueError, match="Cannot specify both template and template_id"
        ):
            BoxConfig(template=BoxTemplate.BASIC, template_id="custom-template")

        # Test default template
        config = BoxConfig()
        assert config.template == BoxTemplate.BASIC

        # Test with custom template_id
        config = BoxConfig(template_id="boxt-custom")
        assert config.template_id == "boxt-custom"
        assert config.template is None
