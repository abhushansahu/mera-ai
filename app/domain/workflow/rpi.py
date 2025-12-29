from dataclasses import dataclass
from typing import List, Optional

from app.core.llm import LLMProvider, LLMMessage
from app.core.memory import MemoryManager
from app.core.types import ContextSource, Query, UserID


@dataclass
class ResearchResult:
    content: str
    memories_used: Optional[List[str]] = None
    context_sources_used: Optional[List[ContextSource]] = None
    
    def __post_init__(self) -> None:
        if self.memories_used is None:
            self.memories_used = []
        if self.context_sources_used is None:
            self.context_sources_used = []


@dataclass
class PlanResult:
    content: str
    research_summary: str = ""


@dataclass
class ImplementResult:
    answer: str
    research_summary: str = ""
    plan_summary: str = ""


class RPIWorkflow:
    def __init__(
        self,
        llm: LLMProvider,
        memory: MemoryManager,
    ) -> None:
        self.llm = llm
        self.memory = memory

    async def research(
        self,
        user_id: UserID,
        query: Query,
        model: str,
        context_sources: Optional[List[ContextSource]] = None,
    ) -> ResearchResult:
        memories = await self.memory.search(user_id=user_id, query=query, limit=5)
        memory_texts = [m.text for m in memories]
        
        memories_section = "\n".join(memory_texts) if memory_texts else "No relevant memories found."
        
        prompt = f"""TASK: A good group of people are understanding the user's request deeply.

USER QUERY:
{query}

MEMORIES:
{memories_section}

OUTPUT: A concise markdown document named 'research.md' with sections:
1. Problem Statement
2. Key Context and Constraints
3. Relevant Prior Information
4. Open Questions / Gaps
5. Recommended High-Level Approach

Be factual and avoid speculation."""

        messages = [LLMMessage(role="user", content=prompt)]
        response = await self.llm.chat(messages=messages, model=model)
        
        return ResearchResult(
            content=response.content,
            memories_used=memory_texts,
            context_sources_used=context_sources or [],
        )

    async def plan(
        self,
        query: Query,
        research: ResearchResult,
        model: str,
    ) -> PlanResult:
        prompt = f"""A good group of people are creating an implementation plan.

INPUT:
- USER QUERY
- RESEARCH DOCUMENT

Create a markdown document named 'plan.md' with:
1. Step-by-step sequence of actions
2. Data or state that must be read or written
3. Any external tools or services that should be called
4. Testing and validation steps
5. Clear success criteria

The plan should be explicit enough that a less-capable model can follow it reliably.

USER QUERY:
{query}

RESEARCH:
{research.content}"""

        messages = [LLMMessage(role="user", content=prompt)]
        response = await self.llm.chat(messages=messages, model=model)
        
        return PlanResult(
            content=response.content,
            research_summary=research.content[:200],
        )

    async def implement(
        self,
        query: Query,
        research: ResearchResult,
        plan: PlanResult,
        model: str,
    ) -> ImplementResult:
        prompt = f"""A good group of people are executing a pre-written plan exactly.

INPUT:
- USER QUERY
- RESEARCH DOCUMENT
- IMPLEMENTATION PLAN

TASK:
- Follow the plan step-by-step.
- Do not introduce unrelated work.
- When unsure, state the uncertainty explicitly.

OUTPUT:
- Final answer for the user
- Brief summary of what you did

USER QUERY:
{query}

RESEARCH:
{research.content}

PLAN:
{plan.content}"""

        messages = [LLMMessage(role="user", content=prompt)]
        response = await self.llm.chat(messages=messages, model=model)
        
        return ImplementResult(
            answer=response.content,
            research_summary=research.content[:200],
            plan_summary=plan.content[:200],
        )
