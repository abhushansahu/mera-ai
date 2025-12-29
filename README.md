# Mera AI - Unified AI Assistant

A self-hosted AI assistant that provides a single interface to chat with multiple AI models, with persistent memory and knowledge base integration.

## What It Does

- **Unified Interface**: Chat with any AI model through OpenRouter (GPT-4, Claude, and 280+ others)
- **Persistent Memory**: Remembers conversations using Chroma vector database
- **Knowledge Base**: Integrates with Obsidian vault using LlamaIndex for enhanced retrieval
- **Observability**: Track usage, costs, and performance with LangSmith
- **LangChain Orchestration**: Uses LangChain Agents and Chains for Research → Plan → Implement workflow
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

**Note:** If you're using Obsidian integration, you may need to mount your vault directory. Edit `docker-compose.yml` and uncomment the Obsidian vault volume mount, then set your vault path.

#### 4. Stop Services

```bash
# Using the convenience script
./stop.sh

# Or using docker-compose directly
docker-compose down
```

## Usage

### Chat with AI

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "query": "Hello, remember my name is Alice"
  }'
```

### Check Status

```bash
curl http://localhost:8000/status
```

### API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Architecture

### LangChain Orchestration

The system uses LangChain Agents and Chains to implement a Research → Plan → Implement (RPI) workflow:

- **Research Phase**: LangChain Agent with retrieval tools (Chroma memory, Obsidian vault, multi-agent context)
- **Plan Phase**: LLM planner that creates structured implementation plans
- **Implement Phase**: Tool-calling agent that executes the plan step-by-step

### Observability with LangSmith

All operations are traced using LangSmith for:
- Request/response tracking
- Token usage and cost monitoring
- Performance metrics
- Debugging and optimization

### LlamaIndex Integration

Obsidian vault is indexed using LlamaIndex with Chroma as the vector store:
- Structured document indexing
- Enhanced retrieval with metadata filtering
- Incremental updates support

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

### Obsidian Integration

Connect your Obsidian vault to provide context from your notes. The system uses LlamaIndex to index your vault for enhanced retrieval.

**Setup:**

1. Set `OBSIDIAN_VAULT_PATH` in `.env` to your vault directory

2. Edit `docker-compose.yml` and uncomment the Obsidian vault volume mount
   - Set the path to your vault: `- /path/to/your/obsidian/vault:/app/obsidian_vault:ro`
   - Update `OBSIDIAN_VAULT_PATH` in `.env` to `/app/obsidian_vault`

3. Rebuild the container: `docker-compose up -d --build app`

4. Build the index: `docker-compose exec app python -m app.infrastructure.indexing.index_manager build`

5. The system will automatically use the indexed vault for retrieval

**Index Management:**

- Build: `docker-compose exec app python -m app.infrastructure.indexing.index_manager build`
- Update: `docker-compose exec app python -m app.infrastructure.indexing.index_manager update`
- Refresh: `docker-compose exec app python -m app.infrastructure.indexing.index_manager refresh`

Configure in `.env`:

```
OBSIDIAN_REST_URL=http://localhost:27124
OBSIDIAN_REST_TOKEN=your_token_here
```

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
- `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` - For observability
- `OBSIDIAN_REST_URL` / `OBSIDIAN_REST_TOKEN` - For Obsidian integration
- `CHROMA_PERSIST_DIR` - Memory storage location (default: `./chroma_db`)

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

## Obsidian Plugin

There's an Obsidian plugin available for direct integration. See [obsidian-plugin/README.md](obsidian-plugin/README.md) for details.

## Troubleshooting

### Services Not Starting

```bash
# Check if ports are in use
lsof -i :8000
lsof -i :3000
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

## Project Structure

```
mera-ai/
├── app/              # Main application code
│   ├── api/          # API routes
│   ├── core/         # Core logic
│   ├── adapters/     # External service adapters
│   └── infrastructure/ # Infrastructure setup
├── obsidian-plugin/  # Obsidian integration plugin
├── scripts/          # Utility scripts
├── tests/            # Test files
└── docker-compose.yml # Service configuration
```

## License

MIT
