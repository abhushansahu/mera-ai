# Mera AI - Unified AI Assistant with Spaces

A self-hosted AI assistant that provides a single interface to chat with multiple AI models, with persistent memory, knowledge base integration, and **multi-project isolation via Spaces**.

## What It Does

- **Unified Interface**: Chat with any AI model through OpenRouter (GPT-4, Claude, and 280+ others)
- **Persistent Memory**: Remembers conversations using Chroma vector database
- **Knowledge Base**: Integrates with Obsidian vault via REST API
- **Spaces System**: Multi-project isolation with separate memory, vaults, and token budgets
- **Observability**: Track usage, costs, and performance with LangSmith (optional)
- **CrewAI Orchestration**: Uses CrewAI multi-agent framework for Research → Plan → Implement workflow
- **Self-Hosted**: Everything runs locally except the AI model API calls

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenRouter API key ([get one here](https://openrouter.ai/))

### Setup

#### 1. Setup Environment

```bash
# Copy environment file
cp env.example .env

# Edit .env and add your OpenRouter API key
# OPENROUTER_API_KEY=your_key_here
```

#### 2. Configure LangSmith (Optional)

1. Sign up at https://smith.langchain.com/
2. Create an API key in your dashboard
3. Add to `.env`:
   ```
   LANGSMITH_API_KEY=your_key_here
   LANGSMITH_PROJECT=mera-ai
   ```

#### 3. Start Everything

**Option A: Using the convenience script (Recommended)**

```bash
# Single command to start everything
./start.sh
```

**Option B: Using docker-compose directly**

```bash
# Build and start all services (PostgreSQL + Application)
docker-compose up -d

# View logs
docker-compose logs -f app

# Check status
docker-compose ps
```

This starts:
- PostgreSQL (database)
- Mera AI Application (with all dependencies)

The API will be available at http://localhost:8000

#### 4. Stop Services

```bash
# Using the convenience script
./stop.sh

# Or using docker-compose directly
docker-compose down
```

## Usage

### Chat with AI

**Basic chat (without Spaces):**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "query": "Hello, remember my name is Alice"
  }'
```

**Chat with Spaces (recommended for multi-project work):**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "query": "How does authentication work in our system?",
    "space_id": "harmonychain"
  }'
```

### Check Status

```bash
curl http://localhost:8000/status
```

### API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Spaces System

Spaces enable **complete isolation** between different projects, allowing you to run multiple projects simultaneously without data leakage.

### What Spaces Provide

- **Isolated Memory**: Each space has its own Chroma collection
- **Isolated Knowledge Base**: Each space has its own Obsidian vault
- **Isolated Database**: Each space has its own PostgreSQL schema
- **Token Budget Tracking**: Track costs per project with monthly budgets
- **Team Collaboration**: Multiple users can work on different spaces
- **Instant Context Switching**: Switch between projects instantly

### Creating a Space

```bash
curl -X POST http://localhost:8000/spaces/create \
  -H "Content-Type: application/json" \
  -d '{
    "space_id": "harmonychain",
    "name": "HarmonyChain Project",
    "owner_id": "alice",
    "monthly_token_budget": 500000,
    "preferred_model": "openai/gpt-4o-mini"
  }'
```

### Listing Your Spaces

```bash
curl "http://localhost:8000/spaces/list?owner_id=alice"
```

### Switching Spaces

```bash
curl -X POST http://localhost:8000/spaces/switch?space_id=harmonychain
```

### Checking Space Usage

```bash
curl "http://localhost:8000/spaces/harmonychain/usage"
```

### Space Management Endpoints

- `POST /spaces/create` - Create a new space
- `GET /spaces/list?owner_id={owner_id}` - List all spaces for an owner
- `POST /spaces/switch?space_id={space_id}` - Switch active space
- `GET /spaces/current` - Get current space
- `GET /spaces/{space_id}/usage` - Get space usage for current month
- `DELETE /spaces/{space_id}?permanently=false` - Archive or delete space

### Spaces Architecture

```
User Query + SpaceID
    ↓
SpaceManager validates & loads space
    ↓
Research-Plan-Implement (within space)
    ├─ Access space-specific Chroma collection
    ├─ Access space-specific Obsidian vault
    ├─ Access space-specific PostgreSQL schema
    └─ Respects space token budget
    ↓
Isolated Results (saved to space)
```

### Benefits of Spaces

| Feature | Without Spaces | With Spaces |
|---------|----------------|------------|
| **Project Isolation** | ❌ All mixed | ✅ Completely separate |
| **Memory Leakage** | ❌ Possible | ✅ Impossible |
| **Cost Tracking** | ❌ Combined | ✅ Per-space |
| **Team Collaboration** | ❌ Hard | ✅ Built-in |
| **Multi-Project** | ❌ Difficult | ✅ Easy |
| **Context Switching** | ❌ Slow | ✅ Instant |
| **Data Privacy** | ❌ Shared | ✅ Isolated |

## Architecture

### CrewAI Orchestration

The system uses CrewAI multi-agent framework to implement a Research → Plan → Implement (RPI) workflow:

- **Research Phase**: CrewAI Researcher Agent with tools (Chroma memory, Obsidian vault, file explorer, link crawler, data analyzer)
- **Plan Phase**: CrewAI Planner Agent that creates structured implementation plans
- **Implement Phase**: CrewAI Implementer Agent that executes the plan step-by-step

### Multi-Agent System

The research phase uses specialized sub-agents that work in parallel:

- **FileExplorer**: Reads and analyzes code files
- **LinkCrawler**: Fetches and processes web documentation
- **DataAnalyzer**: Queries database schemas
- **MemoryRetriever**: Searches relevant memories
- **Synthesizer**: Combines all findings into coherent research

### Observability with LangSmith

All operations are traced using LangSmith (optional) for:
- Request/response tracking
- Token usage and cost monitoring
- Performance metrics
- Debugging and optimization

### Obsidian Integration

Obsidian vault is accessed via REST API:
- Direct vault search via Obsidian Local REST API plugin
- No indexing required - real-time search
- Space-specific vault support

## Key Features

### Memory Management

The assistant remembers past conversations and uses that context in future interactions.

```bash
# Add a memory
curl -X POST http://localhost:8000/mem0/add \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "messages": "I love Python programming"
  }'

# Search memories
curl -X POST http://localhost:8000/mem0/search \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "query": "What do I like?"
  }'
```

**Note**: When using Spaces, memories are automatically isolated per space.

### Obsidian Integration

Connect your Obsidian vault to provide context from your notes via REST API.

**Setup:**

1. Install the [Local REST API plugin](https://github.com/coddingtonbear/obsidian-local-rest-api) in Obsidian
2. Enable the plugin and note the port (default: 27124)
3. Configure in `.env`:
   ```
   OBSIDIAN_REST_URL=http://localhost:27124
   OBSIDIAN_REST_TOKEN=your_token_here  # Optional, if plugin requires auth
   ```
4. The system will automatically use the vault for retrieval

**Note**: Spaces can have their own vault paths configured.

### Multi-Model Support

Switch between different AI models:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "query": "Explain quantum computing",
    "model": "openai/gpt-4o-mini"
  }'
```

## Environment Variables

**Required:**
- `OPENROUTER_API_KEY` - Your OpenRouter API key
- `DATABASE_URL` - PostgreSQL connection (default: `postgresql+psycopg2://ai_user:ai_password@localhost:5432/ai_assistant`)

**Optional:**
- `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` - For observability
- `OBSIDIAN_REST_URL` / `OBSIDIAN_REST_TOKEN` - For Obsidian integration
- `CHROMA_PERSIST_DIR` - Memory storage location (default: `./chroma_db`)
- `CHROMA_HOST` / `CHROMA_PORT` - For client-server Chroma mode
- `CORS_ORIGINS` - CORS allowed origins (default: `*` for development)

See `env.example` for complete configuration options.

## Managing Services

**Using convenience scripts:**

```bash
# Start all services (PostgreSQL + Application)
./start.sh

# Stop all services
./stop.sh
```

**Using docker-compose directly:**

```bash
# Start all services (PostgreSQL + Application)
docker-compose up -d

# Stop all services
docker-compose down

# View logs (all services)
docker-compose logs -f

# View logs (specific service)
docker-compose logs -f app
docker-compose logs -f postgres

# Check service status
docker-compose ps

# Restart a specific service
docker-compose restart app

# Rebuild and restart (after code changes)
docker-compose up -d --build app
```

## Troubleshooting

### Services Not Starting

```bash
# Check if ports are in use
lsof -i :8000
lsof -i :5432

# Check Docker containers
docker-compose ps
docker-compose logs
```

### Database Connection Issues

```bash
# Verify PostgreSQL is running
docker-compose ps postgres

# Test connection
docker exec -it mera-ai-postgres psql -U ai_user -d ai_assistant -c "SELECT 1;"
```

### API Not Responding

1. Check the application container is running: `docker-compose ps app`
2. View application logs: `docker-compose logs app`
3. Verify environment variables in `.env`
4. Ensure all Docker services are healthy: `docker-compose ps`
5. Restart the application: `docker-compose restart app`
6. Rebuild if needed: `docker-compose up -d --build app`

### Spaces Issues

1. Verify space exists: `curl "http://localhost:8000/spaces/list?owner_id=your_id"`
2. Check space usage: `curl "http://localhost:8000/spaces/{space_id}/usage"`
3. Verify database schema was created for the space
4. Check application logs for space-related errors

## Project Structure

```
mera-ai/
├── app/                    # Main application code
│   ├── adapters/          # External service adapters (Chroma, OpenRouter, Obsidian)
│   ├── api.py             # FastAPI routes
│   ├── config.py          # Configuration management
│   ├── core.py            # Core types and protocols
│   ├── crewai.py          # CrewAI agents, tools, and tasks
│   ├── db.py              # Database setup
│   ├── main.py            # Application entry point
│   ├── models.py          # SQLAlchemy models
│   ├── multi_agent_context_system.py  # Multi-agent coordinator
│   ├── observability.py   # LangSmith tracing (optional)
│   ├── orchestrator.py   # CrewAI orchestrator (RPI workflow)
│   └── spaces.py          # Spaces system (isolation, budgets, management)
├── scripts/               # Utility scripts
├── tests/                 # Test files
└── docker-compose.yml     # Service configuration
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_spaces.py

# Run with coverage
pytest --cov=app tests/
```

### Code Structure

- **Orchestrator**: `app/orchestrator.py` - Main RPI workflow using CrewAI
- **Spaces**: `app/spaces.py` - Space management and isolation
- **Memory**: `app/adapters/chroma.py` - Chroma-based memory adapter
- **API**: `app/api.py` - FastAPI endpoints
- **Multi-Agent**: `app/multi_agent_context_system.py` - Parallel sub-agents
- **CrewAI**: `app/crewai.py` - CrewAI agents, tools, and tasks

## License

MIT
