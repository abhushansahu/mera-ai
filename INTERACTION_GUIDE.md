# Mera AI - Interaction Guide

This guide explains how to interact with the Mera AI system now that all services are running in containers.

## 🚀 Quick Start

### 1. Check Service Status

```bash
# Check all Docker containers
docker-compose ps

# Check specific service logs
docker-compose logs mem0
docker-compose logs langfuse
docker-compose logs postgres
```

### 2. Start the Main Application

The Docker containers provide the infrastructure services. To run the main Python application:

```bash
# Activate virtual environment
source venv/bin/activate

# Start the main application server
python -m app.main
```

The server will start on `http://localhost:8000`

### 3. Verify Services are Running

```bash
# Check main application status
curl http://localhost:8000/status

# Check Mem0 health
curl http://localhost:8001/health

# Check Langfuse health (may show errors but service is running)
curl http://localhost:3000/api/public/health
```

## 📡 API Endpoints

### Main Application API

**Base URL:** `http://localhost:8000`

#### Status Endpoint
```bash
GET /status
```
Returns the status of all services and API key configuration.

#### Chat Endpoint
```bash
POST /chat
Content-Type: application/json

{
  "user_id": "user123",
  "query": "What is the weather today?",
  "model": "openai/gpt-4o-mini",  # Optional
  "context_sources": []  # Optional
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "query": "Hello, how are you?",
    "model": "openai/gpt-4o-mini"
  }'
```

#### API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Mem0 API (Self-Hosted)

**Base URL:** `http://localhost:8001`

#### Health Check
```bash
GET /health
```

#### Add Memory
```bash
POST /add
Content-Type: application/json

{
  "user_id": "user123",
  "messages": "User said: I love Python programming",
  "metadata": {}  # Optional
}
```

**Example:**
```bash
curl -X POST http://localhost:8001/add \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "messages": "I am learning about AI and machine learning"
  }'
```

#### Search Memories
```bash
POST /search
Content-Type: application/json

{
  "user_id": "user123",
  "query": "What did I say about Python?",
  "limit": 5
}
```

#### Get All Memories
```bash
GET /get_all/{user_id}?limit=100
```

#### Delete Memories
```bash
DELETE /delete/{user_id}
```

#### Mem0 API Documentation
- Swagger UI: http://localhost:8001/docs

### Langfuse UI

**URL:** http://localhost:3000

1. Open http://localhost:3000 in your browser
2. Create an account (first time only)
3. Go to Settings → API Keys
4. Copy your `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`
5. Add them to your `.env` file:
   ```
   LANGFUSE_PUBLIC_KEY=your_public_key_here
   LANGFUSE_SECRET_KEY=your_secret_key_here
   ```

## 🗄️ Database Access

### PostgreSQL

**Connection Details:**
- Host: `localhost`
- Port: `5432`
- Database: `ai_assistant` (main app) or `langfuse` (Langfuse)
- User: `ai_user`
- Password: `ai_password`

**Connect via psql:**
```bash
psql -h localhost -U ai_user -d ai_assistant
```

**Or via Docker:**
```bash
docker exec -it mera-ai-postgres psql -U ai_user -d ai_assistant
```

## 🔧 Managing Services

### Start All Services
```bash
# Using docker-compose directly
docker-compose up -d

# Or using the convenience script
./start.sh
# or
python scripts/start_all_services.py
```

### Stop All Services
```bash
# Using docker-compose directly
docker-compose down

# Or using the convenience script
./stop.sh
# or
python scripts/stop_all_services.py
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f mem0
docker-compose logs -f langfuse
docker-compose logs -f postgres
```

### Restart a Service
```bash
docker-compose restart mem0
docker-compose restart langfuse
```

### Rebuild a Service (after code changes)
```bash
docker-compose build mem0
docker-compose up -d mem0
```

## 🧪 Testing the System

### 1. Test Mem0
```bash
# Add a memory
curl -X POST http://localhost:8001/add \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "messages": "I like coffee"}'

# Search memories
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "query": "coffee", "limit": 5}'
```

### 2. Test Main Application
```bash
# Check status
curl http://localhost:8000/status

# Send a chat message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "query": "Hello, can you help me?"
  }'
```

### 3. Test Database Connection
```bash
docker exec -it mera-ai-postgres psql -U ai_user -d ai_assistant -c "SELECT 1;"
```

## 📊 Service URLs Summary

| Service | URL | Description |
|---------|-----|-------------|
| Main App API | http://localhost:8000 | FastAPI application |
| Main App Docs | http://localhost:8000/docs | Swagger UI |
| Mem0 API | http://localhost:8001 | Mem0 memory service |
| Mem0 Docs | http://localhost:8001/docs | Mem0 API docs |
| Langfuse UI | http://localhost:3000 | Langfuse observability UI |
| PostgreSQL | localhost:5432 | Database (ai_assistant, langfuse) |
| ClickHouse | http://localhost:8123 | Langfuse analytics database |

## 🔍 Troubleshooting

### Service Not Starting
```bash
# Check container status
docker-compose ps

# Check logs for errors
docker-compose logs [service-name]

# Check if ports are in use
lsof -i :8000
lsof -i :8001
lsof -i :3000
```

### Database Connection Issues
```bash
# Verify PostgreSQL is running
docker-compose ps postgres

# Check database exists
docker exec -it mera-ai-postgres psql -U ai_user -l
```

### Mem0 Issues
```bash
# Check Mem0 logs
docker-compose logs mem0

# Verify Mem0 is accessible
curl http://localhost:8001/health
```

### Langfuse Issues
```bash
# Check Langfuse logs (ZodError is known issue, service still works)
docker-compose logs langfuse | tail -50

# Verify ClickHouse is running
docker-compose ps clickhouse
```

## 📝 Environment Variables

The main application requires these environment variables (set in `.env` file):

**Required:**
- `OPENROUTER_API_KEY` - Your OpenRouter API key
- `DATABASE_URL` - PostgreSQL connection string
- `MEM0_HOST` - Mem0 host URL (http://localhost:8001 for self-hosted)

**Optional:**
- `LANGFUSE_PUBLIC_KEY` - For observability
- `LANGFUSE_SECRET_KEY` - For observability
- `OBSIDIAN_REST_TOKEN` - For Obsidian integration

**Note:** `MEM0_API_KEY` is NOT required for self-hosted Mem0. It's only needed if using external Mem0 service.

## 🎯 Next Steps

1. **Set up your `.env` file:**
   ```bash
   cp env.example .env
   # Edit .env and add your OPENROUTER_API_KEY
   ```

2. **Start the main application:**
   ```bash
   source venv/bin/activate
   python -m app.main
   ```

3. **Access the API documentation:**
   - Main app: http://localhost:8000/docs
   - Mem0: http://localhost:8001/docs

4. **Set up Langfuse (optional):**
   - Visit http://localhost:3000
   - Create account and get API keys
   - Add keys to `.env` file

5. **Start using the API!**
   - Use the `/chat` endpoint to interact with the AI
   - Use Mem0 endpoints to manage memories
   - View traces in Langfuse UI
