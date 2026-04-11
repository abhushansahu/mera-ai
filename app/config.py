"""Application configuration."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    openrouter_api_key: Optional[str] = Field(default=None)
    database_url: str = Field(...)
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    lmstudio_base_url: str = Field(default="http://localhost:1234/v1")
    lmstudio_api_key: Optional[str] = Field(default=None)
    cursor_agent_base_url: str = Field(default="http://localhost:11434/v1")
    cursor_agent_api_key: Optional[str] = Field(default=None)
    default_model: str = Field(default="openai/gpt-4o-mini")
    fallback_models: Optional[str] = Field(default=None, description="Comma-separated fallback OpenRouter models")

    chroma_host: Optional[str] = Field(default=None)
    chroma_port: int = Field(default=8000)
    chroma_collection_name: str = Field(default="memories")
    chroma_persist_dir: str = Field(default="./chroma_db")
    embedding_model: str = Field(default="text-embedding-3-small")
    embedding_base_url: Optional[str] = Field(default=None)
    embedding_api_key: Optional[str] = Field(default=None)

    langsmith_api_key: Optional[str] = Field(default=None)
    langsmith_project: str = Field(default="mera-ai")
    langsmith_api_url: str = Field(default="https://api.smith.langchain.com")
    langsmith_tracing_v2: bool = Field(default=True)

    obsidian_rest_url: str = Field(default="http://localhost:27124")
    obsidian_rest_token: Optional[str] = Field(default=None)
    obsidian_vault_path: Optional[str] = Field(default=None)
    obsidian_plugin_shared_secret: Optional[str] = Field(default=None)
    sidecar_grpc_bind: str = Field(default="127.0.0.1:50051")
    
    cors_origins: Optional[str] = Field(default=None, description="Comma-separated list of allowed CORS origins. Use '*' for all origins (development only).")
    secure_settings_enabled: bool = Field(default=True)
    secret_encryption_key: str = Field(default="dev-only-change-me")
    allow_insecure_secret_key: bool = Field(default=False)
    auth_required: bool = Field(default=False)
    auth_tokens: Optional[str] = Field(
        default=None,
        description="Comma separated user:token pairs for bearer auth. Example: alice:token1,bob:token2",
    )
    internal_service_key: Optional[str] = Field(default=None)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
