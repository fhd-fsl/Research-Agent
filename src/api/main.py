"""FastAPI synchronous wrapper for the Research Agent.

This implements Build Sequence Step 2 from ARCHITECTURE.md Section 11:
A single /research endpoint that blocks until done. Fine for local testing.
"""

import logging
from typing import Literal

import uuid

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from src.config.settings import get_settings
from src.db.job_store import create_job, get_job, init_db

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Research Agent API",
    description="Async API wrapper for the LangGraph Research Agent.",
    version="0.3.0",
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


class JobSubmitResponse(BaseModel):
    job_id: str
    status: str
    message: str


@app.on_event("startup")
def on_startup():
    """Initialize DB on startup."""
    init_db()


@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "Research Agent API"}


@app.post("/research", status_code=status.HTTP_202_ACCEPTED, response_model=JobSubmitResponse)
def run_research(request: ResearchRequest):
    """Submit a research job to the queue."""
    logger.info("Received research request for idea: %s", request.idea)
    depth = request.depth or settings.default_depth
    
    # Generate a unique job ID
    job_id = f"job_{uuid.uuid4().hex[:8]}"

    try:
        create_job(job_id=job_id, raw_idea=request.idea, depth=depth)
        logger.info("Created job %s with depth %s", job_id, depth)
        
        return JobSubmitResponse(
            job_id=job_id,
            status="pending",
            message="Job submitted successfully. Poll GET /research/{job_id} for status."
        )

    except Exception as e:
        logger.error("Failed to submit job: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to submit job: {str(e)}")


@app.get("/research/{job_id}")
def get_job_status(job_id: str):
    """Poll for job status, progress, and results."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return job
