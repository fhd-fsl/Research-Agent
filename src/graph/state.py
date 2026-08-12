"""Research state schema and data types.

This module defines the LangGraph state and all data structures that flow
between agent nodes. Matches the schema in ARCHITECTURE.md Section 9.

All inter-node communication goes through ResearchState. No globals,
no side channels, no agents writing to disk on their own.
"""

from __future__ import annotations

import operator
import uuid
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Reducer functions for state fields that accumulate across nodes
# ---------------------------------------------------------------------------

def merge_dicts(existing: dict, update: dict) -> dict:
    """Merge two dicts. Update values overwrite existing on key conflict."""
    return {**existing, **update}


def merge_token_usage(existing: dict[str, int], update: dict[str, int]) -> dict[str, int]:
    """Additively merge token usage counters across providers."""
    result = dict(existing)
    for provider, tokens in update.items():
        result[provider] = result.get(provider, 0) + tokens
    return result


# ---------------------------------------------------------------------------
# Sub-structures stored as state field values
# ---------------------------------------------------------------------------

class SourceEntry(TypedDict):
    """A single entry in the source map. Created at ingestion time only."""
    url: str
    title: str
    snippet: str
    source_type: Literal["web", "reddit", "hn", "app_store"]
    fetched_at: str                       # ISO 8601 timestamp


class CompetitorProfile(BaseModel):
    """Deep-dive output for a single competitor."""
    src_ids: list[str]                    # multiple sources may inform one profile
    name: str
    url: str
    pricing: str                          # extracted pricing summary
    features: list[str]
    positioning: str                      # how they describe themselves
    weaknesses: list[str]                 # from reviews/complaints about them
    has_mobile_app: bool
    app_store_reviews: list[dict[str, Any]] = Field(default_factory=list)  # 1-2 star reviews if app exists

class PainPointProfile(BaseModel):
    """Deep-dive output for a single pain point URL."""
    src_id: str
    url: str
    core_problem: str
    detailed_frustrations: list[str]
    representative_quotes: list[str]


class Gap(BaseModel):
    """A market gap identified by cross-referencing pain points with competitors."""
    title: str
    description: str
    confidence: Literal["strong", "moderate", "weak"]
    confidence_reasoning: str
    pain_point_evidence: list[str]        # SRC_IDs
    competitor_evidence: list[str]        # SRC_IDs
    competitors_failing: list[str]        # competitor names
    competitors_partial: list[str]        # competitor names


# ---------------------------------------------------------------------------
# Top-level LangGraph state
# ---------------------------------------------------------------------------

class ResearchState(TypedDict):
    """The central state object passed through all agent nodes.

    Reducer annotations:
    - source_map: merges dicts (new sources added by each ingestion node)
    - progress_messages / errors: appended to by each node via operator.add
    - token_usage: additively merged per-provider counters
    All other fields use default replace semantics.
    """

    # --- Input (set once at job creation) ---
    raw_idea: str
    depth: Literal["fast", "deep"]

    # --- Source Map (grows across all ingestion nodes) ---
    source_map: Annotated[dict[str, SourceEntry], merge_dicts]

    # --- Competitor branch ---
    raw_competitor_candidates: Annotated[list[dict[str, Any]], operator.add]
    competitor_profiles: Annotated[list[CompetitorProfile], operator.add]

    # --- Pain point branch ---
    raw_pain_point_candidates: Annotated[list[dict[str, Any]], operator.add]
    pain_point_profiles: Annotated[list[PainPointProfile], operator.add]

    # --- State Tracking ---
    processed_candidates: Annotated[list[str], operator.add]

    # --- Synthesis output ---
    gaps: list[Gap]
    landscape_summary: str
    positioning_suggestions: list[str]

    # --- Final report (both formats, per resolved design decision) ---
    report_json: dict[str, Any]
    report_markdown: str

    # --- Job metadata ---
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    progress_messages: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]
    token_usage: Annotated[dict[str, int], merge_token_usage]
    next_agent: str
    current_strategy: str


def create_initial_state(
    raw_idea: str,
    depth: Literal["fast", "deep"] = "fast",
    job_id: str = "",
) -> ResearchState:
    """Create a blank ResearchState for a new research job."""
    return ResearchState(
        raw_idea=raw_idea,
        depth=depth,
        source_map={},
        raw_competitor_candidates=[],
        competitor_profiles=[],
        raw_pain_point_candidates=[],
        pain_point_profiles=[],
        processed_urls=[],
        gaps=[],
        landscape_summary="",
        positioning_suggestions=[],
        report_json={},
        report_markdown="",
        job_id=job_id or f"job_{uuid.uuid4().hex[:8]}",
        status="pending",
        progress_messages=[],
        errors=[],
        token_usage={},
        next_agent="searcher",
        current_strategy="",
    )
