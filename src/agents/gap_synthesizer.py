"""Gap Synthesizer Agent Node.

Implements Pass 2 of the Gap Synthesis Strategy (ARCHITECTURE.md Section 5).
Cross-references pain point clusters against competitor profiles to find
market gaps, and deterministically assigns confidence scores.
"""

import logging
from typing import Any

from pydantic import BaseModel
from src.graph.state import CompetitorProfile, Gap, PainPointCluster, ParsedIdea, ResearchState
from src.prompts.gap_synthesizer import build_messages
from src.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


def _format_idea(parsed_idea: ParsedIdea) -> str:
    return (
        f"Category: {parsed_idea.category}\n"
        f"Target User: {parsed_idea.target_user}\n"
        f"Core Problem: {parsed_idea.core_problem}\n"
        f"Key Features: {', '.join(parsed_idea.key_features)}"
    )

def _format_competitors(profiles: list[CompetitorProfile]) -> str:
    lines = []
    for p in profiles:
        # p.src_ids might have multiple, usually just the first is the main page
        src_tag = f"[{p.src_ids[0] if p.src_ids else 'UNKNOWN'}]"
        features = ', '.join(p.features)
        pricing = p.pricing
        weaknesses = ', '.join(p.weaknesses)
        lines.append(
            f"{src_tag} {p.name} — Features: {features}, "
            f"Pricing: {pricing}, Weaknesses: {weaknesses}"
        )
        if p.app_store_reviews:
            lines.append("   App Store Reviews (Negative):")
            for r in p.app_store_reviews:
                lines.append(f"   - {r.get('score', 0)} Star: {r.get('content', '')[:100]}...")
    return "\n".join(lines)

def _format_clusters(clusters: list[PainPointCluster]) -> str:
    output = []
    for c in clusters:
        output.append(f"### {c.theme} (Signal: {c.signal_strength})")
        output.append(c.description)
        output.append(f"Evidence from: {c.source_count} sources")
        output.append("Quotes:")
        for q in c.representative_quotes:
            output.append(f"- \"{q.get('quote')}\" [{q.get('src_id')}]")
        output.append("")
    return "\n".join(output)

def _compute_gap_confidence(
    gap_data: dict, clusters: list[PainPointCluster], total_competitors: int,
) -> tuple[str, str]:
    """
    Compute gap confidence level based on pain point evidence and competitor failing ratio.
    - strong: strong-signal cluster AND majority competitors fail
    - moderate: moderate-signal cluster OR only some competitors fail
    - weak: weak-signal cluster OR only one competitor fails
    """
    evidence_srcs = set(gap_data.get("pain_point_evidence", []))

    # Find the maximum signal strength across clusters that share evidence with this gap
    signal_rank = {"weak": 0, "moderate": 1, "strong": 2}
    max_signal = "weak"

    for cluster in clusters:
        # Collect all SRC_IDs associated with this cluster
        cluster_src_ids = set()
        for quote in cluster.representative_quotes:
            sid = quote.get("src_id")
            if sid:
                cluster_src_ids.add(sid)

        # If this cluster's sources overlap the gap's evidence,
        # this cluster supports the gap
        if cluster_src_ids & evidence_srcs:
            cluster_signal = cluster.signal_strength
            if signal_rank.get(cluster_signal, 0) > signal_rank.get(max_signal, 0):
                max_signal = cluster_signal

    # Determine competitor failure ratio
    failing_count = len(gap_data.get("competitors_failing", []))
    majority_fail = total_competitors > 0 and failing_count / total_competitors > 0.5

    # Apply the ARCHITECTURE.md confidence matrix
    if max_signal == "strong" and majority_fail:
        return "strong", (
            f"Strong pain point signal ({len(evidence_srcs)} sources) "
            f"and majority of competitors ({failing_count}/{total_competitors}) fail to address it."
        )
    elif max_signal == "moderate" or (max_signal == "strong" and not majority_fail):
        return "moderate", (
            f"{'Moderate' if max_signal == 'moderate' else 'Strong'} pain point signal "
            f"but {'only some' if not majority_fail else 'majority of'} "
            f"competitors ({failing_count}/{total_competitors}) fail."
        )
    elif failing_count <= 1:
        return "weak", (
            f"Weak pain point signal or only {failing_count} competitor fails to address this."
        )
    else:
        return "moderate", "Moderate evidence and competitor overlap."


class RawGapData(BaseModel):
    title: str
    description: str
    pain_point_evidence: list[str]
    competitor_evidence: list[str]
    competitors_failing: list[str]
    competitors_partial: list[str]


class GapSynthesis(BaseModel):
    """Pydantic model for the gap synthesis LLM output."""
    gaps: list[RawGapData]
    landscape_summary: str
    positioning_suggestions: list[str]


def gap_synthesizer(state: ResearchState) -> dict:
    """Cross-reference clusters with competitors to find gaps."""
    parsed_idea = state.get("parsed_idea")
    competitors = state.get("competitor_profiles", [])
    clusters = state.get("pain_point_clusters", [])

    if not parsed_idea or not competitors or not clusters:
        return {
            "gaps": [],
            "landscape_summary": "Insufficient data to synthesize gaps.",
            "positioning_suggestions": [],
            "progress_messages": ["Skipped synthesis due to missing data."],
            "errors": [
                "Gap synthesis skipped: missing parsed_idea, "
                "competitors, or pain point clusters."
            ],
        }

    idea_text = _format_idea(parsed_idea)
    comps_text = _format_competitors(competitors)
    clusters_text = _format_clusters(clusters)

    client = LLMClient()
    messages = build_messages(idea_text, comps_text, clusters_text)

    try:
        response = client.complete(
            task="gap_synthesis",
            messages=messages,
            temperature=0.3,
            response_model=GapSynthesis,
        )
        parsed = response.parse_pydantic(GapSynthesis)
    except Exception as e:
        logger.error("Gap synthesis failed: %s", e)
        return {
            "gaps": [],
            "landscape_summary": "",
            "positioning_suggestions": [],
            "progress_messages": [f"Synthesis failed: {e}"],
            "errors": [f"Gap synthesis LLM call failed: {e}"],
        }

    gaps_data = parsed.gaps
    gaps = []

    for g_data in gaps_data:
        # Convert Pydantic model to dict for _compute_gap_confidence compatibility
        # since it expects a dictionary.
        confidence, reasoning = _compute_gap_confidence(g_data.model_dump(), clusters, len(competitors))
        gap = Gap(
            title=g_data.title,
            description=g_data.description,
            confidence=confidence,  # type: ignore
            confidence_reasoning=reasoning,
            pain_point_evidence=g_data.pain_point_evidence,
            competitor_evidence=g_data.competitor_evidence,
            competitors_failing=g_data.competitors_failing,
            competitors_partial=g_data.competitors_partial,
        )
        gaps.append(gap)

    return {
        "gaps": gaps,
        "landscape_summary": parsed.landscape_summary,
        "positioning_suggestions": parsed.positioning_suggestions,
        "token_usage": {response.provider: response.input_tokens + response.output_tokens},
        "progress_messages": [f"Synthesized {len(gaps)} market gaps."]
    }
