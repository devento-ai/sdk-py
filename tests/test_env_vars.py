"""Tests for environment variable support."""

import pytest

from tavor import Tavor, AsyncTavor, BoxConfig, BoxTemplate


class TestEnvironmentVariables:
    """Test environment variable support."""

    def test_api_key_from_env(self, monkeypatch):
        """Test API key from environment variable."""
        monkeypatch.setenv("TAVOR_API_KEY", "sk-tavor-test-env")

        client = Tavor()
        assert client.api_key == "sk-tavor-test-env"

    def test_api_key_explicit_overrides_env(self, monkeypatch):
        """Test explicit API key overrides environment."""
        monkeypatch.setenv("TAVOR_API_KEY", "sk-tavor-test-env")

        client = Tavor(api_key="sk-tavor-explicit")
        assert client.api_key == "sk-tavor-explicit"

    def test_base_url_from_env(self, monkeypatch):
        """Test base URL from environment variable."""
        monkeypatch.setenv("TAVOR_API_KEY", "sk-tavor-test")
        monkeypatch.setenv("TAVOR_BASE_URL", "http://localhost:4000")

        client = Tavor()
        assert client.base_url == "http://localhost:4000"

    def test_base_url_explicit_overrides_env(self, monkeypatch):
        """Test explicit base URL overrides environment."""
        monkeypatch.setenv("TAVOR_API_KEY", "sk-tavor-test")
        monkeypatch.setenv("TAVOR_BASE_URL", "http://localhost:4000")

        client = Tavor(base_url="https://custom.api.com")
        assert client.base_url == "https://custom.api.com"

    def test_base_url_default_when_no_env(self, monkeypatch):
        """Test default base URL when no environment variable."""
        monkeypatch.delenv("TAVOR_BASE_URL", raising=False)

        client = Tavor(api_key="sk-tavor-test")
        assert client.base_url == "https://api.tavor.dev"

    def test_box_template_from_env(self, monkeypatch):
        """Test box template from environment variable."""
        monkeypatch.setenv("TAVOR_BOX_TEMPLATE", "Pro")

        config = BoxConfig()
        assert config.template == BoxTemplate.PRO

    def test_box_template_custom_id_from_env(self, monkeypatch):
        """Test custom box template ID from environment variable."""
        monkeypatch.setenv("TAVOR_BOX_TEMPLATE", "boxt-custom-123")

        config = BoxConfig()
        assert config.template is None
        assert config.template_id == "boxt-custom-123"

    def test_box_template_explicit_overrides_env(self, monkeypatch):
        """Test explicit template overrides environment."""
        monkeypatch.setenv("TAVOR_BOX_TEMPLATE", "Pro")

        config = BoxConfig(template=BoxTemplate.BASIC)
        assert config.template == BoxTemplate.BASIC

    def test_box_timeout_from_env(self, monkeypatch):
        """Test box timeout from environment variable."""
        monkeypatch.setenv("TAVOR_BOX_TIMEOUT", "7200")

        config = BoxConfig()
        assert config.timeout == 7200

    def test_box_timeout_invalid_env_uses_default(self, monkeypatch):
        """Test invalid timeout in environment uses default."""
        monkeypatch.setenv("TAVOR_BOX_TIMEOUT", "invalid")

        config = BoxConfig()
        assert config.timeout == 600

    def test_box_timeout_explicit_overrides_env(self, monkeypatch):
        """Test explicit timeout overrides environment."""
        monkeypatch.setenv("TAVOR_BOX_TIMEOUT", "7200")

        config = BoxConfig(timeout=1800)
        assert config.timeout == 1800

    @pytest.mark.asyncio
    async def test_async_client_env_vars(self, monkeypatch):
        """Test AsyncTavor also supports environment variables."""
        monkeypatch.setenv("TAVOR_API_KEY", "sk-tavor-async-test")
        monkeypatch.setenv("TAVOR_BASE_URL", "http://async.localhost:4000")

        # Don't actually create session, just test initialization
        client = AsyncTavor()
        assert client.api_key == "sk-tavor-async-test"
        assert client.base_url == "http://async.localhost:4000"
