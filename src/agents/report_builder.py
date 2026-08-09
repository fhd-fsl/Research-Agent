"""Report Builder Agent Node.

Formats the final research state into both JSON and a Markdown report.
Uses Groq to generate the Markdown, then deterministically resolves SRC_IDs
into real URLs using the SourceMap, as per ARCHITECTURE.md Section 4.
"""

import logging
import re

from src.graph.state import CompetitorProfile, Gap, PainPointCluster, ResearchState
from src.ingestion.source_map import SourceMap
from src.prompts.report_builder import build_messages
from src.utils.llm_client import LLMClient

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


def _format_clusters_for_prompt(clusters: list[PainPointCluster]) -> str:
    """Format pain point clusters for inclusion in the report prompt."""
    lines = []
    for c in clusters:
        theme = c.theme
        signal = c.signal_strength
        count = c.source_count
        lines.append(f'"{theme}" (Signal: {signal}, {count} sources)')
        lines.append(f"  {c.description}")
        for quote in c.representative_quotes:
            lines.append(f"  - [{quote.get('src_id')}] '{quote.get('quote')}'")
        lines.append("")
    return "\n".join(lines)


def report_builder(state: ResearchState) -> dict:
    """Format the final report in JSON and Markdown, resolving citations."""
    gaps = state.get("gaps", [])
    landscape = state.get("landscape_summary", "")
    competitors = state.get("competitor_profiles", [])
    clusters = state.get("pain_point_clusters", [])
    positioning = state.get("positioning_suggestions", [])
    source_map = SourceMap(existing_map=state.get("source_map", {}))

    # 1. JSON Report (Programmatic/UI) — includes all data
    report_json = {
        "idea": state.get("parsed_idea"),
        "landscape_summary": landscape,
        "competitor_profiles": competitors,
        "pain_point_clusters": clusters,
        "gaps": gaps,
        "positioning_suggestions": positioning,
        "sources": source_map.to_dict()
    }

    # 2. Markdown Report — now includes competitor profiles and pain points
    client = LLMClient()
    competitors_text = _format_competitors_for_prompt(competitors)
    clusters_text = _format_clusters_for_prompt(clusters)
    positioning_text = (
        "\n".join(f"- {s}" for s in positioning)
        if positioning
        else "None available."
    )

    messages = build_messages(
        landscape,
        competitors_text,
        clusters_text,
        _format_gaps_for_prompt(gaps),
        positioning_text,
    )

    try:
        response = client.complete(
            task="report_formatting",
            messages=messages,
            temperature=0.2,
            json_mode=False,
        )
        raw_markdown = response.content
        tokens = response.input_tokens + response.output_tokens
        provider = response.provider
    except Exception as e:
        logger.error("Report formatting failed: %s", e)
        raw_markdown = f"# Error\n\nFailed to format report: {e}"
        tokens = 0
        provider = "unknown"

    # 3. Deterministic Citation Resolution
    # Find all [SRC_XXXX] tags and replace with [1](url)

    # Extract unique SRC IDs used in the text
    src_tags = set(re.findall(r"\[(SRC_[A-Z0-9]{4})\]", raw_markdown))

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
