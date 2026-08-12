"""The Deep Diver Agent (The Analyst).

Reads webpages and app store reviews to build competitor dossiers.
"""

import json
import logging
from typing import Any
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from src.graph.state import ResearchState, CompetitorProfile
from src.utils.langchain_models import get_chat_model
from src.agents.tools.web import read_webpage
from src.agents.tools.app_store import get_app_store_reviews
from src.config.settings import get_settings
from src.prompts.deep_diver import build_deep_diver_prompt

@tool(args_schema=CompetitorProfile)
def submit_competitor_profile(**kwargs):
    """Submit the final analyzed competitor profile."""
    pass

logger = logging.getLogger(__name__)

def deep_diver_node(state: ResearchState) -> dict:
    """Run the deep diver agent on search candidates."""
    candidates = state.get("raw_competitor_candidates", [])
    if not candidates:
        return {"progress_messages": ["Deep Diver: No candidates to analyze."]}
        
    logger.info("Deep Diver starting on %d candidates", len(candidates))
    
    llm = get_chat_model("deep_diver")
    agent = create_react_agent(llm, tools=[read_webpage, get_app_store_reviews, submit_competitor_profile])
    
    processed_candidates = state.get("processed_candidates", [])
    profiles = []
    messages = []
    new_processed = []
    
    settings = get_settings()
    processed_count = 0
    for cand in candidates:
        if processed_count >= settings.max_competitors_deep:
            break
            
        c_data = cand.get("candidate", {})
        url = c_data.get("url")
        src_id = c_data.get("src_id")
        name = c_data.get("name", "Unknown Competitor")
        
        if not src_id or src_id in processed_candidates or src_id in new_processed:
            continue
            
        prompt_val = build_deep_diver_prompt(
            raw_idea=state['raw_idea'],
            name=name,
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
                        if tc["name"] == "submit_competitor_profile":
                            p_data = tc["args"]
                            break
                    if p_data:
                        break
                        
            if not p_data:
                raise ValueError("Agent did not call submit_competitor_profile tool.")
            
            profile = CompetitorProfile(
                src_ids=[src_id],
                name=p_data.get("name", name),
                url=p_data.get("url", url),
                pricing=p_data.get("pricing", "Unknown"),
                features=p_data.get("features", []),
                positioning=p_data.get("positioning", "Unknown"),
                weaknesses=p_data.get("weaknesses", []),
                has_mobile_app=p_data.get("has_mobile_app", False)
            )
            profiles.append(profile)
            new_processed.append(src_id)
            processed_count += 1
            messages.append(f"Deep Diver analyzed {name}.")
            
        except Exception as e:
            logger.error("Deep Diver failed on %s: %s", url, e)
            messages.append(f"Deep Diver failed on {name}: {e}")
            new_processed.append(src_id) # Don't retry failed URLs
            
    return {
        "competitor_profiles": profiles,
        "processed_candidates": new_processed,
        "progress_messages": messages
    }
