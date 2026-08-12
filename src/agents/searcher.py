"""The Web Searcher Agent (The Scout).

Finds competitors and pain points using the search_web tool.
"""

import datetime
import json
import logging
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from src.graph.state import ResearchState
from src.utils.langchain_models import get_chat_model
from src.agents.tools.search import search_web
from src.prompts.searcher import build_searcher_prompt
from src.config.settings import get_settings
from pydantic import BaseModel

class CompetitorCandidate(BaseModel):
    name: str
    url: str
    snippet: str

class PainPointCandidate(BaseModel):
    text: str
    url: str
    snippet: str

class SearcherOutput(BaseModel):
    competitors: list[CompetitorCandidate]
    pain_points: list[PainPointCandidate]

@tool(args_schema=SearcherOutput)
def submit_search_results(competitors: list[CompetitorCandidate], pain_points: list[PainPointCandidate]):
    """Submit the final search results."""
    pass

logger = logging.getLogger(__name__)

def searcher_node(state: ResearchState) -> dict:
    """Run the searcher ReAct agent."""
    logger.info("Searcher started for job %s", state.get("job_id"))
    
    llm = get_chat_model("searcher")
    agent = create_react_agent(llm, tools=[search_web, submit_search_results])
    
    settings = get_settings()
    max_comps = settings.max_competitors_fast if state.get("depth") == "fast" else settings.max_competitors_deep
    max_pains = settings.max_pain_points_fast if state.get("depth") == "fast" else settings.max_pain_points_deep
    
    prompt = build_searcher_prompt(
        raw_idea=state['raw_idea'],
        max_competitors=max_comps,
        max_pain_points=max_pains,
        strategy=state.get('current_strategy', '')
    )

    try:
        prompt_val = build_searcher_prompt(
            raw_idea=state['raw_idea'],
            max_competitors=max_comps,
            max_pain_points=max_pains,
            strategy=state.get('current_strategy', '')
        )
        
        result = agent.invoke({"messages": prompt_val.format_messages()})
        
        # Extract structured data from the tool call in trajectory
        data_dict = {}
        for msg in reversed(result["messages"]):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc["name"] == "submit_search_results":
                        data_dict = tc["args"]
                        break
                if data_dict:
                    break
                    
        if not data_dict:
            raise ValueError("Agent did not call submit_search_results tool.")
            
        data = SearcherOutput(**data_dict).model_dump()
        
        # Format for state
        source_map = {}
        now = datetime.datetime.now().isoformat()
        
        comp_offset = len(state.get("raw_competitor_candidates", []))
        pain_offset = len(state.get("raw_pain_point_candidates", []))
        
        comps = []
        for i, c in enumerate(data.get("competitors", [])):
            src_id = f"SRC_COMP_{comp_offset + i}"
            url = c.get("url", "")
            title = c.get("name", "")
            comps.append({
                "candidate": {
                    "src_id": src_id,
                    "name": title,
                    "url": url,
                    "snippet": c.get("snippet", "")
                }
            })
            if url:
                source_map[src_id] = {
                    "url": url,
                    "title": title,
                    "snippet": c.get("snippet", ""),
                    "source_type": "web",
                    "fetched_at": now
                }
            
        pains = []
        for i, p in enumerate(data.get("pain_points", [])):
            src_id = f"SRC_PAIN_{pain_offset + i}"
            url = p.get("url", "")
            snippet = p.get("snippet", "")
            text = p.get("text", "")
            pains.append({
                "candidate": {
                    "src_id": src_id,
                    "text": text,
                    "url": url,
                    "snippet": snippet
                }
            })
            if url:
                source_map[src_id] = {
                    "url": url,
                    "title": "Pain Point Source",
                    "snippet": snippet,
                    "source_type": "web",
                    "fetched_at": now
                }
            
        return {
            "raw_competitor_candidates": comps,
            "raw_pain_point_candidates": pains,
            "source_map": source_map,
            "progress_messages": [f"Searcher found {len(comps)} competitors and {len(pains)} pain points."]
        }
        
    except Exception as e:
        logger.error("Searcher failed: %s", e)
        return {
            "progress_messages": ["Searcher failed to execute or parse results."],
            "errors": [str(e)]
        }
