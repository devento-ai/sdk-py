"""Tests for Devento client."""

import pytest
from unittest.mock import Mock, patch

from devento import (
    Devento,
    BoxConfig,
    AuthenticationError,
    DomainKind,
    DomainStatus,
)


class TestDeventoClient:
    """Test Devento client functionality."""

    def test_init_requires_api_key(self, monkeypatch):
        """Test that API key is required."""
        # Clear any environment variable
        monkeypatch.delenv("DEVENTO_API_KEY", raising=False)
        with pytest.raises(ValueError, match="API key is required"):
            Devento()

    def test_init_with_api_key(self):
        """Test client initialization with API key."""
        client = Devento(api_key="sk-devento-test")
        assert client.api_key == "sk-devento-test"
        assert client.base_url == "https://api.devento.ai"
        assert client.timeout == 30

    def test_init_with_custom_base_url(self):
        """Test client initialization with custom base URL."""
        client = Devento(api_key="sk-devento-test", base_url="http://localhost:4000/")
        assert client.base_url == "http://localhost:4000"

    @patch("devento.client.requests.Session")
    def test_headers_are_set(self, mock_session_class):
        """Test that headers are properly set."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        Devento(api_key="sk-devento-test")

        mock_session.headers.update.assert_called_with(
            {"X-API-Key": "sk-devento-test", "Content-Type": "application/json"}
        )

    @patch("devento.client.requests.Session")
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

        client = Devento(api_key="sk-devento-invalid")

        with pytest.raises(AuthenticationError) as exc_info:
            client._request("GET", "/api/v2/boxes")

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in str(exc_info.value)

    @patch("devento.client.requests.Session")
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
                    "hostname": "box789.deven.to",
                }
            ]
        }
        mock_session.request.return_value = mock_response

        client = Devento(api_key="sk-devento-test")
        boxes = client.list_boxes()

        assert len(boxes) == 1
        assert boxes[0].id == "box-123"
        assert boxes[0].status.value == "running"
        assert boxes[0].timeout == 3600
        assert boxes[0].hostname == "box789.deven.to"

    @patch("devento.client.requests.Session")
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

        # Mock get box response (for status check)
        get_response = Mock()
        get_response.status_code = 200
        get_response.json.return_value = {
            "data": {
                "id": "box-456",
                "status": "running",
                "timeout": 3600,
                "created_at": "2024-01-01T00:00:00Z",
                "hostname": "box-456.deven.to",
            }
        }

        # Configure mock to return different responses
        mock_session.request.side_effect = [
            create_response,  # Create box
            get_response,  # Status check
            delete_response,  # Delete box
        ]

        client = Devento(api_key="sk-devento-test")

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

    @patch("devento.client.requests.Session")
    def test_list_domains(self, mock_session_class):
        """Test listing domains returns typed response."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        domain_payload = {
            "data": [
                {
                    "id": "dom_123",
                    "hostname": "app.deven.to",
                    "slug": "app",
                    "kind": "managed",
                    "status": "active",
                    "target_port": 4000,
                    "box_id": "box_123",
                    "cloudflare_id": None,
                    "verification_payload": {},
                    "verification_errors": {},
                    "inserted_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                }
            ],
            "meta": {"managed_suffix": "deven.to", "cname_target": "edge.deven.to"},
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = domain_payload
        mock_response.headers = {"content-type": "application/json"}
        mock_session.request.return_value = mock_response

        client = Devento(api_key="sk-devento-test")
        result = client.list_domains()

        assert result.meta.managed_suffix == "deven.to"
        assert result.data[0].kind == DomainKind.MANAGED
        assert result.data[0].status == DomainStatus.ACTIVE

        mock_session.request.assert_called_with(
            "GET", "https://api.devento.ai/api/v2/domains", timeout=30
        )

    @patch("devento.client.requests.Session")
    def test_create_domain_omits_none_fields(self, mock_session_class):
        """Test creating managed domain omits optional None fields."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        domain_payload = {
            "data": {
                "id": "dom_123",
                "hostname": "app.deven.to",
                "slug": "app",
                "kind": "managed",
                "status": "active",
                "target_port": 4000,
                "box_id": "box_123",
                "cloudflare_id": None,
                "verification_payload": {},
                "verification_errors": {},
                "inserted_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
            },
            "meta": {"managed_suffix": "deven.to", "cname_target": "edge.deven.to"},
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = domain_payload
        mock_response.headers = {"content-type": "application/json"}
        mock_session.request.return_value = mock_response

        client = Devento(api_key="sk-devento-test")
        client.create_domain(
            kind=DomainKind.MANAGED,
            slug="app",
            hostname=None,
            target_port=4000,
            box_id="box_123",
        )

        args, kwargs = mock_session.request.call_args
        assert args[0] == "POST"
        assert args[1] == "https://api.devento.ai/api/v2/domains"
        assert kwargs["json"]["kind"] == "managed"
        assert "hostname" not in kwargs["json"]

    @patch("devento.client.requests.Session")
    def test_update_domain_allows_nulls(self, mock_session_class):
        """Test updating domain allows explicit null values."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        domain_payload = {
            "data": {
                "id": "dom_123",
                "hostname": "app.deven.to",
                "slug": "app",
                "kind": "managed",
                "status": "active",
                "target_port": None,
                "box_id": None,
                "cloudflare_id": None,
                "verification_payload": {},
                "verification_errors": {},
                "inserted_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
            },
            "meta": {"managed_suffix": "deven.to", "cname_target": "edge.deven.to"},
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = domain_payload
        mock_response.headers = {"content-type": "application/json"}
        mock_session.request.return_value = mock_response

        client = Devento(api_key="sk-devento-test")
        client.update_domain(
            "dom_123",
            target_port=None,
            box_id=None,
            status=DomainStatus.PENDING_DNS,
        )

        _, kwargs = mock_session.request.call_args
        assert kwargs["json"]["target_port"] is None
        assert kwargs["json"]["box_id"] is None
        assert kwargs["json"]["status"] == "pending_dns"

    @patch("devento.client.requests.Session")
    def test_delete_domain(self, mock_session_class):
        """Test deleting domain issues DELETE request."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.headers = {}
        mock_session.request.return_value = mock_response

        client = Devento(api_key="sk-devento-test")
        client.delete_domain("dom_123")

        mock_session.request.assert_called_with(
            "DELETE", "https://api.devento.ai/api/v2/domains/dom_123", timeout=30
        )

    def test_box_config_validation(self):
        """Test BoxConfig validation."""
        # Test default values
        config = BoxConfig()
        assert config.cpu is None
        assert config.mib_ram is None
        assert config.timeout == 600
        assert config.metadata is None
        assert config.watermark_enabled is None

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

        # Test with watermark_enabled
        config = BoxConfig(watermark_enabled=False)
        assert config.watermark_enabled is False

        config = BoxConfig(watermark_enabled=True)
        assert config.watermark_enabled is True

    @patch("devento.client.requests.Session")
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

        # Mock get box response for refresh
        get_response = Mock()
        get_response.status_code = 200
        get_response.json.return_value = {
            "data": {
                "id": "box-888",
                "status": "running",
                "timeout": 3600,
                "created_at": "2024-01-01T00:00:00Z",
                "hostname": "box888.deven.to",
            }
        }

        # Mock delete box response
        delete_response = Mock()
        delete_response.status_code = 204

        mock_session.request.side_effect = [
            create_response,
            get_response,
            get_response,  # Second refresh call from get_public_url (port 8080)
            get_response,  # Third refresh call from get_public_url (port 3000)
            delete_response,
        ]

        client = Devento(api_key="sk-devento-test")

        with client.box() as box:
            box.refresh()  # This triggers the list call

            # Test get_public_url
            url = box.get_public_url(8080)
            assert url == "https://8080-box888.deven.to"

            # Test with different port
            url = box.get_public_url(3000)
            assert url == "https://3000-box888.deven.to"

    @patch("devento.client.requests.Session")
    def test_box_pause_resume(self, mock_session_class):
        """Test box pause and resume functionality."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock create box response
        create_response = Mock()
        create_response.status_code = 200
        create_response.json.return_value = {"id": "box-pause-test"}

        # Mock get box response (for refresh after pause)
        get_response_paused = Mock()
        get_response_paused.status_code = 200
        get_response_paused.json.return_value = {
            "data": {
                "id": "box-pause-test",
                "status": "paused",  # Paused state
                "timeout": 3600,
                "created_at": "2024-01-01T00:00:00Z",
                "details": None,
                "hostname": "box-pause.deven.to",
            }
        }

        # Mock get box response (for refresh after resume)
        get_response_resumed = Mock()
        get_response_resumed.status_code = 200
        get_response_resumed.json.return_value = {
            "data": {
                "id": "box-pause-test",
                "status": "running",  # Resumed state
                "timeout": 3600,
                "created_at": "2024-01-01T00:00:00Z",
                "details": None,
                "hostname": "box-pause.deven.to",
            }
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
            get_response_paused,  # Refresh after pause
            resume_response,
            get_response_resumed,  # Refresh after resume
            delete_response,
        ]

        client = Devento(api_key="sk-devento-test")

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

    @patch("devento.client.requests.Session")
    def test_create_box_with_watermark_enabled(self, mock_session_class):
        """Test creating a box with watermark_enabled option."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock create box response
        create_response = Mock()
        create_response.status_code = 200
        create_response.json.return_value = {"id": "box-watermark-test"}

        mock_session.request.return_value = create_response

        client = Devento(api_key="sk-devento-test")

        # Test with watermark_enabled=False
        config = BoxConfig(watermark_enabled=False)
        box = client.create_box(config)

        assert box.id == "box-watermark-test"

        # Verify the request included watermark_enabled
        create_call = mock_session.request.call_args_list[0]
        assert create_call[0][0] == "POST"
        assert create_call[1]["json"]["watermark_enabled"] is False

    @patch("devento.client.requests.Session")
    def test_box_handle_watermark_enabled_property(self, mock_session_class):
        """Test BoxHandle.watermark_enabled property."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock create box response
        create_response = Mock()
        create_response.status_code = 200
        create_response.json.return_value = {"id": "box-watermark-test"}

        # Mock get box response with watermark_enabled
        get_response = Mock()
        get_response.status_code = 200
        get_response.json.return_value = {
            "data": {
                "id": "box-watermark-test",
                "status": "running",
                "timeout": 3600,
                "created_at": "2024-01-01T00:00:00Z",
                "hostname": "box-watermark.deven.to",
                "watermark_enabled": True,
            }
        }

        mock_session.request.side_effect = [create_response, get_response]

        client = Devento(api_key="sk-devento-test")
        box = client.create_box()
        box.refresh()

        assert box.watermark_enabled is True

    @patch("devento.client.requests.Session")
    def test_box_handle_set_watermark(self, mock_session_class):
        """Test BoxHandle.set_watermark method."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock create box response
        create_response = Mock()
        create_response.status_code = 200
        create_response.json.return_value = {"id": "box-watermark-test"}

        # Mock PATCH response for set_watermark
        patch_response = Mock()
        patch_response.status_code = 200
        patch_response.json.return_value = {}

        # Mock get box response after set_watermark (refresh)
        get_response = Mock()
        get_response.status_code = 200
        get_response.json.return_value = {
            "data": {
                "id": "box-watermark-test",
                "status": "running",
                "timeout": 3600,
                "created_at": "2024-01-01T00:00:00Z",
                "hostname": "box-watermark.deven.to",
                "watermark_enabled": False,
            }
        }

        mock_session.request.side_effect = [
            create_response,
            patch_response,
            get_response,
        ]

        client = Devento(api_key="sk-devento-test")
        box = client.create_box()
        box.set_watermark(False)

        # Verify PATCH request was made with correct payload
        patch_call = mock_session.request.call_args_list[1]
        assert patch_call[0][0] == "PATCH"
        assert patch_call[0][1].endswith("/api/v2/boxes/box-watermark-test")
        assert patch_call[1]["json"]["watermark_enabled"] is False

        # Verify the watermark_enabled property is updated after refresh
        assert box.watermark_enabled is False
