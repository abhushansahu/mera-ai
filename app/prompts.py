"""Prompt templates for the Research → Plan → Implement workflow."""

RESEARCH_PROMPT = """
TASK: A good group of people are understanding the user's request deeply.

USER QUERY:
{query}

MEMORIES:
{memories}

OBSIDIAN CONTEXT:
{obsidian_context}

OUTPUT: A concise markdown document named 'research.md' with sections:
1. Problem Statement
2. Key Context and Constraints
3. Relevant Prior Information
4. Open Questions / Gaps
5. Recommended High-Level Approach

Be factual and avoid speculation.
"""


PLAN_PROMPT = """
A good group of people are creating an implementation plan.

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
"""


IMPLEMENT_PROMPT = """
A good group of people are executing a pre-written plan exactly.

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
"""


