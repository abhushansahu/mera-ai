from app.multi_agent_context_system import (
    ContextSource,
    ContextSourceType,
    ContextSpecification,
    DataAnalyzerAgent,
    FileExplorerAgent,
    LinkCrawlerAgent,
    MemoryRetrieverAgent,
    MultiAgentCoordinator,
    SynthesizerAgent,
)


def test_context_source_and_spec_construction() -> None:
    src = ContextSource(type=ContextSourceType.FILE, path="README.md")
    spec = ContextSpecification(query="What is this project?", sources=[src])
    assert spec.sources[0].type is ContextSourceType.FILE
    assert spec.query.startswith("What")


def test_file_explorer_agent_uses_paths() -> None:
    captured = {}

    def fake_read(paths):
        captured["paths"] = list(paths)
        return "content"

    agent = FileExplorerAgent(read_paths=fake_read)
    src = ContextSource(type=ContextSourceType.FILE, path="a.py")
    out = agent.run([src], query="test")
    assert "File/Directory" in out
    assert captured["paths"] == ["a.py"]


def test_link_crawler_agent_uses_urls() -> None:
    captured = {}

    def fake_fetch(urls):
        captured["urls"] = list(urls)
        return "docs"

    agent = LinkCrawlerAgent(fetch_urls=fake_fetch)
    src = ContextSource(type=ContextSourceType.URL, path="https://example.com")
    out = agent.run([src], query="test")
    assert "Link/API" in out
    assert captured["urls"] == ["https://example.com"]


def test_data_analyzer_agent_uses_dbs() -> None:
    captured = {}

    def fake_analyze(dbs, query):
        captured["dbs"] = list(dbs)
        captured["query"] = query
        return "db-analysis"

    agent = DataAnalyzerAgent(analyze_databases=fake_analyze)
    src = ContextSource(type=ContextSourceType.DATABASE, path="postgres://localhost/db")
    out = agent.run([src], query="auth question")
    assert "Database" in out
    assert captured["dbs"] == ["postgres://localhost/db"]
    assert captured["query"] == "auth question"


def test_memory_retriever_agent_invokes_retriever() -> None:
    captured = {}

    def fake_retrieve(identifier, query):
        captured["identifier"] = identifier
        captured["query"] = query
        return "memory"

    agent = MemoryRetrieverAgent(retrieve_memory=fake_retrieve)
    src = ContextSource(type=ContextSourceType.MEMORY, path="user-1")
    out = agent.run([src], query="test query")
    assert "Memory" in out
    assert captured["identifier"] == "user-1"
    assert captured["query"] == "test query"


def test_synthesizer_agent_combines_parts() -> None:
    synth = SynthesizerAgent()
    result = synth.run(["part1", "part2"], query="q")
    assert "Research Summary" in result
    assert "part1" in result and "part2" in result


def test_multi_agent_coordinator_default_research() -> None:
    coord = MultiAgentCoordinator.default()
    spec = ContextSpecification(
        query="How does auth work?",
        sources=[
            ContextSource(type=ContextSourceType.DIRECTORY, path="./src/auth"),
            ContextSource(type=ContextSourceType.URL, path="https://api.example.com/docs"),
            ContextSource(type=ContextSourceType.DATABASE, path="postgres://localhost/auth"),
            ContextSource(type=ContextSourceType.MEMORY, path="auth-mem"),
        ],
    )
    research = coord.research_with_context(spec)
    assert "Research Summary" in research
    # Ensure that each type contributed something
    assert "Examined code/docs" in research
    assert "Fetched documentation" in research
    assert "Considered database" in research
    assert "Retrieved memory context" in research


