"""Tests for expose_port functionality."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from tavor import Tavor, BoxHandle, ExposedPort
from tavor.exceptions import TavorError


class TestExposePort:
    """Test expose_port functionality."""

    @patch("tavor.client.requests.Session")
    def test_expose_port_success(self, mock_session_class):
        """Test successful port exposure."""
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "data": {
                "proxy_port": 12345,
                "target_port": 3000,
                "expires_at": "2024-12-31T23:59:59Z",
            }
        }
        mock_session.request.return_value = mock_response

        # Create client and box handle
        client = Tavor(api_key="sk-tavor-test")
        box_handle = BoxHandle(client, "test-box-id")

        # Test expose_port
        result = box_handle.expose_port(3000)

        # Verify request
        mock_session.request.assert_called_with(
            "POST",
            "https://api.tavor.dev/api/v2/boxes/test-box-id/expose_port",
            json={"port": 3000},
            timeout=30,
        )

        # Verify result
        assert isinstance(result, ExposedPort)
        assert result.proxy_port == 12345
        assert result.target_port == 3000
        assert result.expires_at == datetime(
            2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc
        )

    @patch("tavor.client.requests.Session")
    def test_expose_port_different_port(self, mock_session_class):
        """Test exposing a different port."""
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "data": {
                "proxy_port": 54321,
                "target_port": 8080,
                "expires_at": "2024-12-31T23:59:59Z",
            }
        }
        mock_session.request.return_value = mock_response

        # Create client and box handle
        client = Tavor(api_key="sk-tavor-test")
        box_handle = BoxHandle(client, "test-box-id")

        # Test expose_port
        result = box_handle.expose_port(8080)

        # Verify request
        mock_session.request.assert_called_with(
            "POST",
            "https://api.tavor.dev/api/v2/boxes/test-box-id/expose_port",
            json={"port": 8080},
            timeout=30,
        )

        # Verify result
        assert result.proxy_port == 54321
        assert result.target_port == 8080

    @patch("tavor.client.requests.Session")
    def test_expose_port_box_not_running(self, mock_session_class):
        """Test error when box is not running."""
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_response = Mock()
        mock_response.status_code = 409
        mock_response.json.return_value = {"error": "Box is not in a running state"}
        mock_response.headers = {"content-type": "application/json"}
        mock_session.request.return_value = mock_response

        # Create client and box handle
        client = Tavor(api_key="sk-tavor-test")
        box_handle = BoxHandle(client, "test-box-id")

        # Test expose_port
        with pytest.raises(TavorError) as exc_info:
            box_handle.expose_port(3000)

        assert "Box is not in a running state" in str(exc_info.value)

    @patch("tavor.client.requests.Session")
    def test_expose_port_no_ports_available(self, mock_session_class):
        """Test error when no ports are available."""
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.json.return_value = {
            "error": "Could not allocate a proxy port, please try again."
        }
        mock_response.headers = {"content-type": "application/json"}
        mock_session.request.return_value = mock_response

        # Create client and box handle
        client = Tavor(api_key="sk-tavor-test")
        box_handle = BoxHandle(client, "test-box-id")

        # Test expose_port
        with pytest.raises(TavorError) as exc_info:
            box_handle.expose_port(3000)

        assert "Could not allocate a proxy port" in str(exc_info.value)

    @patch("tavor.client.requests.Session")
    def test_expose_port_with_timezone_handling(self, mock_session_class):
        """Test that different timezone formats are handled correctly."""
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Test with different timezone formats
        test_cases = [
            (
                "2024-12-31T23:59:59Z",
                datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
            ),
            (
                "2024-12-31T23:59:59+00:00",
                datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
            ),
        ]

        for expires_at_str, expected_datetime in test_cases:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "data": {
                    "proxy_port": 12345,
                    "target_port": 3000,
                    "expires_at": expires_at_str,
                }
            }
            mock_session.request.return_value = mock_response

            # Create client and box handle
            client = Tavor(api_key="sk-tavor-test")
            box_handle = BoxHandle(client, "test-box-id")

            # Test expose_port
            result = box_handle.expose_port(3000)

            # Verify result
            assert result.expires_at == expected_datetime
