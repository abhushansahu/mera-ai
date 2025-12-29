"""Application configuration."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    openrouter_api_key: str = Field(...)
    database_url: str = Field(...)
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    default_model: str = Field(default="openai/gpt-4o-mini")

    chroma_host: Optional[str] = Field(default=None)
    chroma_port: int = Field(default=8000)
    chroma_collection_name: str = Field(default="memories")
    chroma_persist_dir: str = Field(default="./chroma_db")

    langsmith_api_key: Optional[str] = Field(default=None)
    langsmith_project: str = Field(default="mera-ai")
    langsmith_api_url: str = Field(default="https://api.smith.langchain.com")
    langsmith_tracing_v2: bool = Field(default=True)

    obsidian_rest_url: str = Field(default="http://localhost:27124")
    obsidian_rest_token: Optional[str] = Field(default=None)
    obsidian_vault_path: Optional[str] = Field(default=None)
    
    cors_origins: Optional[str] = Field(default=None, description="Comma-separated list of allowed CORS origins. Use '*' for all origins (development only).")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
