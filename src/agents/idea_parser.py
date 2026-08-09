"""Idea Parser Agent Node.

This is the first node in the graph. It takes the raw user idea and
uses Gemini Flash to parse it into a structured format (category,
target user, features, and search terms) to drive the downstream nodes.
"""

import logging

from src.graph.state import ParsedIdea, ResearchState
from src.prompts.idea_parser import build_messages
from src.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

def _create_fallback_idea(raw_idea: str, error_msg: str) -> tuple[ParsedIdea, list[str]]:
    """Create a minimal fallback idea if parsing fails."""
    fallback_term = raw_idea[:100].strip()
    return ParsedIdea(
        category="Unknown",
        target_user="Unknown",
        core_problem="Unknown",
        key_features=[],
        competitor_search_terms=[f"best tools for {fallback_term}"],
        pain_point_search_terms=[f"{fallback_term} frustrations complaints"],
    ), [error_msg]


def idea_parser(state: ResearchState) -> dict:
    """Parse the raw idea into structured components and search terms.

    Args:
        state: The current ResearchState.

    Returns:
        State update dict with parsed_idea, token_usage, and progress_messages.
    """
    raw_idea = state["raw_idea"]
    depth = state.get("depth", "fast")

    # Depth settings from ARCHITECTURE.md Section 8
    num_competitor_queries = 3 if depth == "fast" else 6
    num_pain_point_queries = 4 if depth == "fast" else 8

    client = LLMClient()
    messages = build_messages(
        raw_idea,
        num_competitor_queries=num_competitor_queries,
        num_pain_point_queries=num_pain_point_queries
    )

    try:
        response = client.complete(
            task="idea_parsing",
            messages=messages,
            temperature=0.2,
            response_model=ParsedIdea,
        )
        parsed_idea = response.parse_pydantic(ParsedIdea)
        errors = []
        
        # Ensure search terms aren't empty despite schema
        if not parsed_idea.competitor_search_terms:
            raise ValueError("competitor_search_terms is empty")
            
    except Exception as e:
        logger.error("idea_parser failed to parse JSON: %s", e)
        parsed_idea, errors = _create_fallback_idea(raw_idea, f"idea_parser JSON error: {e}")
        
        # We need a dummy response for token tracking if it completely crashed before returning
        if 'response' not in locals():
            from src.utils.llm_client import LLMResponse
            response = LLMResponse("", provider="unknown", model="unknown", input_tokens=0, output_tokens=0)

    result = {
        "parsed_idea": parsed_idea,
        "token_usage": {
            response.provider: response.input_tokens + response.output_tokens
        },
        "progress_messages": [
            f"Parsed idea into category '{parsed_idea.category}' "
            f"with {len(parsed_idea.competitor_search_terms)} competitor search terms "
            f"and {len(parsed_idea.pain_point_search_terms)} pain point search terms."
        ],
    }

    if errors:
        result["errors"] = errors

    return result
