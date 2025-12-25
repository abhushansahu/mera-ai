# Langfuse Integration Summary

## Changes Made

### 1. ✅ Created Langfuse Client Module (`app/langfuse_client.py`)
- Centralized Langfuse client initialization
- Graceful handling when Langfuse is not configured
- Helper function to check if Langfuse is enabled

### 2. ✅ Added `@observe()` Decorators to All Orchestrator Nodes
All nodes in `app/orchestrator.py` now have observability:

- `@observe(name="mem0_retrieve")` - Memory retrieval from Mem0
- `@observe(name="obsidian_search")` - Obsidian vault search
- `@observe(name="research")` - Research phase (with multi-sub-agent support)
- `@observe(name="research_review")` - Research review checkpoint
- `@observe(name="plan")` - Planning phase
- `@observe(name="plan_review")` - Plan review checkpoint
- `@observe(name="implement")` - Implementation phase
- `@observe(name="monitor_context")` - Context utilization monitoring
- `@observe(name="mem0_store")` - Storing memories to Mem0
- `@observe(name="obsidian_update")` - Updating Obsidian vault
- `@observe(name="process_query")` - Main entry point

### 3. ✅ Added Tracing to Multi-Sub-Agent System (`app/multi_agent_context_system.py`)
All sub-agents are now traced:

- `@observe(name="file_explorer_agent")` - File/directory exploration
- `@observe(name="link_crawler_agent")` - URL/API fetching
- `@observe(name="data_analyzer_agent")` - Database analysis
- `@observe(name="memory_retriever_agent")` - Memory retrieval
- `@observe(name="synthesizer_agent")` - Research synthesis
- `@observe(name="multi_agent_coordinator")` - Coordinator orchestration

### 4. ✅ Updated Requirements (`requirements.txt`)
Added `langfuse` package dependency.

### 5. ✅ Added Langfuse Initialization (`app/api.py`)
- Langfuse client initialized at app startup
- Logging for observability status
- Graceful handling when Langfuse is not configured

## What You'll See in Langfuse Dashboard

Once Langfuse is configured and running, you'll see:

1. **Traces** for each query showing the complete flow:
   - User query → Mem0 retrieval → Obsidian search → Research → Plan → Implement

2. **Sub-agent traces** when using multi-agent context:
   - FileExplorerAgent execution
   - LinkCrawlerAgent execution
   - DataAnalyzerAgent execution
   - MemoryRetrieverAgent execution
   - SynthesizerAgent execution

3. **Metrics**:
   - Token usage per node
   - Latency per phase
   - Cost tracking (when using OpenRouter)
   - Context utilization percentages

4. **Hierarchical view**:
   - Main trace → Sub-traces for each node
   - Nested traces for sub-agents
   - Full state transitions visible

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Langfuse Services
```bash
docker-compose up -d langfuse-db langfuse
```

### 3. Configure Langfuse Keys
1. Access Langfuse UI: http://localhost:3000
2. Create an account (first-time setup)
3. Go to Settings → API Keys
4. Copy your `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`

### 4. Update `.env` File
```bash
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

### 5. Restart Your Application
```bash
# The app will automatically initialize Langfuse on startup
python -m app.main
```

## Testing the Integration

### Test 1: Basic Query
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "query": "What is memory in AI systems?",
    "model": "openai/gpt-4o-mini"
  }'
```

**Check Langfuse:** http://localhost:3000
- You should see a trace named "process_query"
- Expand it to see all node executions

### Test 2: Multi-Agent Query with Context
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "query": "Analyze the authentication system",
    "model": "openai/gpt-4o-mini",
    "context_sources": [
      {"type": "DIRECTORY", "path": "./src/auth"},
      {"type": "URL", "path": "https://api.example.com/docs"}
    ]
  }'
```

**Check Langfuse:**
- Main trace: "process_query"
- Research trace: "research"
- Sub-traces: "file_explorer_agent", "link_crawler_agent", "synthesizer_agent"

## Benefits

1. **Full Visibility**: See exactly what each node does and how long it takes
2. **Cost Tracking**: Monitor token usage and costs per query
3. **Debugging**: Identify bottlenecks and failures quickly
4. **Performance**: Track context utilization and optimize accordingly
5. **Multi-Agent Debugging**: See how sub-agents coordinate and where they spend time

## Notes

- Langfuse is **optional** - the app works fine without it
- If Langfuse keys are not configured, the app will log a message and continue
- All `@observe()` decorators gracefully handle missing Langfuse configuration
- Traces are automatically sent to Langfuse when configured

## Next Steps

1. **Set up Langfuse** (if not already done)
2. **Run a few queries** and explore the traces in the dashboard
3. **Set up alerts** in Langfuse for high costs or errors
4. **Use Langfuse for prompt optimization** - A/B test different prompts
5. **Monitor context utilization** - Set alerts when approaching "dumb zone" (>40%)

