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

    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_api_base: str = "https://graph.facebook.com/v20.0"
    whatsapp_verify_token: str = ""

    ses_sender: str = "wardwatch@example.org"

    default_tenant_id: str = "MDU-CORP"

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.whatsapp_token and self.whatsapp_phone_number_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
