from langchain_core.prompts import ChatPromptTemplate

def build_searcher_prompt(raw_idea: str, max_competitors: int, max_pain_points: int, strategy: str) -> ChatPromptTemplate:
    template = """You are the Web Searcher Agent (The Scout).
Your job is to find competitors and user pain points for the following product idea:
"{raw_idea}"

ORCHESTRATOR INSTRUCTIONS: {strategy}

Use the `search_web` tool to find:
1. Up to {max_competitors} direct competitors.
2. Up to {max_pain_points} user pain points/complaints related to this industry.

When you are finished, you MUST call the `submit_search_results` tool to save your final structured findings."""
    
    return ChatPromptTemplate.from_messages([
        ("system", template)
    ]).partial(
        raw_idea=raw_idea,
        max_competitors=max_competitors,
        max_pain_points=max_pain_points,
        strategy=strategy
    )
