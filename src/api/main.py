"""FastAPI synchronous wrapper for the Research Agent.

This implements Build Sequence Step 2 from ARCHITECTURE.md Section 11:
A single /research endpoint that blocks until done. Fine for local testing.
"""

import logging
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.config.settings import get_settings
from src.graph.build_graph import build_graph
from src.graph.state import create_initial_state

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Research Agent API",
    description="Synchronous API wrapper for the LangGraph Research Agent.",
    version="0.2.0",
)

# Set up logging for the app
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class ResearchRequest(BaseModel):
    idea: str
    depth: Literal["fast", "deep"] | None = None


class ResearchResponse(BaseModel):
    job_id: str
    report_markdown: str
    report_json: dict


@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "Research Agent API"}


@app.post("/research", response_model=ResearchResponse)
def run_research(request: ResearchRequest):
    """Run a full research job synchronously and return the report.
    
    Warning: This endpoint blocks for several minutes depending on depth.
    """
    logger.info("Received research request for idea: %s", request.idea)
    depth = request.depth or settings.default_depth

    try:
        # Initialize state
        state = create_initial_state(raw_idea=request.idea, depth=depth)
        job_id = state["job_id"]
        logger.info("Created job %s with depth %s", job_id, depth)

        # Build and run the graph
        graph = build_graph()
        final_state = graph.invoke(state)

        logger.info("Job %s completed successfully", job_id)
        
        # Build the final response JSON explicitly rather than dumping the whole state
        report_json = {
            "idea": final_state.get("parsed_idea"),
            "landscape_summary": final_state.get("landscape_summary", ""),
            "competitor_profiles": final_state.get("competitor_profiles", []),
            "pain_point_clusters": final_state.get("pain_point_clusters", []),
            "gaps": final_state.get("gaps", []),
            "positioning_suggestions": final_state.get("positioning_suggestions", []),
            "sources": final_state.get("source_map", {}),
        }

        return ResearchResponse(
            job_id=job_id,
            report_markdown=final_state.get("report_markdown", ""),
            report_json=report_json,
        )

    except Exception as e:
        logger.error("Research job failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Research job failed: {str(e)}")
