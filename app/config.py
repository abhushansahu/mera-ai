import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Typed application configuration loaded from environment variables.

    Required environment variables:
    - OPENROUTER_API_KEY: API key for OpenRouter LLM service
    - DATABASE_URL: PostgreSQL database connection string

    Optional environment variables:
    - OPENROUTER_BASE_URL: Base URL for OpenRouter (default: https://openrouter.ai/api/v1)
    - DEFAULT_MODEL: Default LLM model to use (default: openai/gpt-4o-mini)
    - MEM0_API_KEY: API key for Mem0 memory service (required if using external Mem0)
    - MEM0_HOST: Mem0 host URL for self-hosted instance (default: None, uses external if not set)
    - CHROMA_HOST: Chroma server host (for client-server mode, optional)
    - CHROMA_PORT: Chroma server port (default: 8000, optional)
    - CHROMA_COLLECTION_NAME: Chroma collection name (default: memories)
    - CHROMA_PERSIST_DIR: Directory to persist Chroma data in embedded mode (default: ./chroma_db)
    - USE_CHROMA: Set to "true" to use Chroma instead of Mem0 (default: false)
    - LANGFUSE_PUBLIC_KEY: Langfuse public key for observability
    - LANGFUSE_SECRET_KEY: Langfuse secret key for observability
    - LANGFUSE_HOST: Langfuse host URL (default: http://localhost:3000 for self-hosted)
    - OBSIDIAN_REST_URL: Obsidian REST API URL (default: http://localhost:27124)
    - OBSIDIAN_REST_TOKEN: Obsidian REST API token
    """

    openrouter_api_key: str
    openrouter_base_url: str
    default_model: str

    database_url: str

    mem0_api_key: Optional[str] = None
    mem0_host: Optional[str] = None

    chroma_host: Optional[str] = None
    chroma_port: int = 8000
    chroma_collection_name: str = "memories"
    chroma_persist_dir: str = "./chroma_db"
    use_chroma: bool = False
    use_langchain_orchestrator: bool = False

    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: Optional[str] = None

    obsidian_rest_url: Optional[str] = None
    obsidian_rest_token: Optional[str] = None


def load_settings() -> Settings:
    """Load settings from environment variables.

    Raises ValueError if required API keys are missing.
    """
    # Required API keys - fail fast if missing
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        raise ValueError(
            "OPENROUTER_API_KEY is required but not set. "
            "Please set it in your environment variables or .env file."
        )

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "DATABASE_URL is required but not set. "
            "Please set it in your environment variables or .env file. "
            "Example: postgresql+psycopg2://user:password@localhost:5432/dbname"
        )

    # Mem0 configuration: either self-hosted (MEM0_HOST) or external (MEM0_API_KEY)
    # Only required if not using Chroma
    use_chroma = os.getenv("USE_CHROMA", "false").lower() == "true"
    
    mem0_host = os.getenv("MEM0_HOST")
    mem0_api_key = os.getenv("MEM0_API_KEY")
    
    # For self-hosted Mem0, API key is optional (can use a placeholder)
    # For external Mem0, API key is required
    # Only validate if not using Chroma
    if not use_chroma:
        if not mem0_host and not mem0_api_key:
            raise ValueError(
                "Either MEM0_HOST (for self-hosted) or MEM0_API_KEY (for external) is required. "
                "Or set USE_CHROMA=true to use Chroma instead. "
                "Please set one in your environment variables or .env file."
            )
        
        # If using self-hosted but no API key provided, use a default placeholder
        # The self-hosted Mem0 server doesn't actually validate this key
        if mem0_host and not mem0_api_key:
            mem0_api_key = "self-hosted-mem0-no-key-required"

    # Chroma configuration (optional)
    chroma_host = os.getenv("CHROMA_HOST")
    chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
    chroma_collection_name = os.getenv("CHROMA_COLLECTION_NAME", "memories")
    chroma_persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    
    # Orchestrator selection (optional)
    use_langchain_orchestrator = os.getenv("USE_LANGCHAIN_ORCHESTRATOR", "false").lower() == "true"

    # Langfuse host defaults to localhost if not specified (self-hosted)
    langfuse_host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

    return Settings(
        openrouter_api_key=openrouter_api_key,
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ),
        default_model=os.getenv("DEFAULT_MODEL", "openai/gpt-4o-mini"),
        database_url=database_url,
        mem0_api_key=mem0_api_key,
        mem0_host=mem0_host,
        chroma_host=chroma_host,
        chroma_port=chroma_port,
        chroma_collection_name=chroma_collection_name,
        chroma_persist_dir=chroma_persist_dir,
        use_chroma=use_chroma,
        use_langchain_orchestrator=use_langchain_orchestrator,
        langfuse_public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        langfuse_secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        langfuse_host=langfuse_host,
        obsidian_rest_url=os.getenv("OBSIDIAN_REST_URL", "http://localhost:27124"),
        obsidian_rest_token=os.getenv("OBSIDIAN_REST_TOKEN"),
    )


settings = load_settings()


