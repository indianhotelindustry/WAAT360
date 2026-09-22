from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BridgeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    CLOUD_URL: str = Field(default="http://127.0.0.1:8000")
    BRIDGE_CLIENT_ID: str = Field(default="BR-LOCAL-01")
    BRIDGE_API_KEY: str = Field(default="test-bridge-secret-key")
    TALLY_HOST: str = Field(default="127.0.0.1")
    TALLY_PORT: int = Field(default=9000)
    POLL_INTERVAL_SECONDS: float = Field(default=5.0)
    HEARTBEAT_INTERVAL_SECONDS: float = Field(default=15.0)
    DB_PATH: str = Field(default="")
    PREFER_JSON: bool = Field(default=True)


bridge_settings = BridgeSettings()
