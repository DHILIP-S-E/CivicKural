"""Environment-driven settings for WardWatch."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aws_region: str = "ap-south-1"
    wardwatch_table: str = "wardwatch"
    wardwatch_bucket: str = "wardwatch-media-dev"

    bedrock_reasoning_model_id: str = "apac.amazon.nova-lite-v1:0"
    bedrock_vision_model_id: str = "apac.amazon.nova-lite-v1:0"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""

    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_api_base: str = "https://graph.facebook.com/v20.0"
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""

    ses_sender: str = "wardwatch@example.org"

    # SNS SMS reuses aws_region (no separate SNS region config — SNS is a
    # regional AWS service like SES/KMS/DynamoDB above). Leave sns_enabled
    # false to use the in-process FakeSns client.
    sns_enabled: bool = False

    default_tenant_id: str = "MDU-CORP"
    contact_kms_key_id: str = ""
    whatsapp_session_ttl_hours: int = 24

    jwt_expires_minutes: int = 720  # 12h
    enable_simulate_endpoint: bool = False

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.whatsapp_token and self.whatsapp_phone_number_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
