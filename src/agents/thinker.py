"""The Thinker Agent (The Strategist).

Synthesizes the final output and identifies market gaps.
"""

import json
import logging
from langchain_core.messages import SystemMessage
from src.graph.state import ResearchState, Gap
from src.utils.langchain_models import get_chat_model
from src.prompts.thinker import build_thinker_prompt
from pydantic import BaseModel

class ThinkerOutput(BaseModel):
    gaps: list[Gap]
    landscape_summary: str
    positioning_suggestions: list[str]

logger = logging.getLogger(__name__)

def thinker_node(state: ResearchState) -> dict:
    """Run the thinker agent to synthesize gaps."""
    logger.info("Thinker starting for job %s", state.get("job_id"))
    
    llm = get_chat_model("thinker")
    
    pain_points = state.get("pain_point_profiles", [])
    pp_lines = []
    for p in pain_points:
        # Build a detailed string for each profile
        desc = (
            f"URL: {p.url} (Src: {p.src_id})\n"
            f"Core Problem: {p.core_problem}\n"
            f"Detailed Frustrations: {', '.join(p.detailed_frustrations)}\n"
            f"Representative Quotes: {', '.join(p.representative_quotes)}"
        )
        pp_lines.append(desc)
        
    pp_text = "\n\n".join(pp_lines)
    
    competitors = state.get("competitor_profiles", [])
    comp_lines = []
    for c in competitors:
        desc = (
            f"Competitor: {c.name} (URL: {c.url})\n"
            f"Pricing: {c.pricing}\n"
            f"Features: {', '.join(c.features)}\n"
            f"Positioning: {c.positioning}\n"
            f"Weaknesses: {', '.join(c.weaknesses)}\n"
        )
        comp_lines.append(desc)
    competitors_text = "\n\n".join(comp_lines)
    
    prompt = build_thinker_prompt(
        raw_idea=state['raw_idea'],
        pp_text=pp_text,
        competitors_text=competitors_text,
        strategy=state.get('current_strategy', '')
    )

    try:
        parser = llm.with_structured_output(ThinkerOutput).with_retry(stop_after_attempt=3)
        parsed = parser.invoke(prompt.format_messages())
        
        return {
            "gaps": parsed.gaps,
            "landscape_summary": parsed.landscape_summary,
            "positioning_suggestions": parsed.positioning_suggestions,
            "progress_messages": ["Thinker: Synthesized gaps and landscape."],
            "next_agent": "orchestrator"
        }
    except Exception as e:
        logger.error("Thinker failed: %s", e)
        return {
            "progress_messages": [f"Thinker error: {e}"],
            "next_agent": "orchestrator",
            "errors": [str(e)]
        }
