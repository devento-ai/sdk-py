"""Tests for async expose_port functionality."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

from tavor import AsyncTavor, AsyncBoxHandle, ExposedPort
from tavor.exceptions import TavorError


class TestAsyncExposePort:
    """Test async expose_port functionality."""

    @pytest.mark.asyncio
    @patch("tavor.async_client.aiohttp.ClientSession")
    async def test_expose_port_success(self, mock_session_class):
        """Test successful port exposure."""
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_response = Mock()
        mock_response.status = 201
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "proxy_port": 12345,
                    "target_port": 3000,
                    "expires_at": "2024-12-31T23:59:59Z",
                }
            }
        )
        mock_response.headers = {"content-type": "application/json"}

        mock_session.request = Mock(return_value=mock_response)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Create client and box handle
        client = AsyncTavor(api_key="sk-tavor-test")
        client.session = mock_session
        box_handle = AsyncBoxHandle(client, "test-box-id")

        # Test expose_port
        result = await box_handle.expose_port(3000)

        # Verify request
        mock_session.request.assert_called_with(
            "POST",
            "https://api.tavor.dev/api/v2/boxes/test-box-id/expose_port",
            json={"port": 3000},
        )

        # Verify result
        assert isinstance(result, ExposedPort)
        assert result.proxy_port == 12345
        assert result.target_port == 3000
        assert result.expires_at == datetime(
            2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc
        )

    @pytest.mark.asyncio
    @patch("tavor.async_client.aiohttp.ClientSession")
    async def test_expose_port_different_port(self, mock_session_class):
        """Test exposing a different port."""
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_response = Mock()
        mock_response.status = 201
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "proxy_port": 54321,
                    "target_port": 8080,
                    "expires_at": "2024-12-31T23:59:59Z",
                }
            }
        )
        mock_response.headers = {"content-type": "application/json"}

        mock_session.request = Mock(return_value=mock_response)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Create client and box handle
        client = AsyncTavor(api_key="sk-tavor-test")
        client.session = mock_session
        box_handle = AsyncBoxHandle(client, "test-box-id")

        # Test expose_port
        result = await box_handle.expose_port(8080)

        # Verify request
        mock_session.request.assert_called_with(
            "POST",
            "https://api.tavor.dev/api/v2/boxes/test-box-id/expose_port",
            json={"port": 8080},
        )

        # Verify result
        assert result.proxy_port == 54321
        assert result.target_port == 8080

    @pytest.mark.asyncio
    @patch("tavor.async_client.aiohttp.ClientSession")
    async def test_expose_port_box_not_running(self, mock_session_class):
        """Test error when box is not running."""
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_response = Mock()
        mock_response.status = 409
        mock_response.json = AsyncMock(
            return_value={"error": "Box is not in a running state"}
        )
        mock_response.headers = {"content-type": "application/json"}

        mock_session.request = Mock(return_value=mock_response)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Create client and box handle
        client = AsyncTavor(api_key="sk-tavor-test")
        client.session = mock_session
        box_handle = AsyncBoxHandle(client, "test-box-id")

        # Test expose_port
        with pytest.raises(TavorError) as exc_info:
            await box_handle.expose_port(3000)

        assert "Box is not in a running state" in str(exc_info.value)
