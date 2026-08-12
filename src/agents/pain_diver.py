"""The Pain Diver Agent (The User Researcher).

Reads Reddit/HN/Blog threads to extract detailed pain points.
"""

import json
import logging
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from src.graph.state import ResearchState, PainPointProfile
from src.config.settings import get_settings
from src.utils.langchain_models import get_chat_model
from src.agents.tools.web import read_webpage
from src.prompts.pain_diver import build_pain_diver_prompt

@tool(args_schema=PainPointProfile)
def submit_pain_point_profile(**kwargs):
    """Submit the final analyzed pain point profile."""
    pass

logger = logging.getLogger(__name__)

def pain_diver_node(state: ResearchState) -> dict:
    """Run the pain diver agent on pain point candidates."""
    candidates = state.get("raw_pain_point_candidates", [])
    if not candidates:
        return {"progress_messages": ["Pain Diver: No candidates to analyze."]}
        
    logger.info("Pain Diver starting on %d candidates", len(candidates))
    
    llm = get_chat_model("pain_diver")
    agent = create_react_agent(llm, tools=[read_webpage, submit_pain_point_profile])
    
    processed_candidates = state.get("processed_candidates", [])
    profiles = []
    messages = []
    new_processed = []
    
    settings = get_settings()
    processed_count = 0
    for cand in candidates:
        if processed_count >= settings.max_pain_points_deep:
            break
            
        c_data = cand.get("candidate", {})
        url = c_data.get("url")
        src_id = c_data.get("src_id")
        
        if not src_id or src_id in processed_candidates or src_id in new_processed:
            continue
            
        prompt_val = build_pain_diver_prompt(
            raw_idea=state['raw_idea'],
            url=url,
            strategy=state.get('current_strategy', '')
        )
        try:
            result = agent.invoke({"messages": prompt_val.format_messages()})
            
            # Extract structured data from tool call
            p_data = None
            for msg in reversed(result["messages"]):
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        if tc["name"] == "submit_pain_point_profile":
                            p_data = tc["args"]
                            break
                    if p_data:
                        break
                        
            if not p_data:
                raise ValueError("Agent did not call submit_pain_point_profile tool.")
            
            profile = PainPointProfile(
                src_id=src_id,
                url=url,
                core_problem=p_data.get("core_problem", ""),
                detailed_frustrations=p_data.get("detailed_frustrations", []),
                representative_quotes=p_data.get("representative_quotes", [])
            )
            profiles.append(profile)
            new_processed.append(src_id)
            processed_count += 1
            messages.append(f"Pain Diver: Extracted detailed frustrations from {url}")
            
        except Exception as e:
            logger.error("Pain Diver failed on %s: %s", url, e)
            messages.append(f"Pain Diver failed on {url}: {e}")
            new_processed.append(src_id) # Don't retry failed URLs
            
    return {
        "pain_point_profiles": profiles,
        "processed_candidates": new_processed,
        "progress_messages": messages,
        "next_agent": "orchestrator"
    }
