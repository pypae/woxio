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


class SyncConfig(BaseSettings):
    """Configuration for the invoice sync service."""

    model_config = SettingsConfigDict(env_prefix="BEXIO_")

    # Required for creating contacts and invoices
    owner_id: int = Field(
        description="Bexio owner ID for created records (contacts & invoices)",
        validation_alias=AliasChoices("BEXIO_OWNER_ID", "owner_id"),
    )

    # Invoice settings
    revenue_account_no: int = Field(
        description="Bexio account number for revenue (e.g., 3400 for sales revenue)",
        validation_alias=AliasChoices("BEXIO_INVOICE_ACCOUNT_NO", "revenue_account_no"),
    )
    bank_iban: str = Field(
        description="IBAN for invoice payments (used to look up bank_account_id)",
        validation_alias=AliasChoices("BEXIO_INVOICE_IBAN", "bank_iban"),
    )

    # Optional settings
    default_country_id: int | None = Field(
        default=1,  # 1 = Switzerland in Bexio
        description="Default Bexio country ID for new contacts",
        validation_alias=AliasChoices("BEXIO_DEFAULT_COUNTRY_ID", "default_country_id"),
    )


class Config(BaseSettings):
    """Application configuration."""

    wodify: WodifyConfig = Field(default_factory=WodifyConfig)
    bexio: BexioConfig = Field(default_factory=BexioConfig)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    poll_interval_minutes: int = Field(default=15, validation_alias="POLL_INTERVAL_MINUTES")
    poll_buffer_hours: int = Field(default=24, validation_alias="POLL_BUFFER_HOURS")

    @classmethod
    def from_env(cls) -> "Config":
        """Load all configuration from environment variables."""
        return cls()
