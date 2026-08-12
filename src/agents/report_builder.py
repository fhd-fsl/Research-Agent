"""Report Builder Agent Node.

Formats the final research state into both JSON and a Markdown report.
Uses Groq to generate the Markdown, then deterministically resolves SRC_IDs
into real URLs using the SourceMap, as per ARCHITECTURE.md Section 4.
"""

import logging
import re

from src.graph.state import CompetitorProfile, Gap, ResearchState
from src.ingestion.source_map import SourceMap
from src.prompts.report_builder import build_report_prompt
from src.utils.langchain_models import get_chat_model
from langchain_core.messages import SystemMessage
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


def _format_gaps_for_prompt(gaps: list[Gap]) -> str:
    lines = []
    for g in gaps:
        lines.append(f"Gap: {g.title} (Confidence: {g.confidence})")
        lines.append(f"Description: {g.description}")
        lines.append(f"Failing Competitors: {', '.join(g.competitors_failing)}")
        lines.append(f"Pain Point Evidence: {', '.join(g.pain_point_evidence)}")
        lines.append(f"Competitor Evidence: {', '.join(g.competitor_evidence)}")
        lines.append("")
    return "\n".join(lines)


def _format_competitors_for_prompt(profiles: list[CompetitorProfile]) -> str:
    """Format competitor profiles for inclusion in the report prompt."""
    lines = []
    for p in profiles:
        src_tag = f"[{p.src_ids[0] if p.src_ids else 'UNKNOWN'}]"
        lines.append(f"{src_tag} {p.name}")
        lines.append(f"  Pricing: {p.pricing}")
        lines.append(f"  Features: {', '.join(p.features)}")
        lines.append(f"  Positioning: {p.positioning}")
        lines.append(f"  Weaknesses: {', '.join(p.weaknesses)}")
        if p.app_store_reviews:
            lines.append("  App Store Reviews (Negative):")
            for r in p.app_store_reviews:
                src_id = r.get("src_id", "")
                tag = f"[{src_id}] " if src_id else ""
                lines.append(f"    - {tag}{r.get('score', '?')} Star: {r.get('content', '')[:100]}")
        lines.append("")
    return "\n".join(lines)


def _format_pain_points_for_prompt(pain_points: list[dict]) -> str:
    """Format pain points for inclusion in the report prompt."""
    lines = []
    for p in pain_points:
        cand = p.get("candidate", {})
        src_id = cand.get("src_id", "UNKNOWN")
        text = cand.get("text", "")
        lines.append(f"- [{src_id}] {text}")
    return "\n".join(lines)


def report_builder(state: ResearchState) -> dict:
    """Format the final report in JSON and Markdown, resolving citations."""
    llm = get_chat_model(task="report_formatting", temperature=get_settings().report_temperature)
    gaps = state.get("gaps", [])
    landscape = state.get("landscape_summary", "")
    competitors = state.get("competitor_profiles", [])
    pain_points = state.get("raw_pain_point_candidates", [])
    positioning = state.get("positioning_suggestions", [])
    source_map = SourceMap(existing_map=state.get("source_map", {}))

    # 1. JSON Report (Programmatic/UI) — includes all data
    report_json = {
        "idea": state.get("raw_idea"),
        "landscape_summary": landscape,
        "competitor_profiles": [c.model_dump() if hasattr(c, "model_dump") else c for c in competitors],
        "pain_points": pain_points,
        "gaps": [g.model_dump() if hasattr(g, "model_dump") else g for g in gaps],
        "positioning_suggestions": positioning,
        "sources": source_map.to_dict()
    }

    # 2. Format inputs for the prompt
    landscape_text = state.get("landscape_summary", "")
    competitors_text = _format_competitors_for_prompt(state.get("competitor_profiles", []))
    pain_points_text = _format_pain_points_for_prompt(state.get("raw_pain_point_candidates", []))
    gaps_text = _format_gaps_for_prompt(state.get("gaps", []))
    
    # 3. Build messages
    prompt = build_report_prompt(
        landscape=landscape_text,
        competitors_text=competitors_text,
        clusters_text=pain_points_text,
        gaps=gaps_text,
        positioning="\n".join(state.get("positioning_suggestions", [])),
    )

    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        raw_markdown = response.content
        logger.info("report_builder generated markdown report successfully")
        usage = response.response_metadata.get("token_usage", {})
        tokens = usage.get("total_tokens", 0)
        provider = "groq"
    except Exception as e:
        logger.error("Report formatting failed: %s", e)
        raw_markdown = f"# Error\n\nFailed to format report: {e}"
        tokens = 0
        provider = "unknown"

    # 3. Deterministic Citation Resolution
    # Find all [SRC_XXXX] tags and replace with [1](url)

    # Extract unique SRC IDs used in the text
    src_tags = set(re.findall(r"\[(SRC_[A-Z0-9_]+)\]", raw_markdown))

    # Create a numbered reference mapping
    ref_map = {}
    ref_list_md = ["\n\n## Sources\n"]

    for idx, tag in enumerate(sorted(src_tags), 1):
        try:
            url = source_map.resolve(tag)
            entry = source_map.get(tag)
            title = entry.get("title", url)
            # Shorten title if it's too long
            if len(title) > 50:
                title = title[:47] + "..."
            ref_map[tag] = f"[[{idx}]]({url})"
            ref_list_md.append(f"{idx}. [{title}]({url})")
        except KeyError:
            ref_map[tag] = f"[{tag}]"

    # Replace tags in the markdown
    final_markdown = raw_markdown
    for tag, replacement in ref_map.items():
        final_markdown = final_markdown.replace(f"[{tag}]", replacement)

    # Append the source list if we had any citations
    if len(src_tags) > 0:
        final_markdown += "\n".join(ref_list_md)

    return {
        "report_json": report_json,
        "report_markdown": final_markdown,
        "token_usage": {provider: tokens} if provider != "unknown" else {},
        "progress_messages": ["Report formatting and citation resolution complete."]
    }
