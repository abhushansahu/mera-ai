#!/usr/bin/env python3
"""Simple Mem0 API server for self-hosted deployment.

This script runs Mem0 as a local API server that can be accessed via HTTP.
Run this script to start a self-hosted Mem0 instance.

Usage:
    python scripts/start_mem0_server.py

Or with custom settings:
    MEM0_HOST=0.0.0.0 MEM0_PORT=8001 python scripts/start_mem0_server.py
"""

import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from mem0 import Memory

app = FastAPI(title="Mem0 Self-Hosted API", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Mem0 Memory instance
# Configure to use OpenRouter instead of OpenAI
def get_mem0_config():
    """Get Mem0 configuration, preferring OpenRouter over OpenAI."""
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    
    # If OpenRouter is available, use it; otherwise fall back to OpenAI
    if openrouter_api_key:
        # Mem0 uses OpenAI client internally. We configure it to use OpenRouter
        # by setting the base_url and using OpenRouter's API key.
        # Mem0's OpenAI client will pick up OPENAI_API_KEY and OPENAI_BASE_URL env vars
        # So we set them to OpenRouter values temporarily
        original_openai_key = os.environ.get("OPENAI_API_KEY")
        original_openai_base = os.environ.get("OPENAI_BASE_URL")
        
        # Temporarily set OpenAI env vars to OpenRouter values
        os.environ["OPENAI_API_KEY"] = openrouter_api_key
        os.environ["OPENAI_BASE_URL"] = openrouter_base_url
        
        # Also try explicit config
        config = {
            "embedding_model": {
                "provider": "openai",
                "config": {
                    "api_key": openrouter_api_key,
                    "base_url": openrouter_base_url,
                    "model": "text-embedding-3-small"
                }
            }
        }
        return config
    else:
        # Fall back to OpenAI if OpenRouter not configured
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            return {
                "embedding_model": {
                    "provider": "openai",
                    "config": {
                        "api_key": openai_api_key
                    }
                }
            }
        return None

try:
    config = get_mem0_config()
    if config:
        try:
            mem0_instance = Memory.from_config(config_dict=config)
            print("✓ Mem0 initialized with OpenRouter configuration")
        except Exception as config_error:
            print(f"Warning: Could not initialize with explicit config: {config_error}")
            print("Falling back to environment variable configuration...")
            # Fall back to using env vars (which we set above)
            mem0_instance = Memory()
    else:
        # Try to initialize with default settings
        mem0_instance = Memory()
except Exception as e:
    print(f"Warning: Could not initialize Mem0: {e}")
    print("Note: Mem0 requires either OPENROUTER_API_KEY or OPENAI_API_KEY for embeddings.")
    print("Set one of these environment variables to use Mem0.")
    raise


class AddMemoryRequest(BaseModel):
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    messages: str | list[dict[str, str]]  # Can be a string or list of message dicts
    metadata: Optional[dict] = None
    infer: bool = True


class SearchMemoryRequest(BaseModel):
    user_id: str
    query: str
    limit: int = 5


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mem0"}


@app.post("/add")
def add_memory(request: AddMemoryRequest):
    """Add a memory to Mem0."""
    try:
        # Mem0 requires at least one of user_id, agent_id, or run_id
        if not (request.user_id or request.agent_id or request.run_id):
            raise HTTPException(
                status_code=400,
                detail="At least one of user_id, agent_id, or run_id is required"
            )
        
        mem0_instance.add(
            messages=request.messages,
            user_id=request.user_id,
            agent_id=request.agent_id,
            run_id=request.run_id,
            metadata=request.metadata,
            infer=request.infer,
        )
        return {"status": "success", "message": "Memory added"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
def search_memories(request: SearchMemoryRequest):
    """Search memories in Mem0."""
    try:
        results = mem0_instance.search(
            user_id=request.user_id,
            query=request.query,
            limit=request.limit,
        )
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get_all/{user_id}")
def get_all_memories(user_id: str, limit: int = 100):
    """Get all memories for a user."""
    try:
        results = mem0_instance.get_all(user_id=user_id, limit=limit)
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/delete/{user_id}")
def delete_memories(user_id: str):
    """Delete all memories for a user."""
    try:
        mem0_instance.delete(user_id=user_id)
        return {"status": "success", "message": f"All memories deleted for user {user_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("MEM0_HOST", "0.0.0.0")
    port = int(os.getenv("MEM0_PORT", "8001"))

    print(f"Starting Mem0 self-hosted server on {host}:{port}")
    print(f"API documentation available at http://{host}:{port}/docs")
    print(f"Health check: http://{host}:{port}/health")

    uvicorn.run(app, host=host, port=port)

