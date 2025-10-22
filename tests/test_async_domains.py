"""Async domain management tests."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from devento import AsyncDevento, DomainKind, DomainStatus


class TestAsyncDomains:
    """Test async domain API helpers."""

    @pytest.mark.asyncio
    @patch("devento.async_client.aiohttp.ClientSession")
    async def test_list_domains(self, mock_session_class):
        """Ensure list_domains returns typed models."""
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
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=domain_payload)
        mock_response.headers = {"content-type": "application/json"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session.request = Mock(return_value=mock_response)

        client = AsyncDevento(api_key="sk-devento-test")
        client._session = mock_session

        result = await client.list_domains()

        assert result.data[0].kind is DomainKind.MANAGED
        assert result.meta.cname_target == "edge.deven.to"

        mock_session.request.assert_called_with(
            "GET", "https://api.devento.ai/api/v2/domains"
        )

    @pytest.mark.asyncio
    @patch("devento.async_client.aiohttp.ClientSession")
    async def test_update_domain_allows_nulls(self, mock_session_class):
        """Ensure update_domain forwards null values."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        domain_payload = {
            "data": {
                "id": "dom_123",
                "hostname": "app.deven.to",
                "slug": "app",
                "kind": "managed",
                "status": "pending_dns",
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
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=domain_payload)
        mock_response.headers = {"content-type": "application/json"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session.request = Mock(return_value=mock_response)

        client = AsyncDevento(api_key="sk-devento-test")
        client._session = mock_session

        await client.update_domain(
            "dom_123",
            target_port=None,
            box_id=None,
            status=DomainStatus.PENDING_DNS,
        )

        args, kwargs = mock_session.request.call_args
        assert args[0] == "PATCH"
        assert args[1] == "https://api.devento.ai/api/v2/domains/dom_123"
        assert kwargs["json"]["target_port"] is None
        assert kwargs["json"]["box_id"] is None
        assert kwargs["json"]["status"] == "pending_dns"
