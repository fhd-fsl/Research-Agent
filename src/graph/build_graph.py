"""LangGraph Builder.

Wires the agent nodes together into a StateGraph, implementing the topology
defined in ARCHITECTURE.md Section 2.
"""

from langgraph.graph import END, START, StateGraph

from src.agents.competitor_deep_dive import competitor_deep_dive
from src.agents.competitor_searcher import competitor_searcher
from src.agents.gap_synthesizer import gap_synthesizer
from src.agents.idea_parser import idea_parser
from src.agents.pain_point_clusterer import pain_point_clusterer
from src.agents.pain_point_miner import pain_point_miner
from src.agents.relevance_filter import competitor_relevance_filter, pain_point_relevance_filter
from src.agents.report_builder import report_builder
from src.graph.state import ResearchState


def build_graph() -> StateGraph:
    """Build and compile the research agent graph."""
    builder = StateGraph(ResearchState)

    # 1. Add all nodes
    builder.add_node("idea_parser", idea_parser)
    builder.add_node("competitor_searcher", competitor_searcher)
    builder.add_node("pain_point_miner", pain_point_miner)
    builder.add_node("competitor_relevance_filter", competitor_relevance_filter)
    builder.add_node("pain_point_relevance_filter", pain_point_relevance_filter)
    builder.add_node("competitor_deep_dive", competitor_deep_dive)
    builder.add_node("pain_point_clusterer", pain_point_clusterer)
    builder.add_node("gap_synthesizer", gap_synthesizer)
    builder.add_node("report_builder", report_builder)

    # 2. Add edges

    # Entry point
    builder.add_edge(START, "idea_parser")

    # Fan-out to parallel branches
    builder.add_edge("idea_parser", "competitor_searcher")
    builder.add_edge("idea_parser", "pain_point_miner")

    # Competitor branch
    builder.add_edge("competitor_searcher", "competitor_relevance_filter")
    builder.add_edge("competitor_relevance_filter", "competitor_deep_dive")

    # Pain point branch
    builder.add_edge("pain_point_miner", "pain_point_relevance_filter")
    builder.add_edge("pain_point_relevance_filter", "pain_point_clusterer")

    # Fan-in (synthesis)
    builder.add_edge("competitor_deep_dive", "gap_synthesizer")
    builder.add_edge("pain_point_clusterer", "gap_synthesizer")

    # Final formatting
    builder.add_edge("gap_synthesizer", "report_builder")
    builder.add_edge("report_builder", END)

    return builder.compile()
