from pathlib import Path
from typing import Any

from pydantic import DirectoryPath, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.constants import Environment


class CustomBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Config(CustomBaseSettings):
    DEBUG: bool = False

    DATABASE_URL: PostgresDsn
    DATABASE_ASYNC_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 16
    DATABASE_POOL_TTL: int = 60 * 20  # 20 minutes
    DATABASE_POOL_PRE_PING: bool = True

    BASE_DIR: DirectoryPath = Path(__file__).resolve().parent.parent
    TEMPLATES_DIR: DirectoryPath = BASE_DIR / "src" / "templates"

    BANK_PAYMENT_WITHDRAW_CHARGE: int
    MOBILE_BANKING_WITHDRAW_CHARGE: int
    VAT_PERCENTAGE: int

    ENVIRONMENT: Environment = Environment.PRODUCTION

    SENTRY_DSN: str | None = None

    CORS_ORIGINS: list[str] = ["*"]
    CORS_ORIGINS_REGEX: str | None = None
    CORS_HEADERS: list[str] = ["*"]

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    OTP_EXPIRE_MINUTES: int
    OTP_RETRY_DELAY_MINUTES: int
    OTP_RETRY_LIMIT: int

    GOOGLE_CLIENT_IDS: list[str]

    # Email Configuration
    MAIL_SERVER: str
    MAIL_PORT: int
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_SENDER: str
    MAIL_USE_TLS: bool

    # S3 Configuration
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    AWS_CLOUDFRONT_S3_URL: str
    MEDIA_PUBLIC_BUCKET: str
    MEDIA_PRIVATE_BUCKET: str

    # Banglalink SMS
    BL_BASE_DIR: str
    BL_USERNAME: str
    BL_PASSWORD: str
    BILL_MSISDN: str

    # SSL Commerce
    SSLCOMMERZ_IS_SANDBOX: bool
    SSLCOMMERZ_STORE_ID: str
    SSLCOMMERZ_STORE_PASS: str
    SSLCOMMERZ_PAYMENT_CALLBACK_URL: str

    # Google Analytics
    GOOGLE_ANALYTICS_MEASUREMENT_ID: str
    GOOGLE_ANALYTICS_API_SECRET: str

    # Meta
    META_PIXEL_ID: str
    META_PIXEL_ACCESS_TOKEN: str

    APP_VERSION: str = "0.1"

    @model_validator(mode="after")
    def validate_sentry_non_local(self) -> "Config":
        if self.ENVIRONMENT.is_deployed and not self.SENTRY_DSN:
            raise ValueError("Sentry is not set")

        return self


settings = Config()

app_configs: dict[str, Any] = {"title": "App API"}
if settings.ENVIRONMENT.is_deployed:
    app_configs["root_path"] = f"/v{settings.APP_VERSION}"

if not settings.ENVIRONMENT.is_debug:
    app_configs["openapi_url"] = None  # hide docs
