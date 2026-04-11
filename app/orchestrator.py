"""CrewAI orchestrator with Research → Plan → Implement workflow."""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

import tiktoken
from crewai import Crew, Process
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.chroma import ChromaMemoryAdapter
from app.adapters.openrouter import OpenRouterLLMAdapter
from app.adapters.obsidian import ObsidianClient
from app.config import get_settings
from app.core import ContextSource, LLMMessage, Orchestrator, Query, UserID, WorkflowResult
from app.crewai import create_agents_for_space, create_tasks_for_workflow
from app.models import ConversationMessage
from app.multi_agent_context_system import (
    ContextSource as CoordinatorContextSource,
    ContextSourceType,
    ContextSpecification,
    MultiAgentCoordinator,
)
from app.observability import observe_langsmith
from app.spaces import SpaceConfig, SpaceManager

logger = logging.getLogger(__name__)


def _estimate_tokens(content: Any) -> int:
    """Estimate token count using tiktoken."""
    try:
        enc = tiktoken.encoding_for_model("gpt-4o")
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(str(content)))


def _get_memory_for_space(space_config: Optional[SpaceConfig] = None) -> ChromaMemoryAdapter:
    """Get memory manager for a space."""
    settings = get_settings()
    collection_name = space_config.mem0_collection_name if space_config else settings.chroma_collection_name
    return ChromaMemoryAdapter(
        host=settings.chroma_host,
        port=settings.chroma_port,
        collection_name=collection_name,
        persist_directory=settings.chroma_persist_dir,
    )


def _slugify(value: str, max_length: int = 80) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return (slug[:max_length] or "note").strip("-")


def _parse_fallback_models(settings: Any, primary_model: str) -> List[str]:
    fallback_raw = getattr(settings, "fallback_models", None) or ""
    candidates = [primary_model]
    for model_name in fallback_raw.split(","):
        cleaned = model_name.strip()
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)
    if settings.default_model not in candidates:
        candidates.append(settings.default_model)
    return candidates


def _map_context_source_type(source_type: str) -> Optional[ContextSourceType]:
    normalized = (source_type or "").strip().upper()
    aliases = {
        "FILE": ContextSourceType.FILE,
        "DIRECTORY": ContextSourceType.DIRECTORY,
        "URL": ContextSourceType.URL,
        "API": ContextSourceType.API,
        "DATABASE": ContextSourceType.DATABASE,
        "MEMORY": ContextSourceType.MEMORY,
    }
    return aliases.get(normalized)


def _to_coordinator_sources(context_sources: Optional[List[ContextSource]]) -> List[CoordinatorContextSource]:
    mapped: List[CoordinatorContextSource] = []
    for src in context_sources or []:
        ctype = _map_context_source_type(src.type)
        if ctype is None:
            continue
        mapped.append(CoordinatorContextSource(type=ctype, path=src.path, extra=src.extra))
    return mapped


def _extract_frontmatter_value(content: str, key: str) -> str:
    if not content.startswith("---"):
        return ""
    lines = content.splitlines()
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip('"')
    return ""


class OpenRouterLLMWrapper(BaseChatModel):
    """LangChain-compatible wrapper for OpenRouter LLM adapter."""
    
    def __init__(self, model: str = "openai/gpt-4o-mini", **kwargs):
        super().__init__(**kwargs)
        self.model = model
        self.adapter = OpenRouterLLMAdapter()
    
    @property
    def _llm_type(self) -> str:
        return "openrouter"
    
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        import asyncio
        return asyncio.run(self._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs))
    
    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        llm_messages = []
        for msg in messages:
            if hasattr(msg, 'type'):
                role_map = {'human': 'user', 'user': 'user', 'ai': 'assistant', 'assistant': 'assistant', 'system': 'system'}
                role = role_map.get(msg.type, 'user')
            elif hasattr(msg, 'role'):
                role = msg.role
            else:
                role = 'user'
            content = msg.content if hasattr(msg, 'content') else str(msg)
            llm_messages.append(LLMMessage(role=role, content=content))
        
        response = await self.adapter.chat(messages=llm_messages, model=self.model, **kwargs)
        ai_message = AIMessage(content=response.content)
        generation = ChatGeneration(message=ai_message, generation_info={"model": response.model, **response.metadata})
        return ChatResult(generations=[[generation]])


@dataclass
class CrewAIOrchestrator:
    """CrewAI-based orchestrator with Research → Plan → Implement workflow."""

    llm: Optional[OpenRouterLLMAdapter] = None
    memory: Optional[ChromaMemoryAdapter] = None
    obsidian: Optional[ObsidianClient] = None
    coordinator: Optional[MultiAgentCoordinator] = None

    def __post_init__(self) -> None:
        settings = get_settings()
        if self.llm is None:
            self.llm = OpenRouterLLMAdapter()
        if self.memory is None:
            self.memory = ChromaMemoryAdapter(
                host=settings.chroma_host,
                port=settings.chroma_port,
                collection_name=settings.chroma_collection_name,
                persist_directory=settings.chroma_persist_dir,
            )
        if self.obsidian is None:
            self.obsidian = ObsidianClient()
        if self.coordinator is None:
            self.coordinator = MultiAgentCoordinator.production(mem0_wrapper=self.memory)

    async def _save_wiki_artifacts(
        self,
        *,
        obsidian: ObsidianClient,
        query: str,
        research: str,
        plan: str,
        answer: str,
        model_used: str,
        context_sources: List[ContextSource],
    ) -> Dict[str, str]:
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        slug = _slugify(query)
        sanitized_query = query.replace('"', "'")
        source_paths = [f"{src.type}:{src.path}" for src in context_sources]
        source_block = "\n".join([f"  - \"{src}\"" for src in source_paths]) or "  - \"chat\""
        base_frontmatter = (
            "---\n"
            f'query: "{sanitized_query}"\n'
            f'updated_at: "{now.isoformat()}"\n'
            f'model: "{model_used}"\n'
            "confidence: \"medium\"\n"
            "verification_status: \"unverified\"\n"
            "sources:\n"
            f"{source_block}\n"
            "---\n\n"
        )

        research_path = f"Wiki/Research/{date_str}/{timestamp}-{slug}.md"
        plan_path = f"Wiki/Plans/{date_str}/{timestamp}-{slug}.md"
        answer_path = f"Wiki/Answers/{date_str}/{timestamp}-{slug}.md"

        await obsidian.upsert_note(research_path, base_frontmatter + "# Research\n\n" + (research or "No research output"))
        await obsidian.upsert_note(plan_path, base_frontmatter + "# Plan\n\n" + (plan or "No plan output"))
        await obsidian.upsert_note(answer_path, base_frontmatter + "# Answer\n\n" + (answer or "No answer output"))

        index_content = await obsidian.read_note("Wiki/index.md")
        if not index_content:
            index_content = "# Wiki Index\n\n## Research\n\n## Plans\n\n## Answers\n"

        entry_map = {
            "Research": f"- [[{research_path[:-3]}]] - {query}",
            "Plans": f"- [[{plan_path[:-3]}]] - {query}",
            "Answers": f"- [[{answer_path[:-3]}]] - {query}",
        }
        for section, line in entry_map.items():
            if line in index_content:
                continue
            marker = f"## {section}\n"
            if marker not in index_content:
                index_content += f"\n{marker}\n"
            index_content = index_content.replace(marker, marker + "\n" + line + "\n", 1)
        await obsidian.upsert_note("Wiki/index.md", index_content.strip() + "\n")

        await obsidian.append_note(
            "Wiki/log.md",
            (
                f"## [{date_str}] query | {query}\n"
                f"- model: `{model_used}`\n"
                f"- artifacts: [[{research_path[:-3]}]], [[{plan_path[:-3]}]], [[{answer_path[:-3]}]]\n"
            ),
        )
        return {"research": research_path, "plan": plan_path, "answer": answer_path}

    async def lint_space_wiki(
        self,
        *,
        obsidian: ObsidianClient,
        save_report: bool = False,
    ) -> Dict[str, Any]:
        notes = [n for n in await obsidian.list_notes("Wiki") if n.endswith(".md")]
        notes = [n for n in notes if n not in {"Wiki/index.md", "Wiki/log.md"}]
        now = datetime.now(timezone.utc)

        incoming_links: dict[str, int] = {}
        issues: Dict[str, List[str]] = {
            "unsupported_claims": [],
            "stale_claims": [],
            "orphan_pages": [],
            "missing_cross_references": [],
            "possible_contradictions": [],
        }
        note_contents: Dict[str, str] = {}
        lower_lines_by_note: Dict[str, List[str]] = {}

        for note in notes:
            content = await obsidian.read_note(note)
            note_contents[note] = content
            lower_lines = [line.strip().lower() for line in content.splitlines() if line.strip()]
            lower_lines_by_note[note] = lower_lines

            if "TODO:" in content or "TBD" in content or "unverified" in content.lower():
                issues["unsupported_claims"].append(note)
            updated_at = _extract_frontmatter_value(content, "updated_at")
            if updated_at:
                try:
                    parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                    if now - parsed > timedelta(days=30):
                        issues["stale_claims"].append(note)
                except Exception:
                    pass
            if "[[" not in content:
                issues["missing_cross_references"].append(note)
            for match in re.findall(r"\[\[([^\]]+)\]\]", content):
                target = match.split("|", 1)[0].strip()
                if not target.endswith(".md"):
                    target = f"{target}.md"
                incoming_links[target] = incoming_links.get(target, 0) + 1

        for note in notes:
            key = note.split("/", 1)[1] if "/" in note else note
            if incoming_links.get(key, 0) == 0:
                issues["orphan_pages"].append(note)

        for note, lines in lower_lines_by_note.items():
            has_true = any(" is " in line and "not " not in line for line in lines)
            has_not = any(" is not " in line or " isn't " in line for line in lines)
            if has_true and has_not:
                issues["possible_contradictions"].append(note)

        report = {
            "total_notes": len(notes),
            "issues": {k: sorted(set(v)) for k, v in issues.items()},
            "summary": {
                "unsupported_claims": len(set(issues["unsupported_claims"])),
                "stale_claims": len(set(issues["stale_claims"])),
                "orphan_pages": len(set(issues["orphan_pages"])),
                "missing_cross_references": len(set(issues["missing_cross_references"])),
                "possible_contradictions": len(set(issues["possible_contradictions"])),
            },
        }

        if save_report:
            stamp = now.strftime("%Y%m%d-%H%M%S")
            lines = [
                "# Wiki Lint Report",
                "",
                f"- generated_at: {now.isoformat()}",
                f"- total_notes: {report['total_notes']}",
                "",
            ]
            for category, affected in report["issues"].items():
                lines.append(f"## {category}")
                if not affected:
                    lines.append("- none")
                else:
                    lines.extend([f"- [[{n[:-3]}]]" for n in affected])
                lines.append("")
            await obsidian.upsert_note(f"Wiki/Lint/{stamp}.md", "\n".join(lines).strip() + "\n")
        return report

    @observe_langsmith(name="process_query")
    async def process_query(
        self,
        user_id: UserID,
        query: Query,
        model: Optional[str] = None,
        context_sources: Optional[List[ContextSource]] = None,
        db: Optional[AsyncSession] = None,
        space_manager: Optional[SpaceManager] = None,
        **kwargs,
    ) -> WorkflowResult:
        """Process a user query through Research → Plan → Implement workflow."""
        settings = get_settings()
        model = model or settings.default_model

        space_memory = self.memory
        space_obsidian = self.obsidian
        space_coordinator = self.coordinator
        space_schema = None
        active_space: Optional[SpaceConfig] = None
        tokens_used = 0

        if space_manager:
            try:
                space_config = space_manager.get_current_space()
                active_space = space_config
                space_schema = space_config.postgres_schema
                usage = await space_manager.get_space_usage(space_config.space_id)
                remaining = usage.get_budget_remaining(space_config)
                if remaining < 10_000:
                    return WorkflowResult(
                        answer=f"Space budget exceeded. Only {remaining:,} tokens remaining.",
                        metadata={"error": "budget_exceeded", "remaining": remaining},
                    )
                space_memory = _get_memory_for_space(space_config)
                space_obsidian = ObsidianClient(vault_path=space_config.obsidian_vault_path)
                space_coordinator = MultiAgentCoordinator.production(mem0_wrapper=space_memory)
                if space_config.preferred_model:
                    model = space_config.preferred_model
            except RuntimeError:
                pass

        try:
            # Retrieve context directly from adapters
            memories = await space_memory.search(user_id=user_id, query=query, limit=5)
            memories_text = "\n".join([m.text for m in memories])
            
            obsidian_text = ""
            try:
                obsidian_results = await space_obsidian.search(query=query, limit=5)
                obsidian_text = "\n\n".join([r.get("content", "") for r in obsidian_results])
            except Exception as e:
                logger.warning(f"Obsidian retrieval failed: {e}")

            context_sources = context_sources or []
            source_research = ""
            coordinator_sources = _to_coordinator_sources(context_sources)
            if coordinator_sources:
                try:
                    spec = ContextSpecification(query=query, sources=coordinator_sources)
                    source_research = await space_coordinator.research_with_context(spec)
                except Exception as e:
                    logger.warning(f"Context source research failed: {e}")
                    source_research = f"Context source research failed: {e}"

            models_to_try = _parse_fallback_models(settings, model)
            research = ""
            plan = ""
            answer = ""
            result = None
            model_used = model
            last_error: Optional[Exception] = None

            for candidate_model in models_to_try:
                try:
                    llm = OpenRouterLLMWrapper(model=candidate_model)
                    researcher, planner, implementer = create_agents_for_space(
                        memory=space_memory,
                        obsidian=space_obsidian,
                        coordinator=space_coordinator,
                        user_id=user_id,
                        llm=llm,
                        verbose=False,
                    )
                    research_task, plan_task, implement_task = create_tasks_for_workflow(
                        researcher_agent=researcher,
                        planner_agent=planner,
                        implementer_agent=implementer,
                        query=query,
                        memories=memories_text,
                        obsidian_context=obsidian_text,
                        context_findings=source_research,
                    )
                    crew = Crew(
                        agents=[researcher, planner, implementer],
                        tasks=[research_task, plan_task, implement_task],
                        process=Process.sequential,
                        verbose=False,
                    )
                    result = await asyncio.to_thread(crew.kickoff)

                    research = (
                        str(research_task.output.raw)
                        if hasattr(research_task, "output") and research_task.output and hasattr(research_task.output, "raw")
                        else (str(research_task.output) if hasattr(research_task, "output") and research_task.output else "")
                    )
                    plan = (
                        str(plan_task.output.raw)
                        if hasattr(plan_task, "output") and plan_task.output and hasattr(plan_task.output, "raw")
                        else (str(plan_task.output) if hasattr(plan_task, "output") and plan_task.output else "")
                    )
                    answer = (
                        str(implement_task.output.raw)
                        if hasattr(implement_task, "output") and implement_task.output and hasattr(implement_task.output, "raw")
                        else (str(implement_task.output) if hasattr(implement_task, "output") and implement_task.output else "")
                    )

                    if not answer and result is not None:
                        if hasattr(result, "tasks_output") and result.tasks_output and len(result.tasks_output) >= 3:
                            research = str(result.tasks_output[0]) if len(result.tasks_output) > 0 else research
                            plan = str(result.tasks_output[1]) if len(result.tasks_output) > 1 else plan
                            answer = str(result.tasks_output[2]) if len(result.tasks_output) > 2 else ""
                        elif hasattr(result, "raw") and result.raw:
                            answer = str(result.raw)
                        elif isinstance(result, str):
                            answer = result
                        else:
                            answer = str(result)

                    if answer.strip():
                        model_used = candidate_model
                        break
                    raise RuntimeError("Empty answer from workflow")
                except Exception as e:
                    last_error = e
                    logger.warning(f"Workflow failed with model '{candidate_model}': {e}")
                    continue

            if not answer.strip():
                if last_error is not None:
                    raise last_error
                raise RuntimeError("Workflow failed for all candidate models")
            
            if db:
                if space_schema:
                    await db.execute(text(f'SET search_path TO "{space_schema}", public'))
                messages = [
                    ConversationMessage(id=f"{user_id}-{hash(query)}-0", user_id=user_id, role="user", content=query, message_metadata={}),
                    ConversationMessage(id=f"{user_id}-{hash(query)}-1", user_id=user_id, role="assistant", content=answer, message_metadata={}),
                ]
                db.add_all(messages)
                await db.commit()

            asyncio.create_task(space_memory.store(user_id=user_id, text=f"Q: {query}\nA: {answer}", metadata={"source": "crewai-assistant"}))

            wiki_artifacts: Dict[str, str] = {}
            lint_report: Optional[Dict[str, Any]] = None
            try:
                wiki_artifacts = await self._save_wiki_artifacts(
                    obsidian=space_obsidian,
                    query=query,
                    research=research,
                    plan=plan,
                    answer=answer,
                    model_used=model_used,
                    context_sources=context_sources,
                )
                if active_space:
                    lint_report = await self.lint_space_wiki(obsidian=space_obsidian, save_report=True)
            except Exception as e:
                logger.warning(f"Wiki persistence/lint failed: {e}")

            if space_manager:
                try:
                    space_config = space_manager.get_current_space()
                    total_tokens = _estimate_tokens(query) + _estimate_tokens(research) + _estimate_tokens(plan) + _estimate_tokens(answer)
                    await space_manager.update_space_usage(
                        space_id=space_config.space_id, tokens_used=total_tokens, api_calls_used=3, cost_usd=(total_tokens / 1000) * 0.015
                    )
                    tokens_used = total_tokens
                except Exception as e:
                    logger.warning(f"Failed to track token usage: {e}")

            return WorkflowResult(
                answer=answer,
                research=research,
                plan=plan,
                metadata={
                    "model": model_used,
                    "tokens_used": tokens_used,
                    "context_sources_used": len(coordinator_sources),
                    "source_research_included": bool(source_research),
                    "wiki_artifacts": wiki_artifacts,
                    "wiki_lint_summary": lint_report["summary"] if lint_report else None,
                },
            )
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            return WorkflowResult(answer=f"I encountered an error processing your query: {str(e)}", metadata={"error": str(e)})
