"""
Configuration validation tests for WAAST360 Bridge production deployment.

Tests cover:
- Development vs. Production mode differentiation
- API Key security constraints
- Cloud URL HTTPS enforcement for production
- Credential validation
- Environment variable handling
"""

import pytest
from pydantic import ValidationError

from src.config import BridgeSettings


class TestDevelopmentConfiguration:
    """Tests for safe development configuration."""

    def test_dev_mode_allows_http_localhost(self):
        """Development mode allows HTTP on localhost."""
        settings = BridgeSettings(
            BRIDGE_ENV="development",
            CLOUD_URL="http://127.0.0.1:8000",
            BRIDGE_API_KEY="test-bridge-secret-key",
        )
        assert settings.CLOUD_URL == "http://127.0.0.1:8000"
        assert settings.is_development
        assert not settings.is_production

    def test_dev_mode_default_test_api_key(self):
        """Development mode accepts test API key as default."""
        settings = BridgeSettings(BRIDGE_ENV="development")
        assert settings.BRIDGE_API_KEY == "test-bridge-secret-key"

    def test_dev_mode_allows_empty_cloud_url_default(self):
        """Development mode provides sensible default for empty CLOUD_URL."""
        settings = BridgeSettings(BRIDGE_ENV="development", CLOUD_URL="")
        assert settings.CLOUD_URL == "http://127.0.0.1:8000"

    def test_dev_mode_properties(self):
        """Development mode properties are correctly set."""
        settings = BridgeSettings(BRIDGE_ENV="development")
        assert settings.is_development
        assert not settings.is_production


class TestProductionConfiguration:
    """Tests for production safety constraints."""

    def test_prod_mode_rejects_http(self):
        """Production mode rejects insecure HTTP URLs."""
        with pytest.raises(ValidationError) as exc_info:
            BridgeSettings(
                BRIDGE_ENV="production",
                CLOUD_URL="http://waast360-api.example.com",
            )

        error = exc_info.value.errors()[0]
        assert "HTTPS" in error["msg"] or "insecure" in error["msg"]

    def test_prod_mode_requires_cloud_url(self):
        """Production mode requires non-empty CLOUD_URL."""
        with pytest.raises(ValidationError) as exc_info:
            BridgeSettings(
                BRIDGE_ENV="production",
                CLOUD_URL="",
            )

        error = exc_info.value.errors()[0]
        assert "required" in error["msg"] or "cannot be empty" in error["msg"]

    def test_prod_mode_rejects_test_api_key(self):
        """Production mode rejects test API key as primary credential."""
        with pytest.raises(ValidationError) as exc_info:
            BridgeSettings(
                BRIDGE_ENV="production",
                CLOUD_URL="https://waast360-api.example.com",
                BRIDGE_API_KEY="test-bridge-secret-key",
            )

        error = exc_info.value.errors()[0]
        assert "test" in error["msg"] or "production" in error["msg"]

    def test_prod_mode_requires_api_key(self):
        """Production mode requires valid API key."""
        with pytest.raises(ValidationError) as exc_info:
            BridgeSettings(
                BRIDGE_ENV="production",
                CLOUD_URL="https://waast360-api.example.com",
                BRIDGE_API_KEY="",
            )

        error = exc_info.value.errors()[0]
        assert "required" in error["msg"] or "API" in error["msg"]

    def test_prod_mode_accepts_https_url_and_valid_key(self):
        """Production mode accepts valid HTTPS URL with proper API key."""
        settings = BridgeSettings(
            BRIDGE_ENV="production",
            CLOUD_URL="https://waast360-api.example.com",
            BRIDGE_API_KEY="prod-valid-api-key-xyz",
        )
        assert settings.CLOUD_URL == "https://waast360-api.example.com"
        assert settings.BRIDGE_API_KEY == "prod-valid-api-key-xyz"
        assert settings.is_production
        assert not settings.is_development

    def test_prod_mode_properties(self):
        """Production mode properties are correctly set."""
        settings = BridgeSettings(
            BRIDGE_ENV="production",
            CLOUD_URL="https://waast360-api.example.com",
            BRIDGE_API_KEY="valid-key",
        )
        assert settings.is_production
        assert not settings.is_development


class TestCloudUrlValidation:
    """Tests for Cloud URL security validation."""

    def test_localhost_http_allowed_in_dev(self):
        """HTTP on localhost is allowed in development."""
        settings = BridgeSettings(
            BRIDGE_ENV="development",
            CLOUD_URL="http://localhost:8000",
        )
        assert settings.CLOUD_URL == "http://localhost:8000"

    def test_localhost_http_allowed_in_dev_127_0_0_1(self):
        """HTTP on 127.0.0.1 is allowed in development."""
        settings = BridgeSettings(
            BRIDGE_ENV="development",
            CLOUD_URL="http://127.0.0.1:8000",
        )
        assert settings.CLOUD_URL == "http://127.0.0.1:8000"

    def test_prod_https_required_for_non_localhost(self):
        """HTTPS is required for non-localhost URLs in production."""
        # This should fail
        with pytest.raises(ValidationError):
            BridgeSettings(
                BRIDGE_ENV="production",
                CLOUD_URL="http://waast360-prod.example.com",
            )

    def test_prod_https_accepted_for_remote_url(self):
        """HTTPS is accepted for remote URLs in production."""
        settings = BridgeSettings(
            BRIDGE_ENV="production",
            CLOUD_URL="https://waast360-prod.example.com",
            BRIDGE_API_KEY="valid-key",
        )
        assert settings.CLOUD_URL == "https://waast360-prod.example.com"

    def test_https_localhost_allowed_in_prod(self):
        """HTTPS on localhost is accepted in production."""
        settings = BridgeSettings(
            BRIDGE_ENV="production",
            CLOUD_URL="https://localhost:8443",
            BRIDGE_API_KEY="valid-key",
        )
        assert settings.CLOUD_URL == "https://localhost:8443"


class TestEnvironmentVariables:
    """Tests for environment variable configuration."""

    def test_config_loads_from_env_vars(self, monkeypatch):
        """Configuration loads from environment variables."""
        monkeypatch.setenv("BRIDGE_ENV", "production")
        monkeypatch.setenv("CLOUD_URL", "https://api.example.com")
        monkeypatch.setenv("BRIDGE_CLIENT_ID", "BR-TEST-01")
        monkeypatch.setenv("BRIDGE_API_KEY", "env-api-key")

        settings = BridgeSettings()
        assert settings.BRIDGE_ENV == "production"
        assert settings.CLOUD_URL == "https://api.example.com"
        assert settings.BRIDGE_CLIENT_ID == "BR-TEST-01"
        assert settings.BRIDGE_API_KEY == "env-api-key"

    def test_explicit_params_override_env_vars(self, monkeypatch):
        """Explicit parameters override environment variables."""
        monkeypatch.setenv("CLOUD_URL", "https://env-api.example.com")

        settings = BridgeSettings(CLOUD_URL="https://param-api.example.com")
        assert settings.CLOUD_URL == "https://param-api.example.com"

    def test_tally_host_port_configuration(self):
        """Tally host and port are configurable."""
        settings = BridgeSettings(
            TALLY_HOST="192.168.1.100",
            TALLY_PORT=9001,
        )
        assert settings.TALLY_HOST == "192.168.1.100"
        assert settings.TALLY_PORT == 9001


class TestDeploymentScenarios:
    """Integration tests for realistic deployment scenarios."""

    def test_developer_scenario(self):
        """Typical developer scenario: localhost HTTP, test credentials."""
        settings = BridgeSettings(
            BRIDGE_ENV="development",
            CLOUD_URL="http://127.0.0.1:8000",
            BRIDGE_CLIENT_ID="BR-LOCAL-01",
            BRIDGE_API_KEY="test-bridge-secret-key",
        )

        assert settings.is_development
        assert settings.CLOUD_URL == "http://127.0.0.1:8000"

    def test_client_production_scenario(self):
        """Typical client production scenario: remote HTTPS, prod credentials."""
        settings = BridgeSettings(
            BRIDGE_ENV="production",
            CLOUD_URL="https://waast360-api.mycorp.com",
            BRIDGE_CLIENT_ID="BR-ACME-01",
            BRIDGE_API_KEY="prod-secret-xyz123",
        )

        assert settings.is_production
        assert settings.CLOUD_URL.startswith("https://")
        assert settings.BRIDGE_API_KEY != "test-bridge-secret-key"

    def test_ci_cd_scenario(self):
        """CI/CD testing scenario: simulated adapter, dev mode."""
        settings = BridgeSettings(
            BRIDGE_ENV="development",
            BRIDGE_API_KEY="ci-test-key",
        )

        assert settings.is_development
        assert settings.CLOUD_URL == "http://127.0.0.1:8000"  # default


class TestConfigurationErrors:
    """Tests for helpful error messages."""

    def test_prod_missing_url_error_message(self):
        """Production mode provides helpful error for missing CLOUD_URL."""
        with pytest.raises(ValidationError) as exc_info:
            BridgeSettings(
                BRIDGE_ENV="production",
                CLOUD_URL="",
                BRIDGE_API_KEY="valid-key",
            )

        error_msg = str(exc_info.value)
        assert "required" in error_msg.lower() or "cannot be empty" in error_msg.lower()

    def test_prod_http_error_message(self):
        """Production mode provides helpful error for insecure HTTP."""
        with pytest.raises(ValidationError) as exc_info:
            BridgeSettings(
                BRIDGE_ENV="production",
                CLOUD_URL="http://api.example.com",
            )

        error_msg = str(exc_info.value)
        assert "https" in error_msg.lower()

    def test_prod_test_key_error_message(self):
        """Production mode provides helpful error for test API key."""
        with pytest.raises(ValidationError) as exc_info:
            BridgeSettings(
                BRIDGE_ENV="production",
                CLOUD_URL="https://api.example.com",
                BRIDGE_API_KEY="test-bridge-secret-key",
            )

        error_msg = str(exc_info.value)
        assert "test" in error_msg.lower() or "production" in error_msg.lower()
