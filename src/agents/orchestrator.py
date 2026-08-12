"""The Orchestrator Agent Node.

This is the supervisor of the swarm. It reviews the global state and decides
which specialist agent should act next, or if the research is complete.
"""

import logging
from typing import Literal
from pydantic import BaseModel, Field
from src.graph.state import ResearchState
from src.utils.langchain_models import get_chat_model
from src.prompts.orchestrator import build_orchestrator_prompt
from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)

class OrchestratorDecision(BaseModel):
    """The routing decision from the orchestrator."""
    next_agent: Literal["searcher", "pain_diver", "deep_diver", "thinker", "writer", "FINISH"]
    reasoning: str = Field(description="Why this agent was chosen.")
    strategy: str = Field(description="Specific instructions for the next agent on what to focus on.")

def orchestrator_node(state: ResearchState) -> dict:
    """Analyze state and route to the next agent."""
    logger.info("Orchestrator evaluating state for job %s...", state.get("job_id"))
    
    # State inspection
    processed_candidates = state.get("processed_candidates", [])
    competitors = state.get("competitor_profiles", [])
    pain_points = state.get("pain_point_profiles", [])
    gaps = state.get("gaps", [])
    has_report = bool(state.get("report_markdown"))
    search_results_comps = state.get("raw_competitor_candidates", [])
    search_results_pains = state.get("raw_pain_point_candidates", [])
    
    unprocessed_comps = [c for c in search_results_comps if c.get("candidate", {}).get("src_id") not in processed_candidates]
    unprocessed_pains = [p for p in search_results_pains if p.get("candidate", {}).get("src_id") not in processed_candidates]
    
    # State inspection for the prompt
    state_summary = []
    if search_results_comps or search_results_pains:
        state_summary.append(f"- {len(unprocessed_comps)} unprocessed competitor URLs remaining.")
        state_summary.append(f"- {len(unprocessed_pains)} unprocessed pain point URLs remaining.")
    if pain_points:
        state_summary.append(f"- {len(pain_points)} pain point URLs deeply scraped and analyzed.")
    if competitors:
        state_summary.append(f"- {len(competitors)} competitor profiles deeply analyzed and saved.")
    if gaps:
        state_summary.append(f"- {len(gaps)} market gaps synthesized by the Thinker.")
    if has_report:
        state_summary.append("- Final markdown report drafted.")
        
    if not state_summary:
        state_str = "We are just starting. No research has been done yet."
    else:
        state_str = "\n".join(state_summary)
        
    llm = get_chat_model("orchestrator")
    structured_llm = llm.with_structured_output(OrchestratorDecision)
    
    prompt_val = build_orchestrator_prompt(
        raw_idea=state['raw_idea'],
        depth=state.get('depth', 'fast'),
        state_summary=state_str
    )

    try:
        decision = structured_llm.invoke(prompt_val.format_messages())
        
        return {
            "next_agent": decision.next_agent,
            "current_strategy": decision.strategy,
            "progress_messages": [
                f"Orchestrator Plan: {decision.reasoning}", 
                f"Strategy: {decision.strategy}",
                f"Delegating to {decision.next_agent}"
            ]
        }
    except Exception as e:
        logger.error("Orchestrator failed: %s", e)
        # Fallback to searcher
        return {"next_agent": "searcher", "progress_messages": ["Orchestrator error, falling back to Searcher."]}
