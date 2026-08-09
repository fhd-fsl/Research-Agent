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

class ParsedIdea(BaseModel):
    """Structured output from the idea_parser node."""
    category: str                         # e.g. "project management", "note-taking"
    target_user: str                      # e.g. "solo founders", "small dev teams"
    core_problem: str                     # one-sentence problem statement
    key_features: list[str]               # what the user described wanting to build
    competitor_search_terms: list[str]     # queries for finding competitors
    pain_point_search_terms: list[str]    # queries for finding complaints
    target_country_code: str = "us"       # ISO 3166-1 alpha-2 country code for app stores
    target_communities: list[str] = []    # dynamic communities to search (e.g. reddit.com, quora.com)


class SourceEntry(TypedDict):
    """A single entry in the source map. Created at ingestion time only."""
    url: str
    title: str
    snippet: str
    source_type: Literal["web", "reddit", "hn", "app_store"]
    fetched_at: str                       # ISO 8601 timestamp


class CompetitorCandidate(TypedDict):
    """A competitor that passed Stage 1 relevance filtering."""
    src_id: str
    name: str
    relevance_score: float                # 0.0–1.0 from Stage 1 filter
    relevance_reasoning: str


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


class PainPointCandidate(TypedDict):
    """A pain point that passed Stage 1 relevance filtering."""
    src_id: str
    text: str
    relevance_score: float
    relevance_reasoning: str


class PainPointCluster(BaseModel):
    """A group of related pain points, output from the clustering node."""
    theme: str                            # e.g. "pricing complaints"
    description: str
    source_count: int                     # number of independent sources
    source_diversity: list[str]           # e.g. ["reddit", "hn", "web"]
    representative_quotes: list[dict[str, str]]  # [{"src_id": ..., "quote": ...}]
    signal_strength: Literal["strong", "moderate", "weak"]


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

    # --- Parsed (set by idea_parser) ---
    parsed_idea: ParsedIdea | None

    # --- Source Map (grows across all ingestion nodes) ---
    source_map: Annotated[dict[str, SourceEntry], merge_dicts]

    # --- Competitor branch ---
    raw_competitor_candidates: list[dict[str, Any]]
    filtered_competitors: list[CompetitorCandidate]
    competitor_profiles: list[CompetitorProfile]

    # --- Pain point branch ---
    raw_pain_point_candidates: list[dict[str, Any]]
    filtered_pain_points: list[PainPointCandidate]
    pain_point_clusters: list[PainPointCluster]

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


def create_initial_state(
    raw_idea: str,
    depth: Literal["fast", "deep"] = "fast",
    job_id: str = "",
) -> ResearchState:
    """Create a blank ResearchState for a new research job."""
    return ResearchState(
        raw_idea=raw_idea,
        depth=depth,
        parsed_idea=None,
        source_map={},
        raw_competitor_candidates=[],
        filtered_competitors=[],
        competitor_profiles=[],
        raw_pain_point_candidates=[],
        filtered_pain_points=[],
        pain_point_clusters=[],
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
    )
