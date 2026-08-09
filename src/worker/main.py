"""Background worker to execute jobs from the SQLite queue."""

import logging
import time
from typing import Any

from src.config.settings import get_settings
from src.db.job_store import append_progress, claim_pending_job, init_db, update_job_status
from src.graph.build_graph import build_graph
from src.graph.state import create_initial_state

logger = logging.getLogger(__name__)


def process_job(job: dict[str, Any]):
    """Process a single job."""
    job_id = job["job_id"]
    raw_idea = job["raw_idea"]
    depth = job["depth"]

    logger.info("Starting job %s: '%s'", job_id, raw_idea)
    update_job_status(job_id, "running")

    try:
        # Initialize state
        state = create_initial_state(raw_idea=raw_idea, depth=depth)
        
        # Override the random job_id from create_initial_state with our actual DB job_id
        state["job_id"] = job_id 
        
        graph = build_graph()
        
        # Stream the graph execution so we can catch intermediate progress updates
        final_state = state
        for update in graph.stream(state):
            # The update is a dict where keys are node names and values are state diffs
            for node_name, state_diff in update.items():
                logger.info("Job %s finished node: %s", job_id, node_name)
                
                # Check if this node added any progress messages
                if "progress_messages" in state_diff and state_diff["progress_messages"]:
                    append_progress(job_id, state_diff["progress_messages"])
                    
                # Keep accumulating the final state
                final_state.update(state_diff)
                
        logger.info("Job %s completed successfully", job_id)
        
        parsed_idea = final_state.get("parsed_idea")
        competitor_profiles = final_state.get("competitor_profiles", [])
        pain_point_clusters = final_state.get("pain_point_clusters", [])
        gaps = final_state.get("gaps", [])
        
        report_json = {
            "idea": parsed_idea.model_dump() if parsed_idea else None,
            "landscape_summary": final_state.get("landscape_summary", ""),
            "competitor_profiles": [c.model_dump() for c in competitor_profiles] if competitor_profiles else [],
            "pain_point_clusters": [p.model_dump() for p in pain_point_clusters] if pain_point_clusters else [],
            "gaps": [g.model_dump() for g in gaps] if gaps else [],
            "positioning_suggestions": final_state.get("positioning_suggestions", []),
            "sources": final_state.get("source_map", {}),
        }
        
        result = {
            "report_markdown": final_state.get("report_markdown", ""),
            "report_json": report_json,
        }
        
        update_job_status(job_id, "completed", result=result)

    except Exception as e:
        logger.exception("Job %s failed with error: %s", job_id, e)
        append_progress(job_id, [f"Fatal error: {str(e)}"])
        update_job_status(job_id, "failed")


def run_worker():
    """Main polling loop."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    logger.info("Initializing database...")
    init_db()
    
    logger.info("Starting worker loop...")
    while True:
        try:
            job = claim_pending_job()
            if job:
                process_job(job)
            else:
                time.sleep(2.0)  # Polling interval
        except KeyboardInterrupt:
            logger.info("Worker shutting down.")
            break
        except Exception as e:
            logger.error("Worker error in polling loop: %s", e)
            time.sleep(5.0)


if __name__ == "__main__":
    run_worker()
