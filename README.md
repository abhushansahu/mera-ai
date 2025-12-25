## Unified AI Assistant – Implementation Workspace

This repo contains a self-hosted unified AI assistant that:

- Uses **OpenRouter** (and optionally local models) behind a single interface
- Adds **persistent memory** via **Mem0** and an **Obsidian** vault
- Orchestrates interactions through **LangGraph** with a **Research → Plan → Implement** workflow
- Adds **observability** via **Langfuse**

## Setup

This project uses **self-hosted services** for everything except OpenRouter and Obsidian. All services (PostgreSQL, Mem0, Langfuse) run locally via Docker Compose.

### Prerequisites

- Docker and Docker Compose installed
- Python 3.8+ 
- OpenRouter API key (external service)
- Obsidian installed locally (optional)

### Quick Start

**Recommended: Use the unified startup script** (checks ports, starts everything):
```bash
# Using Python script directly
python scripts/start_all_services.py

# Or using convenience shell wrapper
./start.sh
```

This single command will:
- Check for port conflicts (5432, 5433, 3000, 8001)
- Start PostgreSQL (port 5432)
- Start Langfuse DB (port 5433) and Langfuse UI (port 3000)
- Start Mem0 API server (port 8001)
- Wait for all services to be ready
- Show service status and access URLs

**To stop all services:**
```bash
# Using Python script directly
python scripts/stop_all_services.py

# Or using convenience shell wrapper
./stop.sh
```

**Alternative: Manual startup** (if you prefer to start services separately):

1. **Start Docker services** (PostgreSQL, Langfuse):
   ```bash
   docker-compose up -d
   ```

2. **Start Mem0 server** (in a separate terminal):
   ```bash
   python scripts/start_mem0_server.py
   ```

3. **Set up Langfuse** (first time only):
   - Open http://localhost:3000 in your browser
   - Create an account
   - Go to Settings → API Keys
   - Copy your `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`

4. **Copy the example environment file** and fill in your configuration:
   ```bash
   cp env.example .env
   # Then edit .env with your actual values
   ```
   
   Required values in `.env`:
   ```bash
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   DATABASE_URL=postgresql+psycopg2://ai_user:ai_password@localhost:5432/ai_assistant
   MEM0_HOST=http://localhost:8001
   MEM0_API_KEY=local_mem0_api_key_change_in_production
   LANGFUSE_HOST=http://localhost:3000
   LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
   LANGFUSE_SECRET_KEY=your_langfuse_secret_key
   ```

5. **Create and activate virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

6. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

7. **Start the server**:
   ```bash
   python -m app.main
   ```

8. **Check server status**:
   ```bash
   curl http://localhost:8000/status
   ```

### Required Environment Variables

**⚠️ The server will NOT start without these:**

1. **OPENROUTER_API_KEY** - Your OpenRouter API key for LLM access (external service)
   - Get one at: https://openrouter.ai/
   
2. **DATABASE_URL** - PostgreSQL database connection string (self-hosted)
   - Default from docker-compose: `postgresql+psycopg2://ai_user:ai_password@localhost:5432/ai_assistant`

3. **MEM0_HOST** and **MEM0_API_KEY** - Self-hosted Mem0 instance
   - Default: `MEM0_HOST=http://localhost:8001`
   - Default API key: `local_mem0_api_key_change_in_production` (change in production!)

### Optional Environment Variables

- `OPENROUTER_BASE_URL` - Default: `https://openrouter.ai/api/v1`
- `DEFAULT_MODEL` - Default: `openai/gpt-4o-mini`
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` - For observability (self-hosted)
  - Default: `LANGFUSE_HOST=http://localhost:3000`
- `OBSIDIAN_REST_URL` - Default: `http://localhost:27124`
- `OBSIDIAN_REST_TOKEN` - For Obsidian integration

### Managing Self-Hosted Services

**Start all services** (recommended):
```bash
# Option 1: Python script
python scripts/start_all_services.py

# Option 2: Shell wrapper (convenience)
./start.sh
```

**Stop all services:**
```bash
# Option 1: Python script
python scripts/stop_all_services.py

# Option 2: Shell wrapper (convenience)
./stop.sh
```

**Manual Docker management:**
```bash
# Start Docker services only
docker-compose up -d

# Stop Docker services only
docker-compose down

# View logs
docker-compose logs -f

# Restart a specific service
docker-compose restart langfuse
```

**Port Configuration:**
The following ports are used (configured in `scripts/start_all_services.py`):
- `5432` - PostgreSQL
- `5433` - Langfuse Database
- `3000` - Langfuse UI
- `8001` - Mem0 API Server

**Access services:**
- Langfuse UI: http://localhost:3000
- Mem0 API: http://localhost:8001
- Mem0 API Docs: http://localhost:8001/docs
- PostgreSQL: `localhost:5432`

**Note:** 
- Mem0 server runs as a Python process (not in Docker) because it doesn't have an official Docker image
- The unified startup script (`start_all_services.py`) checks for port conflicts before starting services
- All services can be managed together using the unified scripts

6. Access API documentation:
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

### Status Endpoint

The `/status` endpoint shows which API keys are configured and the health of required services. The server will fail to start if any required keys are missing.

This file is intentionally minimal; see `docs/ARCHITECTURE.md` and `docs/QUICKSTART.md` (to be added as the implementation progresses) for deeper details.


