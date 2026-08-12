from langchain_core.prompts import ChatPromptTemplate

def build_orchestrator_prompt(raw_idea: str, depth: str, state_summary: str) -> ChatPromptTemplate:
    template = """You are the Lead Orchestrator of an AI research firm.
Your job is to coordinate a team of AI workers to investigate a user's product idea and write a comprehensive market research report.

PRODUCT IDEA: "{raw_idea}"
DEPTH REQUIRED: {depth}

Your workers are:
1. searcher: Finds competitors and pain points on the web.
2. pain_diver: Deeply scrapes and extracts details from the pain point URLs.
3. deep_diver: Deeply analyzes specific competitors.
4. thinker: Synthesizes market gaps.
5. writer: Writes the final report.

CURRENT STATE OF RESEARCH:
{state_summary}

Based on the current state, decide which worker needs to run next.
Provide the next agent to route to, your reasoning for this choice, and specific instructions (strategy) for that agent."""
    
    return ChatPromptTemplate.from_messages([
        ("system", template)
    ]).partial(
        raw_idea=raw_idea,
        depth=depth,
        state_summary=state_summary
    )
