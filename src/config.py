from typing import Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PathaoConfig(BaseSettings):
    """Configuration for Pathao Logistics SDK"""

    # Authentication credentials
    pathao_client_id: str = Field(..., description="Pathao API client ID")
    pathao_client_secret: str = Field(..., description="Pathao API client secret")
    pathao_username: str = Field(..., description="Pathao merchant username")
    pathao_password: str = Field(..., description="Pathao merchant password")

    # OAuth grant type
    pathao_grant_type: str = Field(default="password", description="OAuth2 grant type")

    # API configuration
    pathao_base_url: Optional[str] = Field(
        default=None,
        description="Pathao API base URL (auto-set based on environment if not provided)",
    )
    pathao_environment: str = Field(
        default="production", description="Environment: sandbox or production"
    )

    # Request settings
    pathao_timeout: float = Field(
        default=30.0, description="Request timeout in seconds"
    )
    pathao_max_retries: int = Field(
        default=3, description="Maximum number of retries for failed requests"
    )

    # Webhook configuration
    pathao_webhook_secret: Optional[str] = Field(
        default=None, description="Secret key for webhook signature verification"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="PATHAO_",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("pathao_environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value"""
        allowed = ["sandbox", "production"]
        if v.lower() not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v.lower()

    @model_validator(mode="after")
    def set_base_url_if_needed(self) -> "PathaoConfig":
        """Auto-set base URL based on environment if not explicitly provided"""
        if self.pathao_base_url is None:
            if self.pathao_environment == "sandbox":
                self.pathao_base_url = "https://courier-api-sandbox.pathao.com"
            else:
                self.pathao_base_url = "https://api-hermes.pathao.com"
        return self

    def get_auth_url(self) -> str:
        """Get authentication endpoint URL"""
        return f"{self.pathao_base_url}/aladdin/api/v1/issue-token"

    def is_production(self) -> bool:
        """Check if running in production"""
        return self.pathao_environment == "production"

    def is_sandbox(self) -> bool:
        """Check if running in sandbox"""
        return self.pathao_environment == "sandbox"


_config_instance: Optional[PathaoConfig] = None


def get_config() -> PathaoConfig:
    """Get or create config instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = PathaoConfig()
    return _config_instance
