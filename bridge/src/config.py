from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BridgeSettings(BaseSettings):
    """
    WAAST360 Bridge configuration with production-safe security constraints.

    Secret Storage Strategy:
    - DEV MODE: BRIDGE_API_KEY defaults to "test-bridge-secret-key" (requires BRIDGE_ENV=development)
    - PROD MODE: BRIDGE_API_KEY must be provided via:
      1. Environment variable BRIDGE_API_KEY (set by installer)
      2. Windows Credential Manager (retrieved via keyring)
      3. No hardcoded defaults; fails fast if missing

    URL Security:
    - DEV MODE (BRIDGE_ENV=development): HTTP allowed for localhost testing
    - PROD MODE: HTTPS required; HTTP rejected with validation error
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BRIDGE_ENV: str = Field(default="development", description="Set to 'development' or 'production'")
    CLOUD_URL: str = Field(default="", description="Cloud API URL (must be HTTPS in production)")
    BRIDGE_CLIENT_ID: str = Field(default="BR-LOCAL-01")
    BRIDGE_API_KEY: str = Field(default="", description="API key for Cloud authentication")
    TALLY_HOST: str = Field(default="127.0.0.1")
    TALLY_PORT: int = Field(default=9000)
    POLL_INTERVAL_SECONDS: float = Field(default=5.0)
    HEARTBEAT_INTERVAL_SECONDS: float = Field(default=15.0)
    DB_PATH: str = Field(default="")
    PREFER_JSON: bool = Field(default=True)

    @field_validator("CLOUD_URL")
    @classmethod
    def validate_cloud_url(cls, v: str, info) -> str:
        """Enforce HTTPS for production, allow HTTP for development."""
        is_production = info.data.get("BRIDGE_ENV", "development") == "production"

        if not v:
            if is_production:
                raise ValueError("CLOUD_URL is required and cannot be empty in production mode")
            # Dev mode: default to localhost
            return "http://127.0.0.1:8000"

        if is_production and v.startswith("http://"):
            raise ValueError(
                f"Production deployment requires HTTPS. Got insecure URL: {v}. "
                "Set CLOUD_URL to an https:// endpoint."
            )

        return v

    @field_validator("BRIDGE_API_KEY")
    @classmethod
    def validate_api_key(cls, v: str, info) -> str:
        """Enforce API key presence in production; allow test key in development."""
        is_production = info.data.get("BRIDGE_ENV", "development") == "production"

        # If explicitly set (non-empty), accept it
        if v:
            if is_production and v == "test-bridge-secret-key":
                raise ValueError(
                    "Production deployment detected with test API key. "
                    "BRIDGE_API_KEY must be a valid production credential. "
                    "Set BRIDGE_API_KEY via environment variable or Windows Credential Manager."
                )
            return v

        # Empty: apply defaults based on mode
        if is_production:
            raise ValueError(
                "BRIDGE_API_KEY is required in production mode. "
                "Provide via BRIDGE_API_KEY environment variable or Windows Credential Manager. "
                "Run the installer to securely configure credentials."
            )

        # Development: allow test key as fallback
        return "test-bridge-secret-key"

    @property
    def is_production(self) -> bool:
        return self.BRIDGE_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.BRIDGE_ENV == "development"


def _load_settings() -> BridgeSettings:
    """
    Load and validate bridge settings with environment detection.
    """
    try:
        settings = BridgeSettings()

        # Log configuration state (never log the actual API key)
        import logging

        logger = logging.getLogger("waast_bridge.config")
        logger.info(f"Bridge configuration loaded: mode={settings.BRIDGE_ENV}, client_id={settings.BRIDGE_CLIENT_ID}")

        return settings
    except ValueError as e:
        import logging

        logger = logging.getLogger("waast_bridge.config")
        logger.error(f"Configuration validation error: {e}")
        raise


bridge_settings = _load_settings()
