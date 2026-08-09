"""Pain Point Clusterer Agent Node.

Implements Pass 1 of the Gap Synthesis Strategy (ARCHITECTURE.md Section 5).
Takes the filtered pain points, formats them with their SRC_IDs, and uses
Groq to group them into themes. Computes signal strength deterministically.
"""

import logging

from src.graph.state import PainPointCluster, ResearchState
from src.ingestion.source_map import SourceMap
from src.prompts.pain_point_clusterer import build_messages
from src.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


def _compute_signal_strength(source_count: int, source_diversity_count: int) -> str:
    """Compute signal strength deterministically based on ARCHITECTURE.md rules.

    Rules:
    - strong: 3+ independent sources AND 2+ source types (e.g. Reddit + HN)
    - moderate: 2 independent sources OR 3+ from same source type
    - weak: single source

    The "3+ from same source type" condition is checked as:
    source_count >= 3 AND source_diversity_count == 1 (all from one type).
    """
    if source_count >= 3 and source_diversity_count >= 2:
        return "strong"
    elif source_count >= 2 or (source_count >= 3 and source_diversity_count == 1):
        return "moderate"
    else:
        return "weak"


def pain_point_clusterer(state: ResearchState) -> dict:
    """Group pain points into clusters and assign signal strength."""
    filtered = state.get("filtered_pain_points", [])
    if not filtered:
        return {
            "pain_point_clusters": [],
            "progress_messages": ["No filtered pain points to cluster."],
        }

    source_map = SourceMap(existing_map=state.get("source_map", {}))

    # Format input with SRC_IDs
    formatted_points = []
    for p in filtered:
        # e.g. "[SRC_01] User says: The pricing is too high..."
        formatted_points.append(f"[{p['src_id']}] {p['text']}")

    pain_points_text = "\n\n".join(formatted_points)

    client = LLMClient()
    messages = build_messages(pain_points_text)

    try:
        response = client.complete(
            task="pain_point_clustering",
            messages=messages,
            temperature=0.1,
            json_mode=True,
        )
        parsed = response.parse_json()
    except Exception as e:
        logger.error("Pain point clustering failed: %s", e)
        return {
            "pain_point_clusters": [],
            "progress_messages": [f"Clustering failed: {e}"],
            "errors": [f"Pain point clustering LLM call failed: {e}"],
        }

    clusters_data = parsed.get("clusters", [])
    clusters = []

    for c_data in clusters_data:
        src_ids = c_data.get("source_ids", [])
        # Determine source diversity by checking the source_type in the source map
        source_types = set()
        for sid in src_ids:
            try:
                entry = source_map.get(sid)
                source_types.add(entry["source_type"])
            except KeyError:
                pass

        signal = _compute_signal_strength(len(src_ids), len(source_types))

        cluster = PainPointCluster(
            theme=c_data.get("theme", "Unknown Theme"),
            description=c_data.get("description", ""),
            source_count=len(src_ids),
            source_diversity=list(source_types),
            representative_quotes=c_data.get("representative_quotes", []),
            signal_strength=signal  # type: ignore
        )
        clusters.append(cluster)

    return {
        "pain_point_clusters": clusters,
        "token_usage": {response.provider: response.input_tokens + response.output_tokens},
        "progress_messages": [f"Clustered {len(filtered)} pain points into {len(clusters)} themes."]
    }
