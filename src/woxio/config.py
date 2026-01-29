"""Configuration from environment variables."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WodifyConfig(BaseSettings):
    """Wodify API configuration."""

    model_config = SettingsConfigDict(env_prefix="WODIFY_")

    api_key: str = Field(validation_alias=AliasChoices("WODIFY_API_KEY", "api_key"))
    base_url: str = Field(
        default="https://api.wodify.com/v1",
        validation_alias=AliasChoices("WODIFY_API_URL", "base_url"),
    )


class BexioConfig(BaseSettings):
    """Bexio API configuration."""

    model_config = SettingsConfigDict(env_prefix="BEXIO_")

    api_token: str = Field(validation_alias=AliasChoices("BEXIO_API_TOKEN", "api_token"))
    base_url: str = Field(
        default="https://api.bexio.com",
        validation_alias=AliasChoices("BEXIO_API_URL", "base_url"),
    )


class Config(BaseSettings):
    """Application configuration."""

    wodify: WodifyConfig = Field(default_factory=WodifyConfig)
    bexio: BexioConfig = Field(default_factory=BexioConfig)
    poll_interval_minutes: int = Field(default=15, validation_alias="POLL_INTERVAL_MINUTES")
    poll_buffer_hours: int = Field(default=24, validation_alias="POLL_BUFFER_HOURS")

    @classmethod
    def from_env(cls) -> "Config":
        """Load all configuration from environment variables."""
        return cls()
