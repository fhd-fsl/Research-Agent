"""Relevance Filter Agent Nodes.

Implements Stage 1 of the two-stage filtering process (ARCHITECTURE.md Section 3).
Uses Groq (fast, cheap) to evaluate raw candidates before deep extraction.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from src.config.settings import get_settings
from src.graph.state import CompetitorCandidate, PainPointCandidate, ParsedIdea, ResearchState
from src.prompts.relevance_filter import build_competitor_messages, build_pain_point_messages
from src.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


def format_idea_summary(parsed_idea: ParsedIdea) -> str:
    """Format the parsed idea for the filter prompt."""
    return (
        f"Category: {parsed_idea.category}\n"
        f"Target User: {parsed_idea.target_user}\n"
        f"Core Problem: {parsed_idea.core_problem}\n"
    )

def _evaluate_candidate(
    client: LLMClient, task: str, messages: list[dict], candidate: dict,
) -> dict:
    """Evaluate a single candidate using the LLM client. Runs in a thread pool."""
    try:
        response = client.complete(
            task=task,
            messages=messages,
            temperature=0.0,
            json_mode=True,
        )
        parsed = response.parse_json()
        return {
            "candidate": candidate,
            "relevant": parsed.get("relevant", "NO"),
            "reasoning": parsed.get("reasoning", ""),
            "tokens": response.input_tokens + response.output_tokens,
            "provider": response.provider
        }
    except Exception as e:
        logger.warning("Filter evaluation failed for %s: %s", candidate.get("src_id"), e)
        return {
            "candidate": candidate,
            "relevant": "NO",
            "reasoning": f"Error: {e}",
            "tokens": 0,
            "provider": "unknown"
        }


def _aggregate_tokens(results: list[dict]) -> dict[str, int]:
    """Aggregate token usage per-provider across all evaluation results."""
    token_usage: dict[str, int] = {}
    for res in results:
        provider = res.get("provider", "unknown")
        if provider != "unknown" and res["tokens"] > 0:
            token_usage[provider] = token_usage.get(provider, 0) + res["tokens"]
    return token_usage


def competitor_relevance_filter(state: ResearchState) -> dict:
    """Filter raw competitor candidates using Groq."""
    raw_candidates = state.get("raw_competitor_candidates", [])
    if not raw_candidates:
        return {
            "filtered_competitors": [],
            "progress_messages": ["No raw competitor candidates to filter."],
        }

    parsed_idea = state["parsed_idea"]
    idea_summary = format_idea_summary(parsed_idea)  # type: ignore
    settings = get_settings()
    depth = state.get("depth", settings.default_depth)
    max_output = settings.max_competitors_fast if depth == "fast" else settings.max_competitors_deep

    client = LLMClient()
    all_results = []
    filtered = []

    # Run evaluations in parallel to speed up Stage 1
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        for cand in raw_candidates:
            messages = build_competitor_messages(
                idea_summary, cand.get("title", ""), cand.get("snippet", ""),
            )
            futures.append(
                executor.submit(_evaluate_candidate, client, "relevance_filter", messages, cand)
            )

        for future in as_completed(futures):
            res = future.result()
            all_results.append(res)

            if res["relevant"] in ("YES", "MAYBE"):
                # Score mapping for downstream sorting
                score = 1.0 if res["relevant"] == "YES" else 0.5
                filtered.append(CompetitorCandidate(
                    src_id=res["candidate"]["src_id"],
                    # We'll extract true name in deep dive
                    name=res["candidate"].get("title", "Unknown"),
                    relevance_score=score,
                    relevance_reasoning=res["reasoning"]
                ))

    # Sort by score descending, then cap to max_output
    filtered.sort(key=lambda x: x["relevance_score"], reverse=True)
    filtered = filtered[:max_output]

    token_usage = _aggregate_tokens(all_results)

    return {
        "filtered_competitors": filtered,
        "token_usage": token_usage,
        "progress_messages": [
            f"Filtered {len(raw_candidates)} competitors down to "
            f"{len(filtered)} relevant candidates (capped at {max_output})."
        ]
    }


def pain_point_relevance_filter(state: ResearchState) -> dict:
    """Filter raw pain point candidates using Groq."""
    raw_candidates = state.get("raw_pain_point_candidates", [])
    if not raw_candidates:
        return {
            "filtered_pain_points": [],
            "progress_messages": ["No raw pain point candidates to filter."],
        }

    parsed_idea = state["parsed_idea"]
    idea_summary = format_idea_summary(parsed_idea)  # type: ignore
    depth = state.get("depth", "fast")

    # Cap from ARCHITECTURE.md Section 8: pain points into clustering: 8 (fast) or 15 (deep)
    max_output = 8 if depth == "fast" else 15

    client = LLMClient()
    all_results = []
    filtered = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        for cand in raw_candidates:
            messages = build_pain_point_messages(
                idea_summary, cand.get("title", ""), cand.get("snippet", ""),
            )
            futures.append(
                executor.submit(_evaluate_candidate, client, "relevance_filter", messages, cand)
            )

        for future in as_completed(futures):
            res = future.result()
            all_results.append(res)

            if res["relevant"] in ("YES", "MAYBE"):
                score = 1.0 if res["relevant"] == "YES" else 0.5
                filtered.append(PainPointCandidate(
                    src_id=res["candidate"]["src_id"],
                    text=res["candidate"].get("snippet", ""),
                    relevance_score=score,
                    relevance_reasoning=res["reasoning"]
                ))

    # Sort by score descending, then cap to max_output
    filtered.sort(key=lambda x: x["relevance_score"], reverse=True)
    filtered = filtered[:max_output]

    token_usage = _aggregate_tokens(all_results)

    return {
        "filtered_pain_points": filtered,
        "token_usage": token_usage,
        "progress_messages": [
            f"Filtered {len(raw_candidates)} pain points down to "
            f"{len(filtered)} relevant discussions (capped at {max_output})."
        ]
    }
